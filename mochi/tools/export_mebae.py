"""んちょめちょぽ を glTF バイナリ (.glb) に書き出す。
ページ (index.html) の three.js での組み立てをそのまま numpy で再現している。
"""
import json, struct, sys, math
import numpy as np

# ---------------- 形のパラメータ（index.html と同じ） ----------------
A, B, C = 1.42, 1.15, 1.25
FLOOR, FLAT, SKIRT, DOME = -0.3, 0.3, 0.1, 0.05
INK = 0x5b3a2e
FILL = 0xf0c6a4
LEAF = 0xc5e3c8


def srgb_to_linear(c):
    c = np.asarray(c, dtype=np.float64)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def hex_lin(h):
    rgb = np.array([(h >> 16) & 255, (h >> 8) & 255, h & 255]) / 255.0
    return list(srgb_to_linear(rgb)) + [1.0]


# ---------------- three.js SphereGeometry ----------------
def sphere(ws, hs):
    verts, idx = [], []
    grid = []
    for iy in range(hs + 1):
        v = iy / hs
        row = []
        for ix in range(ws + 1):
            u = ix / ws
            x = -math.cos(u * 2 * math.pi) * math.sin(v * math.pi)
            y = math.cos(v * math.pi)
            z = math.sin(u * 2 * math.pi) * math.sin(v * math.pi)
            row.append(len(verts)); verts.append((x, y, z))
        grid.append(row)
    for iy in range(hs):
        for ix in range(ws):
            a, b = grid[iy][ix + 1], grid[iy][ix]
            c, d = grid[iy + 1][ix], grid[iy + 1][ix + 1]
            if iy != 0: idx.append((a, b, d))
            if iy != hs - 1: idx.append((b, c, d))
    return np.array(verts, dtype=np.float64), np.array(idx, dtype=np.int64)


def smooth_normals(P, F):
    """位置が同じ頂点（球の継ぎ目）はまとめて法線を平均 → 継ぎ目が出ない"""
    key = np.round(P, 5)
    _, inv = np.unique(key, axis=0, return_inverse=True)
    inv = inv.ravel()
    fn = np.cross(P[F[:, 1]] - P[F[:, 0]], P[F[:, 2]] - P[F[:, 0]])
    acc = np.zeros((inv.max() + 1, 3))
    for k in range(3):
        np.add.at(acc, inv[F[:, k]], fn)
    N = acc[inv]
    N /= np.linalg.norm(N, axis=1, keepdims=True) + 1e-12
    return N


# ---------------- 体 ----------------
def make_body():
    P, F = sphere(128, 96)
    out = P.copy()
    for i, (x, y, z) in enumerate(P):
        if y < FLOOR:
            d = FLOOR - y
            y = FLOOR - d * FLAT
            s = 1 + math.sin(min(d / (1 + FLOOR), 1) * math.pi * 0.5) * SKIRT
            x *= s; z *= s
        else:
            s = 1 + math.sin(((y - FLOOR) / (1 - FLOOR)) * math.pi) * DOME
            x *= s; z *= s
        out[i] = (x * A, y * B, z * C)
    fy = FLOOR * B - (1 + FLOOR) * B * FLAT
    # 色えんぴつっぽいグラデーション（ページと同じ式・リニア値）
    h = np.clip((out[:, 1] - fy) / 1.75, 0, 1)
    front = np.maximum(out[:, 2] / 1.25, 0)
    left = np.maximum(-out[:, 0] / 1.42, 0)
    t = np.clip(0.15 + h * 0.75 + front * 0.35 - left * 0.25, 0, 1)[:, None]
    col = np.array([0.66, 0.6, 0.53]) * (1 - t) + np.array([0.96, 0.945, 0.88]) * t
    return out, F, col, fy


BODY_P, BODY_F, BODY_C, FLOOR_Y = make_body()
BODY_N = smooth_normals(BODY_P, BODY_F)
T0, T1, T2 = BODY_P[BODY_F[:, 0]], BODY_P[BODY_F[:, 1]], BODY_P[BODY_F[:, 2]]
E1, E2 = T1 - T0, T2 - T0
FACE_N = np.cross(E1, E2); FACE_N /= np.linalg.norm(FACE_N, axis=1, keepdims=True) + 1e-12


