"""Self-contained versioned CSV snapshots, no motion/UART/ADC imports.
Exclusive publication uses a same-directory temporary file + hard link, never overwrite.
Filesystem must support hard links. Directory durability after power failure is not guaranteed.
"""
import csv, hashlib, io, json, math, os, re, tempfile
from pathlib import Path
FIELDS = ['point','quantity','value','unit','quality_flags']
PREFIX = '# pynq_result_history_v1 '

def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(',',':'))

def validate_snapshot(meta, rows):
    # Detach objects and prohibit NaN throughout metadata before any IO.
    meta = json.loads(_json(meta))
    rows = json.loads(_json(rows))
    if not isinstance(meta,dict) or type(meta.get('schema_version')) is not int or meta.get('schema_version') != 1:
        raise ValueError('unknown schema version')
    if not isinstance(meta.get('run_id'),str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',meta['run_id']):
        raise ValueError('invalid run_id')
    if meta.get('source') not in ('MOCK','BOARD') or type(meta.get('complete')) is not bool:
        raise ValueError('source and completion must be explicit')
    if type(meta.get('expected_points')) is not int or not 1 <= meta['expected_points'] <= 10000:
        raise ValueError('invalid point count')
    def safe_label(text):
        return isinstance(text,str) and bool(text) and text == text.strip() and text[0] not in '=+-@' and not any(ord(c)<32 for c in text)
    quantities = meta.get('quantities')
    if not isinstance(quantities,dict) or not quantities or any(not safe_label(k) or not safe_label(v) for k,v in quantities.items()):
        raise ValueError('quantity to unit contract required')
    if len(quantities) > 64 or not isinstance(rows,list) or len(rows) > 640000:
        raise ValueError('snapshot too large')
    if not isinstance(meta.get('provenance'),dict) or not meta['provenance']:
        raise ValueError('provenance required; BOARD remains a caller claim')
    seen = set()
    for r in rows:
        if not isinstance(r,dict) or set(r) != set(FIELDS): raise ValueError('invalid row schema')
        point,quantity,value = r['point'],r['quantity'],r['value']
        if type(point) is not int or not 1 <= point <= meta['expected_points'] or not isinstance(quantity,str) or quantity not in quantities:
            raise ValueError('invalid point or quantity')
        if r['unit'] != quantities[quantity]: raise ValueError('unit mismatch')
        key = point,quantity
        if key in seen: raise ValueError('duplicate point/quantity')
        seen.add(key)
        flags = r['quality_flags']
        if not isinstance(flags,list) or any(not isinstance(f,str) or not f for f in flags):
            raise ValueError('invalid quality flags')
        if value is None:
            if not flags: raise ValueError('missing value needs a quality flag')
        elif isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
            raise ValueError('invalid value')
    if meta['complete'] and len(seen) != meta['expected_points'] * len(quantities):
        raise ValueError('complete snapshot must contain all point/quantity pairs')
    return meta,rows

def save_snapshot(directory, meta, rows):
    meta,rows = validate_snapshot(meta,rows)
    directory = Path(directory)
    directory.mkdir(parents=True,exist_ok=True)
    target = directory/(meta['run_id']+'.csv')
    fd,temp = tempfile.mkstemp(prefix='.snapshot_',suffix='.tmp',dir=directory)
    try:
        with os.fdopen(fd,'w',encoding='utf-8',newline='') as f:
            f.write(PREFIX + _json(meta) + '\n')
            writer = csv.DictWriter(f,fieldnames=FIELDS)
            writer.writeheader()
            for r in rows:
                writer.writerow({**r,'value': _json(r['value']), 'quality_flags':_json(r['quality_flags'])})
            f.flush();os.fsync(f.fileno())
        # Atomic exclusive publish on supporting local filesystems; no replace fallback.
        os.link(temp,target)
    finally:
        Path(temp).unlink(missing_ok=True)
    return target

def load_snapshot(path, max_bytes=16_000_000):
    if type(max_bytes) is not int or max_bytes <= 0: raise ValueError('invalid byte limit')
    with Path(path).open('rb') as f: data = f.read(max_bytes+1)
    if len(data)>max_bytes: raise ValueError('CSV too large')
    stream = io.StringIO(data.decode('utf-8'))
    line = stream.readline()
    if not line.startswith(PREFIX): raise ValueError('unknown CSV format')
    meta = json.loads(line[len(PREFIX):])
    reader = csv.DictReader(stream)
    if reader.fieldnames != FIELDS: raise ValueError('invalid CSV columns')
    rows = []
    for r in reader:
        if None in r or any(v is None for v in r.values()): raise ValueError('malformed CSV row')
        rows.append({'point':int(r['point']),'quantity':r['quantity'],'value':json.loads(r['value']),
                     'unit':r['unit'],'quality_flags':json.loads(r['quality_flags'])})
    meta,rows = validate_snapshot(meta,rows)
    return {'metadata':meta,'records':rows,'sha256':hashlib.sha256(data).hexdigest()}

def list_history(directory, *, source):
    if source not in ('MOCK','BOARD'): raise ValueError('choose source explicitly')
    good,errors = [],[]
    for p in sorted(Path(directory).glob('*.csv')):
        try:
            snapshot=load_snapshot(p)
            if snapshot['metadata']['complete'] and snapshot['metadata']['source']==source:
                good.append({'path':str(p),'metadata':snapshot['metadata'],'sha256':snapshot['sha256']})
        except (ValueError,OSError,UnicodeError) as exc:
            errors.append({'path':str(p),'error':str(exc)})
    # No RTC/newest-slot assumption: caller supplies sequence or deliberate ordering policy.
    return {'items':good,'errors':errors,'order':'FILENAME_LEXICAL_NOT_RECENCY'}

def restore_snapshot(path, *, begin, write_row, finish):
    """Validate all CSV before display. begin can navigate first; finish only on success.
    Callbacks are application supplied; no physical actuators are permitted in display-only use.
    """
    snapshot=load_snapshot(path)
    meta=snapshot['metadata']
    if not meta['complete']: raise ValueError('partial snapshot not a complete history')
    begin(meta)
    for row in snapshot['records']: write_row(dict(row))
    finish(meta)
    return {'records_written':len(snapshot['records']), 'source':meta['source'],
            'sha256':snapshot['sha256'], 'hardware_verified':False}
