"""Read-only source hash comparison. Does not discover Vivado's selected sources."""
import argparse, hashlib, json
from pathlib import Path

def audit_sources(paths):
    if len(paths) < 2:
        raise ValueError('provide at least two explicit source files')
    entries = []
    for path in paths:
        p = Path(path).resolve(strict=True)
        if not p.is_file():
            raise ValueError('source must be a file')
        entries.append({'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()})
    if len({e['path'] for e in entries}) != len(entries):
        raise ValueError('duplicate source path')
    return {'passed': len({e['sha256'] for e in entries}) == 1,
            'evidence': 'FILE_IDENTITY_ONLY', 'hardware_verified': False, 'sources': entries}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('sources', nargs='+')
    report = audit_sources(parser.parse_args().sources)
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report['passed'] else 1)