def raycast(o, d):
    """Möller–Trumbore（全三角形をまとめて）。一番近い当たりの点と面法線"""
    o, d = np.asarray(o, float), np.asarray(d, float)
    p = np.cross(d, E2)
    det = np.einsum('ij,ij->i', E1, p)
    ok = np.abs(det) > 1e-12
    inv = np.where(ok, 1 / np.where(ok, det, 1), 0)
    tv = o - T0
    u = np.einsum('ij,ij->i', tv, p) * inv
    q = np.cross(tv, E1)
    v = (q @ d) * inv
    t = np.einsum('ij,ij->i', E2, q) * inv
    hit = ok & (u >= 0) & (v >= 0) & (u + v <= 1) & (t > 1e-9)
    if not hit.any():
        raise RuntimeError('ray missed body')
    t = np.where(hit, t, np.inf)
    k = int(np.argmin(t))
    n = FACE_N[k]
    if n @ d > 0: n = -n            # 外向き（three の face.normal と同じ向き）
    return o + d * t[k], n


def on_front(x, y, lift):
    p, n = raycast((x, y, 5), (0, 0, -1))
    return p + n * lift


# ---------------- CatmullRom（three と同じ centripetal）＋チューブ ----------------
def catmull(points, closed, n_samples):
    P = [np.asarray(p, float) for p in points]
    L = len(P)

    def point(t):
        pt = (L - (0 if closed else 1)) * t
        ip = int(math.floor(pt)); w = pt - ip
        if closed:
            ip += (0 if ip > 0 else (math.floor(abs(ip) / L) + 1) * L)
        elif w == 0 and ip == L - 1:
            ip = L - 2; w = 1
        if closed or ip > 0: p0 = P[(ip - 1) % L]
        else: p0 = P[0] - (P[1] - P[0])
        p1 = P[ip % L]; p2 = P[(ip + 1) % L]
        if closed or ip + 2 < L: p3 = P[(ip + 2) % L]
        else: p3 = P[L - 1] - (P[L - 2] - P[L - 1])
        def dist(a, b): return max(np.sum((a - b) ** 2) ** 0.25, 1e-4)
        dt0, dt1, dt2 = dist(p0, p1), dist(p1, p2), dist(p2, p3)
        if dt1 < 1e-4: dt1 = 1.0
        if dt0 < 1e-4: dt0 = dt1
        if dt2 < 1e-4: dt2 = dt1
        def init(x0, x1, x2, x3):
            t1 = ((x1 - x0) / dt0 - (x2 - x0) / (dt0 + dt1) + (x2 - x1) / dt1) * dt1
            t2 = ((x2 - x1) / dt1 - (x3 - x1) / (dt1 + dt2) + (x3 - x2) / dt2) * dt1
            c0, c1 = x1, t1
            c2 = -3 * x1 + 3 * x2 - 2 * t1 - t2
            c3 = 2 * x1 - 2 * x2 + t1 + t2
            return c0 + c1 * w + c2 * w * w + c3 * w * w * w
        return init(p0, p1, p2, p3)

    # 弧長で等間隔にサンプル（three の getPointAt と同じ考え方）
    dense = np.array([point(i / 2000) for i in range(2001)])
    seg = np.linalg.norm(np.diff(dense, axis=0), axis=1)
    cum = np.concatenate([[0], np.cumsum(seg)])
    target = np.linspace(0, cum[-1], n_samples + 1)
    out = np.empty((n_samples + 1, 3))
    for k in range(3):
        out[:, k] = np.interp(target, cum, dense[:, k])
    return out


def tube(path, r, radial, closed):
    n = len(path)
    if closed: path = path[:-1]; n -= 1
    T = np.zeros_like(path)
    for i in range(n):
        a = path[(i + 1) % n] if (closed or i + 1 < n) else path[i]
        b = path[(i - 1) % n] if (closed or i > 0) else path[i]
        T[i] = a - b
    T /= np.linalg.norm(T, axis=1, keepdims=True)
    # 平行移動フレーム（ねじれない）
    ref = np.array([0, 0, 1.0]) if abs(T[0][2]) < 0.9 else np.array([1.0, 0, 0])
    N = np.zeros_like(path); Bv = np.zeros_like(path)
    N[0] = np.cross(T[0], ref); N[0] /= np.linalg.norm(N[0])
    for i in range(1, n):
        v = N[i - 1] - T[i] * (N[i - 1] @ T[i])
        N[i] = v / np.linalg.norm(v)
    for i in range(n): Bv[i] = np.cross(T[i], N[i])
    verts, norms, idx = [], [], []
    for i in range(n):
        for j in range(radial):
            a = j / radial * 2 * math.pi
            nn = N[i] * math.cos(a) + Bv[i] * math.sin(a)
            verts.append(path[i] + nn * r); norms.append(nn)
    rings = n if closed else n - 1
    for i in range(rings):
        i2 = (i + 1) % n
        for j in range(radial):
            j2 = (j + 1) % radial
            a, b = i * radial + j, i2 * radial + j
            c, d = i2 * radial + j2, i * radial + j2
            idx += [(a, d, b), (b, d, c)]
    return np.array(verts), np.array(norms), np.array(idx)


