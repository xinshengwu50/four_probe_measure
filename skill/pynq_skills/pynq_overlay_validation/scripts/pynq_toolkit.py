"""Dependency-free offline toolkit; PYNQ imports only for explicit board loading."""
import argparse
import hashlib
import json
import math
import platform
from pathlib import Path
import re
import time
import xml.etree.ElementTree as ET


def integer(value):
    if isinstance(value,bool):raise ValueError('boolean is not an integer')
    return int(value,0) if isinstance(value,str) else int(value) if isinstance(value,int) else _bad('integer required')


def _bad(message):raise ValueError(message)


def validate_contract(c):
    if type(c.get('schema_version')) is not int or c.get('schema_version')!=1:raise ValueError('unsupported contract schema')
    ip=c['ip'];name=ip['instance']
    if not isinstance(name,str) or not re.fullmatch(r'[a-zA-Z_][a-zA-Z0-9_/]*',name):raise ValueError('invalid IP instance')
    size=integer(ip['addr_range'])
    if size<4 or size%4:raise ValueError('invalid IP range')
    if 'phys_addr' in ip and (integer(ip['phys_addr'])<0 or integer(ip['phys_addr'])%4):raise ValueError('invalid base address')
    if not isinstance(c['registers'],dict) or not c['registers']:raise ValueError('registers required')
    offsets=set()
    for name,r in c['registers'].items():
        if not re.fullmatch(r'[a-z][a-z0-9_]*',name):raise ValueError('invalid register name')
        off=integer(r['offset'])
        if off<0 or off%4 or off+4>size or off in offsets:raise ValueError('overlapping/unaligned/out-of-range register')
        offsets.add(off)
        if r.get('width',32)!=32:raise ValueError('only32bit AXI registers supported')
        if r['access'] not in ('ro','rw','wo'):raise ValueError('invalid access')
        if r.get('read_effect','none') not in ('none','clear','pop'):raise ValueError('invalid read effect')
        if r.get('write_effect','none') not in ('none','pulse','w1c','command'):raise ValueError('invalid write effect')
        if not isinstance(r.get('signed',False),bool) or not isinstance(r.get('dangerous',False),bool):raise ValueError('invalid boolean')
        scale=r.get('scale',1)
        if isinstance(scale,bool) or not isinstance(scale,(int,float)) or not math.isfinite(scale) or scale<=0:raise ValueError('invalid scale')
        if 'expected' in r:
            if r['access']=='wo' or r.get('read_effect','none')!='none':raise ValueError('expected must be safe read')
            integer(r['expected'])
    return c


def load_contract(path):return validate_contract(json.loads(Path(path).read_text(encoding='utf-8')))


class MemoryTransport:
    """MOCK transport, not an FPGA simulation."""
    def __init__(self,values=None):self.values=dict(values or {});self.writes=[]
    def read(self,offset):return self.values.get(offset,0)
    def write(self,offset,value):self.writes.append((offset,value));self.values[offset]=value


class RegisterClient:
    def __init__(self,contract,transport,allow_writes=False):
        import copy
        self.contract=validate_contract(copy.deepcopy(contract));self.transport=transport;self.allow_writes=bool(allow_writes)
    def read(self,name,allow_side_effect=False):
        r=self.contract['registers'][name]
        if r['access']=='wo':raise PermissionError('write-only register')
        if r.get('read_effect','none')!='none' and not allow_side_effect:raise PermissionError('destructive read requires opt-in')
        value=integer(self.transport.read(integer(r['offset'])))&0xffffffff
        return value-(1<<32) if r.get('signed',False) and value&(1<<31) else value
    def read_scaled(self,name):return self.read(name)*self.contract['registers'][name].get('scale',1)
    def write(self,name,value,allow_side_effect=False):
        r=self.contract['registers'][name]
        if not self.allow_writes or r['access']=='ro':raise PermissionError('write not authorized')
        if (r.get('dangerous',False) or r.get('write_effect','none')!='none') and not allow_side_effect:
            raise PermissionError('command/side effect requires explicit opt-in')
        value=integer(value);lo=-(1<<31) if r.get('signed',False) else 0;hi=(1<<31)-1 if r.get('signed',False) else 0xffffffff
        if not lo<=value<=hi:raise ValueError('value outside register width')
        self.transport.write(integer(r['offset']),value&0xffffffff)
    def wait(self,name,mask,expected,timeout_s=1.,poll_s=.001):
        if not all(math.isfinite(v) and v>0 for v in (timeout_s,poll_s)):raise ValueError('invalid wait timing')
        mask=integer(mask);expected=integer(expected)
        if not 0<=mask<=0xffffffff or expected&~mask:raise ValueError('invalid mask/expected')
        deadline=time.monotonic()+timeout_s
        while True:
            value=self.read(name)
            if value&mask==expected:return value
            if time.monotonic()>=deadline:raise TimeoutError('register wait timeout: '+name)
            time.sleep(min(poll_s,max(0,deadline-time.monotonic())))


