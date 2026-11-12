"""小さな QR コードエンコーダ（バイトモード・誤り訂正 M・バージョン 1〜10）"""

# (総コード語数, ブロックあたりの誤り訂正コード語数, [(ブロック数, データコード語数), ...])
_M = {
    1: (26, 10, [(1, 16)]), 2: (44, 16, [(1, 28)]), 3: (70, 26, [(1, 44)]), 4: (100, 18, [(2, 32)]),
    5: (134, 24, [(2, 43)]), 6: (172, 16, [(4, 27)]), 7: (196, 18, [(4, 31)]),
    8: (242, 22, [(2, 38), (2, 39)]), 9: (292, 22, [(3, 36), (2, 37)]), 10: (346, 26, [(4, 43), (1, 44)]),
}
_ALIGN = {1: [], 2: [6, 18], 3: [6, 22], 4: [6, 26], 5: [6, 30], 6: [6, 34], 7: [6, 22, 38],
          8: [6, 24, 42], 9: [6, 26, 46], 10: [6, 28, 50]}

_EXP = [0] * 512
_LOG = [0] * 256
_x = 1
for _i in range(255):
    _EXP[_i] = _x
    _LOG[_x] = _i
    _x <<= 1
    if _x & 0x100:
        _x ^= 0x11D
for _i in range(255, 512):
    _EXP[_i] = _EXP[_i - 255]


def _gmul(a, b):
    return 0 if a == 0 or b == 0 else _EXP[_LOG[a] + _LOG[b]]


def _rs_ec(data, n):
    gen = [1]
    for i in range(n):
        ng = [0] * (len(gen) + 1)
        for j, c in enumerate(gen):
            ng[j] ^= c
            ng[j + 1] ^= _gmul(c, _EXP[i])
        gen = ng
    rem = list(data) + [0] * n
    for i in range(len(data)):
        c = rem[i]
        if c:
            for j in range(1, len(gen)):
                rem[i + j] ^= _gmul(gen[j], c)
    return rem[len(data):]


def encode(text):
    data = text.encode('utf-8')
    for ver in range(1, 11):
        total, ecn, groups = _M[ver]
        cap = sum(b * d for b, d in groups)
        cc_bits = 8 if ver < 10 else 16
        if 4 + cc_bits + len(data) * 8 <= cap * 8:
            break
    else:
        raise ValueError('too long')
    bits = [0, 1, 0, 0] + [(len(data) >> i) & 1 for i in range(cc_bits - 1, -1, -1)]
    for b in data:
        bits += [(b >> i) & 1 for i in range(7, -1, -1)]
    bits += [0] * min(4, cap * 8 - len(bits))
    bits += [0] * ((8 - len(bits) % 8) % 8)
    cws = [int(''.join(map(str, bits[i:i + 8])), 2) for i in range(0, len(bits), 8)]
    pad, k = [0xEC, 0x11], 0
    while len(cws) < cap:
        cws.append(pad[k % 2])
        k += 1
    # ブロックに分けて誤り訂正
    blocks, k = [], 0
    for nb, nd in groups:
        for _ in range(nb):
            blocks.append(cws[k:k + nd])
            k += nd
    ecs = [_rs_ec(b, ecn) for b in blocks]
    final = []
    for i in range(max(len(b) for b in blocks)):
        for b in blocks:
            if i < len(b):
                final.append(b[i])
    for i in range(ecn):
        for e in ecs:
            final.append(e[i])
    assert len(final) == total
    return _build(ver, final)