def uv_sphere(r, ws=16, hs=12):
    P, F = sphere(ws, hs)
    return P * r, smooth_normals(P, F), F


def merge(parts):
    Ps, Ns, Fs, off = [], [], [], 0
    for P, N, F in parts:
        Ps.append(P); Ns.append(N); Fs.append(F + off); off += len(P)
    return np.vstack(Ps), np.vstack(Ns), np.vstack(Fs)


def stroke_on_face(pts2d, r, lift, closed=False, segs=None):
    L = max(lift, r * 0.8 + 0.014)
    pts = [on_front(x, y, L) for x, y in pts2d]
    path = catmull(pts, closed, segs or (80 if closed else 56))
    parts = [tube(path, r, 12, closed)]
    if not closed:
        for p in (pts[0], pts[-1]):
            P, N, F = uv_sphere(r, 12, 8)
            parts.append((P + p, N, F))
    return merge(parts)


# ---------------- 顔 ----------------
eyes, fills = [], []
for cx in (-0.43, 0.43):
    cy, rx, ry = 0.42, 0.095, 0.135
    ring = [(cx + math.cos(i / 40 * 2 * math.pi) * rx, cy + math.sin(i / 40 * 2 * math.pi) * ry) for i in range(40)]
    eyes.append(stroke_on_face(ring, 0.027, 0.034, closed=True))
    # 中の色：曲面に沿う、少しふくらんだ楕円
    RINGS, SEG = 10, 48
    dome = lambda k: 0.024 + 0.016 * math.sqrt(max(1 - k * k, 0))
    V = [on_front(cx, cy, dome(0))]
    for r in range(1, RINGS + 1):
        k = r / RINGS
        for i in range(SEG):
            a = i / SEG * 2 * math.pi
            V.append(on_front(cx + math.cos(a) * rx * k, cy + math.sin(a) * ry * k, dome(k)))
    Fi = []
    for i in range(SEG): Fi.append((0, 1 + i, 1 + (i + 1) % SEG))
    for r in range(1, RINGS):
        o0, o1 = 1 + (r - 1) * SEG, 1 + r * SEG
        for i in range(SEG):
            j = (i + 1) % SEG
            Fi += [(o0 + i, o1 + i, o1 + j), (o0 + i, o1 + j, o0 + j)]
    V, Fi = np.array(V), np.array(Fi)
    fills.append((V, smooth_normals(V, Fi), Fi))
mouth = stroke_on_face([(-0.055, 0.305), (0, 0.305), (0.055, 0.305)], 0.02, 0.018)
ink_face = merge(eyes + [mouth])
fill_face = merge(fills)

# ---------------- 芽 ----------------
top_p, _ = raycast((0, 5, 0.05), (0, -1, 0))
stem_path = catmull([(0, -0.08, 0), (0.01, 0.12, 0), (0, 0.3, 0)], False, 20)
sP, sN, sF = tube(stem_path, 0.032, 10, False)
cP, cN, cF = uv_sphere(0.032, 10, 8)
stem = merge([(sP, sN, sF), (cP + stem_path[-1], cN, cF)])


def leaf_geo(side):
    P, F = sphere(32, 20)
    P = P * np.array([0.3, 0.075, 0.2])
    P[:, 0] += side * 0.28
    return P, smooth_normals(P, F), F


def quat_z(a):
    return [0.0, 0.0, math.sin(a / 2), math.cos(a / 2)]


