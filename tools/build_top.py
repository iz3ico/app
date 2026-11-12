"""top_template.html の __THUMB_<id>__ を assets/<id>.jpg の data URI に置きかえて index.html をつくる"""
import base64, re, pathlib
root = pathlib.Path(__file__).resolve().parent.parent
s = (root / 'top_template.html').read_text(encoding='utf-8')
def sub(m):
    p = root / 'assets' / f'{m.group(1)}.jpg'
    return 'data:image/jpeg;base64,' + base64.b64encode(p.read_bytes()).decode() if p.exists() else ''
(root / 'index.html').write_text(re.sub(r'__THUMB_([a-z0-9_-]+)__', sub, s), encoding='utf-8')
print('index.html built')