def _build(ver, cw):
    size = ver * 4 + 17
    M = [[0] * size for _ in range(size)]
    F = [[False] * size for _ in range(size)]

    def setf(x, y, v):
        M[y][x] = 1 if v else 0
        F[y][x] = True

    # タイミングパターン
    for i in range(size):
        setf(6, i, i % 2 == 0)
        setf(i, 6, i % 2 == 0)
    # ファインダー
    for cx, cy in ((3, 3), (size - 4, 3), (3, size - 4)):
        for dy in range(-4, 5):
            for dx in range(-4, 5):
                x, y = cx + dx, cy + dy
                if 0 <= x < size and 0 <= y < size:
                    d = max(abs(dx), abs(dy))
                    setf(x, y, d not in (2, 4))
    # アライメント
    al = _ALIGN[ver]
    n = len(al)
    for i in range(n):
        for j in range(n):
            if (i == 0 and j == 0) or (i == 0 and j == n - 1) or (i == n - 1 and j == 0):
                continue
            for dy in range(-2, 3):
                for dx in range(-2, 3):
                    setf(al[i] + dx, al[j] + dy, max(abs(dx), abs(dy)) != 1)
    # 形式情報・型番情報の領域を予約
    _draw_format(M, F, setf, size, 0)
    if ver >= 7:
        _draw_version(setf, size, ver)
    # データ配置
    i = 0
    total_bits = len(cw) * 8
    right = size - 1
    while right >= 1:
        if right == 6:
            right = 5
        for vert in range(size):
            for j in range(2):
                x = right - j
                upward = ((right + 1) & 2) == 0
                y = size - 1 - vert if upward else vert
                if not F[y][x] and i < total_bits:
                    M[y][x] = (cw[i >> 3] >> (7 - (i & 7))) & 1
                    i += 1
        right -= 2
    # マスクを選ぶ
    best, best_pen = None, None
    for mask in range(8):
        T = [row[:] for row in M]
        _apply_mask(T, F, size, mask)

        def sf(x, y, v, T=T):
            T[y][x] = 1 if v else 0
        _draw_format(T, F, sf, size, mask)
        p = _penalty(T, size)
        if best_pen is None or p < best_pen:
            best, best_pen = T, p
    return best


def _draw_format(M, F, setf, size, mask):
    data = (0 << 3) | mask  # 誤り訂正 M = 0b00
    rem = data
    for _ in range(10):
        rem = (rem << 1) ^ ((rem >> 9) * 0x537)
    bits = ((data << 10) | rem) ^ 0x5412
    b = lambda i: (bits >> i) & 1
    for i in range(6):
        setf(8, i, b(i))
    setf(8, 7, b(6))
    setf(8, 8, b(7))
    setf(7, 8, b(8))
    for i in range(9, 15):
        setf(14 - i, 8, b(i))
    for i in range(8):
        setf(size - 1 - i, 8, b(i))
    for i in range(8, 15):
        setf(8, size - 15 + i, b(i))
    setf(8, size - 8, 1)


def _draw_version(setf, size, ver):
    rem = ver
    for _ in range(12):
        rem = (rem << 1) ^ ((rem >> 11) * 0x1F25)
    bits = (ver << 12) | rem
    for i in range(18):
        v = (bits >> i) & 1
        a, b = size - 11 + i % 3, i // 3
        setf(a, b, v)
        setf(b, a, v)


_MASKS = [
    lambda x, y: (x + y) % 2 == 0, lambda x, y: y % 2 == 0, lambda x, y: x % 3 == 0,
    lambda x, y: (x + y) % 3 == 0, lambda x, y: (x // 3 + y // 2) % 2 == 0,
    lambda x, y: x * y % 2 + x * y % 3 == 0, lambda x, y: (x * y % 2 + x * y % 3) % 2 == 0,
    lambda x, y: ((x + y) % 2 + x * y % 3) % 2 == 0,
]


def _apply_mask(T, F, size, mask):
    f = _MASKS[mask]
    for y in range(size):
        for x in range(size):
            if not F[y][x] and f(x, y):
                T[y][x] ^= 1


def _penalty(T, size):
    p = 0
    lines = [T[y] for y in range(size)] + [[T[y][x] for y in range(size)] for x in range(size)]
    pat1, pat2 = [1, 0, 1, 1, 1, 0, 1, 0, 0, 0, 0], [0, 0, 0, 0, 1, 0, 1, 1, 1, 0, 1]
    for ln in lines:
        run, prev = 0, -1
        for v in ln:
            if v == prev:
                run += 1
            else:
                if run >= 5:
                    p += 3 + run - 5
                run, prev = 1, v
        if run >= 5:
            p += 3 + run - 5
        for i in range(len(ln) - 10):
            seg = ln[i:i + 11]
            if seg == pat1 or seg == pat2:
                p += 40
    for y in range(size - 1):
        for x in range(size - 1):
            c = T[y][x]
            if c == T[y][x + 1] == T[y + 1][x] == T[y + 1][x + 1]:
                p += 3
    dark = sum(map(sum, T))
    p += 10 * (abs(dark * 20 - size * size * 10) // (size * size))
    return p
