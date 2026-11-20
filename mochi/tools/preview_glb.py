"""書き出した .glb を読み直して、ソフトウェアで描画して確認する（ファイルの中身の検証も兼ねる）"""
import json, struct, sys, math
import numpy as np
from PIL import Image, ImageDraw


def load(path):
    b = open(path, 'rb').read()
    magic, ver, total = struct.unpack('<III', b[:12])
    assert magic == 0x46546C67 and ver == 2 and total == len(b), 'header'
    jl, jt = struct.unpack('<II', b[12:20]); assert jt == 0x4E4F534A
    j = json.loads(b[20:20 + jl])
    o = 20 + jl
    bl, bt = struct.unpack('<II', b[o:o + 8]); assert bt == 0x004E4942
    binb = b[o + 8:o + 8 + bl]
    assert j['buffers'][0]['byteLength'] <= len(binb)

    def acc(i):
        a = j['accessors'][i]; v = j['bufferViews'][a['bufferView']]
        start = v.get('byteOffset', 0) + a.get('byteOffset', 0)
        assert start % 4 == 0
        if a['componentType'] == 5126:
            n = {'VEC3': 3, 'SCALAR': 1}[a['type']]
            arr = np.frombuffer(binb, np.float32, a['count'] * n, start).reshape(-1, n)
            if 'min' in a:
                assert np.allclose(arr.min(0), a['min'], atol=1e-5) and np.allclose(arr.max(0), a['max'], atol=1e-5), 'minmax'
            return arr
        return np.frombuffer(binb, np.uint32, a['count'], start)
    return j, acc


def qmat(q):
    x, y, z, w = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def gather(j, acc):
    tris = []
    def walk(ni, R, T):
        n = j['nodes'][ni]
        r = qmat(n.get('rotation', [0, 0, 0, 1])); t = np.array(n.get('translation', [0, 0, 0]))
        R2, T2 = R @ r, R @ t + T
        if 'mesh' in n:
            for p in j['meshes'][n['mesh']]['primitives']:
                P = acc(p['attributes']['POSITION']) @ R2.T + T2
                N = acc(p['attributes']['NORMAL']) @ R2.T
                C = acc(p['attributes']['COLOR_0']) if 'COLOR_0' in p['attributes'] else None
                F = acc(p['indices']).reshape(-1, 3)
                assert F.max() < len(P), 'index range'
                m = j['materials'][p['material']]
                tris.append((P, N, C, F, m))
        for c in n.get('children', []): walk(c, R2, T2)
    for ni in j['scenes'][0]['nodes']: walk(ni, np.eye(3), np.zeros(3))
    return tris


def lin2srgb(c):
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


def render(path, out, yaw_deg=25, elev_deg=14, size=640):
    j, acc = load(path)
    tris = gather(j, acc)
    yaw, el = math.radians(yaw_deg), math.radians(elev_deg)
    fwd = np.array([math.sin(yaw) * math.cos(el), math.sin(el), math.cos(yaw) * math.cos(el)])  # 視点方向（カメラ位置向き）
    right = np.cross([0, 1, 0], fwd); right /= np.linalg.norm(right)
    up = np.cross(fwd, right)
    light = np.array([0.45, 0.8, 0.6]); light /= np.linalg.norm(light)
    polys = []
    for P, N, C, F, m in tris:
        base = np.array(m['pbrMetallicRoughness']['baseColorFactor'][:3])
        unlit = 'extensions' in m
        double = m.get('doubleSided', False)
        v0, v1, v2 = P[F[:, 0]], P[F[:, 1]], P[F[:, 2]]
        fn = np.cross(v1 - v0, v2 - v0)
        facing = fn @ fwd
        keep = facing > 0 if not double else np.ones(len(F), bool)
        cen = (v0 + v1 + v2) / 3
        depth = cen @ fwd
        nrm = N[F].mean(1)
        nrm /= np.linalg.norm(nrm, axis=1, keepdims=True) + 1e-9
        if C is not None: col = C[F].mean(1) * base
        else: col = np.tile(base, (len(F), 1))
        if not unlit:
            shade = 0.55 + 0.45 * np.clip(nrm @ light, 0, 1)
            col = col * shade[:, None]
        rgb = (lin2srgb(col) * 255).astype(int)
        for k in np.nonzero(keep)[0]:
            pts = [(float(p @ right), float(p @ up)) for p in (v0[k], v1[k], v2[k])]
            polys.append((depth[k], pts, tuple(rgb[k])))
    polys.sort(key=lambda x: x[0])
    allp = np.array([p for _, ps, _ in polys for p in ps])
    lo, hi = allp.min(0), allp.max(0)
    sc = size * 0.86 / (hi - lo).max()
    ctr = (lo + hi) / 2
    im = Image.new('RGB', (size, size), (238, 236, 228))
    d = ImageDraw.Draw(im)
    for _, ps, c in polys:
        q = [((x - ctr[0]) * sc + size / 2, size / 2 - (y - ctr[1]) * sc) for x, y in ps]
        d.polygon(q, fill=c)
    im.save(out)
    return j


if __name__ == '__main__':
    j = render(sys.argv[1], sys.argv[2], float(sys.argv[3]) if len(sys.argv) > 3 else 25)
    print('nodes', len(j['nodes']), 'meshes', len(j['meshes']), 'materials', [m['name'] for m in j['materials']])
