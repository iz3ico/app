"""トップと各ゲームの QR コード画像（下にタイトル）をつくる。  python3 tools/make_qr.py"""
import pathlib, sys
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from qr import encode

root = pathlib.Path(__file__).resolve().parent.parent
out = root / 'qr'
out.mkdir(exist_ok=True)
ITEMS = [  # (ファイル名, タイトル, 小見出し, URL, アクセント色)
    ('top',       'あそびば',     'トップ',      'https://iz3ico.github.io/app/', (159, 198, 255)),
    ('bokyaku',   '忘却の都市',   'さんぽ',      'https://iz3ico.github.io/app/bokyaku/', (127, 195, 255)),
    ('hoshiyomi', '星詠みガチャ', 'ガチャ',      'https://iz3ico.github.io/app/hoshiyomi/', (242, 196, 106)),
]
SERIF = '/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc'
SANS = '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
INK = (16, 26, 52)

def card(title, sub, url, accent, W=720):
    m = encode(url)
    n = len(m)
    quiet = 4
    mod = (W - 120) // (n + quiet * 2)
    qs = mod * (n + quiet * 2)
    H = 60 + qs + 190
    im = Image.new('RGB', (W, H), (255, 255, 255))
    d = ImageDraw.Draw(im)
    ox, oy = (W - qs) // 2, 60
    for y in range(n):
        for x in range(n):
            if m[y][x]:
                d.rectangle([ox + (x + quiet) * mod, oy + (y + quiet) * mod,
                             ox + (x + quiet + 1) * mod - 1, oy + (y + quiet + 1) * mod - 1], fill=INK)
    ty = oy + qs + 18
    f_sub = ImageFont.truetype(SANS, 22, index=0)
    f_ttl = ImageFont.truetype(SERIF, 54, index=0)
    sw = d.textlength(sub, font=f_sub)
    d.rounded_rectangle([(W - sw) / 2 - 18, ty, (W + sw) / 2 + 18, ty + 36], radius=18, fill=accent)
    d.text((W / 2, ty + 18), sub, font=f_sub, fill=INK, anchor='mm')
    # 字間をあけてタイトル
    sp = 10
    widths = [d.textlength(ch, font=f_ttl) for ch in title]
    tw = sum(widths) + sp * (len(title) - 1)
    x = (W - tw) / 2
    for ch, w in zip(title, widths):
        d.text((x, ty + 60), ch, font=f_ttl, fill=INK)
        x += w + sp
    d.rectangle([0, H - 8, W, H], fill=accent)
    return im

cards = []
for fn, title, sub, url, acc in ITEMS:
    im = card(title, sub, url, acc)
    im.save(out / f'qr_{fn}.png')
    cards.append(im)
# まとめて 1 枚（印刷用）
gap = 40
cw, ch = cards[0].size
sheet = Image.new('RGB', (cw * len(cards) + gap * (len(cards) + 1), ch + gap * 2), (235, 239, 247))
for i, im in enumerate(cards):
    sheet.paste(im, (gap + i * (cw + gap), gap))
sheet.save(out / 'qr_all.png')
print('ok', [c.size for c in cards[:1]], sheet.size)
