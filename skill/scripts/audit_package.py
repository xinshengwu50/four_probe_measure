"""Read-only integrity, syntax, notebook and local Markdown-link audit. No hardware."""
import ast,hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def audit():
    checked=set()
    for line in (ROOT/'checksums.sha256').read_text(encoding='utf-8').splitlines():
        digest,name=line.split('  ',1)
        p=(ROOT/name).resolve()
        try:
            p.relative_to(ROOT.resolve())
        except ValueError:
            raise ValueError('invalid manifest path')
        if p in checked:
            raise ValueError('invalid manifest path')
        checked.add(p)
        if hashlib.sha256(p.read_bytes()).hexdigest()!=digest:raise ValueError('hash mismatch '+name)
    actual={p.resolve() for p in ROOT.rglob('*') if p.is_file() and p.name!='checksums.sha256' and '__pycache__' not in p.parts}
    if checked!=actual:raise ValueError('manifest coverage mismatch')
    cells=0
    for p in ROOT.rglob('*.py'):ast.parse(p.read_text(encoding='utf-8-sig'),filename=str(p))
    for p in ROOT.rglob('*.ipynb'):
        nb=json.loads(p.read_text(encoding='utf-8'))
        for cell in nb['cells']:
            if cell['cell_type']=='code':
                ast.parse(''.join(cell['source']));cells+=1
                if cell.get('outputs') or cell.get('execution_count') is not None:raise ValueError('notebook outputs must be cleared')
    skills=list(ROOT.rglob('SKILL.md'))
    for p in skills:
        s=p.read_text(encoding='utf-8')
        if not re.match(r'^---\nname: [a-z0-9-]+\ndescription: .+\n---',s):raise ValueError('invalid skill frontmatter '+str(p))
    links=0
    for p in ROOT.rglob('*.md'):
        for link in re.findall(r'\[[^\]]*\]\(([^)]+)\)',p.read_text(encoding='utf-8')):
            link=link.strip('<>')
            if ':' in link or link.startswith('#'):continue
            path=link.split('#',1)[0]
            if path and not (p.parent/path).exists():raise ValueError('broken link '+str(p)+' -> '+link)
            links+=1
    print(f'PASS_PACKAGE: {len(checked)} hashes, {len(skills)} skills, {cells} code cells, {links} local links; no hardware')

if __name__=='__main__':audit()
