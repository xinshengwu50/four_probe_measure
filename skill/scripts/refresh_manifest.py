"""Refresh the package checksum inventory, not a trusted signing operation."""
from pathlib import Path
import hashlib
ROOT=Path(__file__).resolve().parents[1]
if __name__=='__main__':
    lines=[]
    for p in sorted(ROOT.rglob('*')):
        if p.is_file() and p.name!='checksums.sha256' and '__pycache__' not in p.parts:
            lines.append(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.relative_to(ROOT).as_posix())
    (ROOT/'checksums.sha256').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('MANIFEST_REFRESHED',len(lines),'files; hashes are not signatures')