def verify_versions(client):
    checked=[]
    for name,r in client.contract['registers'].items():
        if 'expected' in r:
            actual=client.read(name)
            if actual!=integer(r['expected']):raise ValueError('identity mismatch '+name+': '+str(actual))
            checked.append(name)
    return checked


def check_ip_dict(c,info):
    validate_contract(c);want=c['ip'];actual=info.get(want['instance'])
    if actual is None:raise ValueError('expected IP not loaded')
    base=integer(actual['phys_addr']);size=integer(actual['addr_range'])
    if 'phys_addr' in want and base!=integer(want['phys_addr']):raise ValueError('IP address mismatch')
    if size<integer(want['addr_range']):raise ValueError('IP register range too small')
    if 'vlnv' in want and actual.get('type')!=want['vlnv']:raise ValueError('IP VLNV mismatch')
    return actual


def sha256(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def make_manifest(bit,output,board):
    bit=Path(bit);hwh=bit.with_suffix('.hwh')
    if not board:raise ValueError('declare target board')
    if not bit.is_file() or not hwh.is_file():raise FileNotFoundError('matching bit/hwh required')
    if Path(output).resolve() in (bit.resolve(),hwh.resolve()):raise ValueError('manifest must not overwrite bit/hwh')
    data=dict(schema_version=1,board=board,bit_name=bit.name,hwh_name=hwh.name,
              bit_sha256=sha256(bit),hwh_sha256=sha256(hwh))
    Path(output).write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8');return data


def check_bundle(bit,manifest):
    bit=Path(bit);hwh=bit.with_suffix('.hwh')
    if not bit.is_file() or not hwh.is_file():raise FileNotFoundError('bit/hwh pair missing')
    m=json.loads(Path(manifest).read_text(encoding='utf-8'))
    if m.get('schema_version')!=1 or not m.get('board'):raise ValueError('invalid manifest')
    for p,key in [(bit,'bit'),(hwh,'hwh')]:
        if p.name!=m[key+'_name'] or sha256(p)!=m[key+'_sha256']:raise ValueError('release hash/name mismatch: '+key)
    return m


def read_hwh(path):
    data=Path(path).read_bytes()
    if len(data)>16*1024*1024 or b'<!DOCTYPE' in data or b'<!ENTITY' in data:raise ValueError('unsupported/unsafe XML')
    root=ET.fromstring(data);info={}
    for module in root.iter('MODULE'):
        name=module.get('INSTANCE');vlnv=module.get('VLNV')
        if name:info[name]={'type':vlnv}
    for region in root.iter('MEMRANGE'):
        name=region.get('INSTANCE');base=region.get('BASEVALUE');high=region.get('HIGHVALUE')
        if name and base is not None and high is not None:
            value=dict(phys_addr=integer(base),addr_range=integer(high)-integer(base)+1)
            if name in info:info[name].update(value)
            else:info[name]=value
    return info


def load_board(bit,manifest,contract,*,download=False,safety_confirmed=False,actual_board=None):
    release=check_bundle(bit,manifest);validate_contract(contract)
    if actual_board!=release['board']:raise ValueError('explicit actual_board must match release target')
    check_ip_dict(contract,read_hwh(Path(bit).with_suffix('.hwh')))
    # This API deliberately refuses unsafe reconfiguration and no-download stale state.
    if not download or not safety_confirmed:raise PermissionError('board loading requires download and safety_confirmed')
    from pynq import Overlay
    overlay=Overlay(str(bit),download=True)
    if not overlay.is_loaded():raise ValueError('overlay not loaded')
    check_ip_dict(contract,overlay.ip_dict)
    client=RegisterClient(contract,_resolve_ip(overlay,contract['ip']['instance']))
    checked=verify_versions(client)
    return overlay,client,checked


def _resolve_ip(overlay,name):
    obj=overlay
    for part in name.split('/'):obj=getattr(obj,part)
    return obj


def compare(actual,expected,atol=0.,rtol=0.):
    for v in (atol,rtol):
        if not math.isfinite(v) or v<0:raise ValueError('invalid tolerance')
    a=list(actual);e=list(expected)
    if len(a)!=len(e):return dict(passed=False,reason='length mismatch',count=len(a))
    errors=[];fail=[]
    for i,(x,y) in enumerate(zip(a,e)):
        x=float(x);y=float(y)
        if not math.isfinite(x) or not math.isfinite(y):fail.append(i);continue
        error=abs(x-y);errors.append(error)
        if error>atol+rtol*abs(y):fail.append(i)
    return dict(passed=bool(a) and not fail,count=len(a),failed_indices=fail,
                max_abs_error=max(errors) if errors else None,atol=atol,rtol=rtol)


def parse_vivado(text):
    out=dict(wns_ns=None,whs_ns=None,lut=None,ff=None,dsp=None,bram=None)
    lines=text.splitlines()
    for i,line in enumerate(lines):
        if 'WNS(ns)' in line and 'WHS(ns)' in line:
            whs_index=4 if 'TNS Failing Endpoints' in line and 'TNS Total Endpoints' in line else 2 if line.split()==['WNS(ns)','TNS(ns)','WHS(ns)'] else None
            if whs_index is None:continue
            for candidate in lines[i+1:i+5]:
                tokens=candidate.split()
                try:values=[float(v) for v in tokens]
                except ValueError:continue
                if len(values)>whs_index:
                    out['wns_ns']=values[0];out['whs_ns']=values[whs_index];break
    for key,label in [('lut','Slice LUTs'),('ff','Slice Registers'),('dsp','DSPs'),('bram','Block RAM Tile')]:
        m=re.search(r'\|\s*'+re.escape(label)+r'\s*\|\s*([0-9.]+)',text)
        if m:out[key]=float(m.group(1)) if '.' in m.group(1) else int(m.group(1))
    return out


def validation_report(kind,contract,comparison,metrics,board_evidence=None):
    if kind not in ('MOCK','SIMULATION','BOARD'):raise ValueError('invalid evidence kind')
    if kind=='BOARD' and not board_evidence:raise ValueError('BOARD label requires actual board evidence')
    return dict(schema_version=1,evidence_kind=kind,hardware_verified=kind=='BOARD',board_evidence=board_evidence,
                ip=contract['ip']['instance'],python=platform.python_version(),platform=platform.platform(),
                correctness=comparison,metrics=metrics,
                note='Evidence label is supplied by caller; BOARD requires preserved actual board output.')


def generate_driver(c):
    validate_contract(c)
    code='from pynq_toolkit import RegisterClient\nCONTRACT = '+repr(c)+'\nclass Driver(RegisterClient):\n    def __init__(self,transport,allow_writes=False):\n        super().__init__(CONTRACT,transport,allow_writes=allow_writes)\n'
    for name,r in c['registers'].items():
        if r['access']!='wo':code+='    def read_'+name+'(self):\n        return self.read('+repr(name)+')\n'
        if r['access']!='ro':code+='    def write_'+name+'(self,value,allow_side_effect=False):\n        return self.write('+repr(name)+',value,allow_side_effect=allow_side_effect)\n'
    return code


def main():
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='command',required=True)
    m=s.add_parser('manifest');m.add_argument('bit');m.add_argument('output');m.add_argument('--board',required=True)
    a=s.add_parser('audit');a.add_argument('bit');a.add_argument('manifest');a.add_argument('contract')
    g=s.add_parser('generate');g.add_argument('contract');g.add_argument('output')
    v=s.add_parser('compare');v.add_argument('data');v.add_argument('output');v.add_argument('--atol',type=float,default=0);v.add_argument('--rtol',type=float,default=0)
    args=p.parse_args()
    if args.command=='manifest':print(json.dumps(make_manifest(args.bit,args.output,args.board),indent=2))
    elif args.command=='audit':
        release=check_bundle(args.bit,args.manifest);check_ip_dict(load_contract(args.contract),read_hwh(Path(args.bit).with_suffix('.hwh')))
        print(json.dumps(dict(status='PASS_OFFLINE_METADATA',board=release['board'],hardware_verified=False)))
    elif args.command=='generate':Path(args.output).write_text(generate_driver(load_contract(args.contract)),encoding='utf-8')
    elif args.command=='compare':
        data=json.loads(Path(args.data).read_text());result=compare(data['actual'],data['expected'],args.atol,args.rtol)
        Path(args.output).write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
        if not result['passed']:raise SystemExit(1)
if __name__=='__main__':main()