# ---------------- glTF 書き出し ----------------
class GLB:
    def __init__(self):
        self.bin = bytearray()
        self.j = {"asset": {"version": "2.0", "generator": "mochi-chara export"},
                  "extensionsUsed": ["KHR_materials_unlit"],
                  "buffers": [], "bufferViews": [], "accessors": [], "meshes": [],
                  "materials": [], "nodes": [], "scenes": [{"nodes": [0]}], "scene": 0}

    def _view(self, data, target):
        while len(self.bin) % 4: self.bin.append(0)
        off = len(self.bin); self.bin += data
        self.j["bufferViews"].append({"buffer": 0, "byteOffset": off, "byteLength": len(data), "target": target})
        return len(self.j["bufferViews"]) - 1

    def acc(self, arr, kind):
        if kind == 'idx':
            a = np.ascontiguousarray(arr, dtype=np.uint32).ravel()
            v = self._view(a.tobytes(), 34963)
            self.j["accessors"].append({"bufferView": v, "componentType": 5125, "count": int(a.size), "type": "SCALAR"})
        else:
            a = np.ascontiguousarray(arr, dtype=np.float32)
            v = self._view(a.tobytes(), 34962)
            d = {"bufferView": v, "componentType": 5126, "count": int(len(a)), "type": "VEC3"}
            if kind == 'pos':
                d["min"] = [float(x) for x in a.min(0)]; d["max"] = [float(x) for x in a.max(0)]
            self.j["accessors"].append(d)
        return len(self.j["accessors"]) - 1

    def material(self, name, rgba, unlit=False, double=False):
        m = {"name": name, "pbrMetallicRoughness": {"baseColorFactor": [float(x) for x in rgba], "metallicFactor": 0.0, "roughnessFactor": 1.0}}
        if unlit: m["extensions"] = {"KHR_materials_unlit": {}}
        if double: m["doubleSided"] = True
        self.j["materials"].append(m)
        return len(self.j["materials"]) - 1

    def mesh(self, name, P, N, F, mat, color=None):
        attrs = {"POSITION": self.acc(P, 'pos'), "NORMAL": self.acc(N, 'n')}
        if color is not None: attrs["COLOR_0"] = self.acc(color, 'c')
        self.j["meshes"].append({"name": name, "primitives": [{"attributes": attrs, "indices": self.acc(F, 'idx'), "material": mat}]})
        return len(self.j["meshes"]) - 1

    def node(self, name, mesh=None, children=None, t=None, r=None):
        n = {"name": name}
        if mesh is not None: n["mesh"] = mesh
        if children: n["children"] = children
        if t is not None: n["translation"] = [float(x) for x in t]
        if r is not None: n["rotation"] = [float(x) for x in r]
        self.j["nodes"].append(n)
        return len(self.j["nodes"]) - 1

    def save(self, path):
        self.j["buffers"] = [{"byteLength": len(self.bin)}]
        js = json.dumps(self.j, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        while len(js) % 4: js += b' '
        while len(self.bin) % 4: self.bin.append(0)
        total = 12 + 8 + len(js) + 8 + len(self.bin)
        with open(path, 'wb') as f:
            f.write(struct.pack('<III', 0x46546C67, 2, total))
            f.write(struct.pack('<II', len(js), 0x4E4F534A)); f.write(js)
            f.write(struct.pack('<II', len(self.bin), 0x004E4942)); f.write(self.bin)


def hull(P, N, F, th):
    """裏返しの殻（インバーテッドハル）＝ページと同じ輪郭線"""
    return P + N * th, -N, F[:, ::-1]


def build(path, outline):
    g = GLB()
    m_body = g.material("Body", [1, 1, 1, 1])
    m_ink = g.material("Ink", hex_lin(INK), unlit=True)
    m_fill = g.material("EyeFill", hex_lin(FILL), unlit=True, double=True)
    m_leaf = g.material("Leaf", hex_lin(LEAF))
    m_line = g.material("Outline", hex_lin(INK), unlit=True) if outline else None

    nodes = []
    b = g.mesh("Body", BODY_P, BODY_N, BODY_F, m_body, color=BODY_C)
    nodes.append(g.node("Body", b))
    if outline:
        nodes.append(g.node("Body_Outline", g.mesh("Body_Outline", *hull(BODY_P, BODY_N, BODY_F, 0.04), m_line)))
    face_kids = [g.node("Eyes_Mouth", g.mesh("Eyes_Mouth", *ink_face, m_ink)),
                 g.node("Eye_Fill", g.mesh("Eye_Fill", *fill_face, m_fill))]
    nodes.append(g.node("Face", children=face_kids))

    sprout_kids = [g.node("Stem", g.mesh("Stem", *stem, m_ink))]
    for side, nm in ((-1, "Leaf_L"), (1, "Leaf_R")):
        P, N, F = leaf_geo(side)
        kids = [g.node(nm + "_Mesh", g.mesh(nm, P, N, F, m_leaf))]
        if outline:
            kids.append(g.node(nm + "_Outline", g.mesh(nm + "_Outline", *hull(P, N, F, 0.028), m_line)))
        # 茎の先が支点：ここを回すとふたばがぱたぱたする
        sprout_kids.append(g.node(nm, children=kids, t=(0, 0.3, 0), r=quat_z(side * 0.28)))
    nodes.append(g.node("Sprout", children=sprout_kids, t=top_p))

    # ルート：床(y=0)の真ん中が原点
    root = {"name": "nchomechopo", "children": nodes, "translation": [0.0, float(-FLOOR_Y), 0.0]}
    g.j["nodes"].insert(0, root)
    # 挿入で番号がずれたのを直す
    for n in g.j["nodes"][1:]:
        if "children" in n: n["children"] = [c + 1 for c in n["children"]]
    root["children"] = [c + 1 for c in root["children"]]
    g.save(path)


if __name__ == '__main__':
    build(sys.argv[1], outline=False)
    build(sys.argv[2], outline=True)
    print('floorY', FLOOR_Y, 'top', top_p)
