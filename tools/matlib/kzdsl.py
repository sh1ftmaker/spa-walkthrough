"""Tiny node-building DSL for Blender shader node trees (Kazan-yu material library).

    b = B(node_tree)
    n = b.noise4(t, scale=6, detail=8)      # S wrappers around sockets
    h = (n * 0.6 + 0.2).clamp()
    col = b.ramp(h, [(0, (0.02,)*3), (1, (0.08,)*3)])

Every float operator creates a Math node; colours/vectors go through b.mixc / b.vmath.
Node locations are laid out by dependency depth so the trees stay readable in the UI.
"""
import math
import bpy

TAU = 2.0 * math.pi


class S:
    """A node output socket plus the builder that owns it."""

    def __init__(self, b, sock, depth=0):
        self.b, self.sock, self.depth = b, sock, depth

    # float arithmetic -------------------------------------------------
    def _m(self, op, o=None, rev=False):
        a, c = (o, self) if rev else (self, o)
        return self.b.math(op, a, c)

    def __add__(self, o): return self._m('ADD', o)
    def __radd__(self, o): return self._m('ADD', o, True)
    def __sub__(self, o): return self._m('SUBTRACT', o)
    def __rsub__(self, o): return self._m('SUBTRACT', o, True)
    def __mul__(self, o): return self._m('MULTIPLY', o)
    def __rmul__(self, o): return self._m('MULTIPLY', o, True)
    def __truediv__(self, o): return self._m('DIVIDE', o)
    def __rtruediv__(self, o): return self._m('DIVIDE', o, True)
    def __pow__(self, o): return self._m('POWER', o)
    def __neg__(self): return self.b.math('MULTIPLY', self, -1.0)

    def clamp(self): return self.b.math('ADD', self, 0.0, clamp=True)
    def abs(self): return self.b.math('ABSOLUTE', self)
    def fract(self): return self.b.math('FRACT', self)
    def floor(self): return self.b.math('FLOOR', self)
    def sin(self): return self.b.math('SINE', self)
    def cos(self): return self.b.math('COSINE', self)
    def sqrt(self): return self.b.math('SQRT', self)
    def min(self, o): return self.b.math('MINIMUM', self, o)
    def max(self, o): return self.b.math('MAXIMUM', self, o)
    def mod(self, o): return self.b.math('FLOORED_MODULO', self, o)

    def smooth(self, lo, hi):
        """smoothstep(lo, hi, x) in [0,1]."""
        return self.b.maprange(self, lo, hi, 0.0, 1.0, interp='SMOOTHSTEP')

    def lin(self, lo, hi, a=0.0, c=1.0, clamp=True):
        return self.b.maprange(self, lo, hi, a, c, clamp=clamp)


class B:
    def __init__(self, nt):
        self.nt = nt
        self.cols = {}

    # infrastructure ---------------------------------------------------
    def _place(self, node, depth):
        y = self.cols.get(depth, 0)
        node.location = (depth * 220.0, -y)
        self.cols[depth] = y + node.dimensions[1] + 180.0 if node.dimensions[1] else y + 220.0

    def node(self, typ, inputs=None, props=None, label=None, name=None):
        n = self.nt.nodes.new(typ)
        for k, v in (props or {}).items():
            setattr(n, k, v)
        depth = 0
        for key, val in (inputs or {}).items():
            d = self.set_in(n, key, val)
            depth = max(depth, d)
        self._place(n, depth + 1)
        n['_depth'] = depth + 1
        if label:
            n.label = label
        if name:
            n.name = name
        return n

    def _sock(self, n, key, out=False):
        coll = n.outputs if out else n.inputs
        if isinstance(key, int):
            return coll[key]
        for s in coll:  # identifier first (Mix node has duplicate names)
            if s.identifier == key and s.enabled:
                return s
        for s in coll:
            if s.name == key and s.enabled:
                return s
        for s in coll:
            if s.identifier == key or s.name == key:
                return s
        raise KeyError(f"{n.bl_idname} has no {'output' if out else 'input'} {key!r}")

    def set_in(self, n, key, val):
        s = self._sock(n, key)
        if isinstance(val, S):
            self.nt.links.new(val.sock, s)
            return val.depth
        if isinstance(val, bpy.types.NodeSocket):
            self.nt.links.new(val, s)
            return int(val.node.get('_depth', 0))
        if isinstance(val, (tuple, list)):
            v = list(val)
            n_expected = len(s.default_value)
            if len(v) == 3 and n_expected == 4:
                v = v + [1.0]
            s.default_value = v
        else:
            s.default_value = val
        return 0

    def out(self, n, key=0):
        return S(self, self._sock(n, key, out=True), int(n.get('_depth', 1)))

    # math ---------------------------------------------------------------
    def math(self, op, a, c=None, d=None, clamp=False):
        ins = {0: a}
        if c is not None:
            ins[1] = c
        if d is not None:
            ins[2] = d
        n = self.node('ShaderNodeMath', ins, {'operation': op, 'use_clamp': clamp})
        return self.out(n, 0)

    def maprange(self, x, a, b, c, d, interp='LINEAR', clamp=True):
        n = self.node('ShaderNodeMapRange', {'Value': x, 1: a, 2: b, 3: c, 4: d},
                      {'interpolation_type': interp, 'clamp': clamp, 'data_type': 'FLOAT'})
        return self.out(n, 'Result')

    def mixf(self, f, a, c):
        n = self.node('ShaderNodeMix', {'Factor_Float': f, 'A_Float': a, 'B_Float': c},
                      {'data_type': 'FLOAT', 'clamp_factor': True})
        return self.out(n, 'Result_Float')

    def mixc(self, f, a, c, blend='MIX'):
        n = self.node('ShaderNodeMix', {'Factor_Float': f, 'A_Color': a, 'B_Color': c},
                      {'data_type': 'RGBA', 'blend_type': blend, 'clamp_factor': True})
        return self.out(n, 'Result_Color')

    def cmul(self, c, f):
        """colour * scalar (or colour * colour) via vector math."""
        if isinstance(f, (int, float)):
            n = self.node('ShaderNodeVectorMath', {0: c, 'Scale': f}, {'operation': 'SCALE'})
        elif isinstance(f, S) and f.sock.type == 'VALUE':
            n = self.node('ShaderNodeVectorMath', {0: c, 'Scale': f}, {'operation': 'SCALE'})
        else:
            n = self.node('ShaderNodeVectorMath', {0: c, 1: f}, {'operation': 'MULTIPLY'})
        return self.out(n, 'Vector')

    def cadd(self, c, d):
        n = self.node('ShaderNodeVectorMath', {0: c, 1: d}, {'operation': 'ADD'})
        return self.out(n, 'Vector')

    def vmath(self, op, a, c=None, out='Vector'):
        ins = {0: a}
        if c is not None:
            ins[1] = c
        n = self.node('ShaderNodeVectorMath', ins, {'operation': op})
        return self.out(n, out)

    def xyz(self, x, y, z):
        return self.out(self.node('ShaderNodeCombineXYZ', {0: x, 1: y, 2: z}), 0)

    def sep(self, v):
        n = self.node('ShaderNodeSeparateXYZ', {0: v})
        return self.out(n, 0), self.out(n, 1), self.out(n, 2)

    def rgb_sep(self, c):
        n = self.node('ShaderNodeSeparateColor', {0: c})
        return self.out(n, 0), self.out(n, 1), self.out(n, 2)

    def rgb(self, r, g, bb):
        return self.out(self.node('ShaderNodeCombineColor', {0: r, 1: g, 2: bb}), 0)

    def ramp(self, f, stops, interp='LINEAR'):
        n = self.node('ShaderNodeValToRGB', {0: f})
        cr = n.color_ramp
        cr.interpolation = interp
        while len(cr.elements) > len(stops):
            cr.elements.remove(cr.elements[-1])
        while len(cr.elements) < len(stops):
            cr.elements.new(0.5)
        for el, (pos, col) in zip(cr.elements, stops):
            el.position = pos
            el.color = tuple(col) + ((1.0,) if len(col) == 3 else ())
        return self.out(n, 'Color')

    # coordinates & textures --------------------------------------------
    def torus(self, uv, ax=1.0, ay=1.0, rot=None):
        """Flat-torus embedding of a periodic (u,v) square into 4D.

        One repeat of u maps to a circle of circumference ax, one repeat of v to ay,
        so texture features have frequency `scale` per repeat (scaled by 1/ax, 1/ay)
        and every 4D texture sampled through it tiles seamlessly.
        rot=(i,j,k,l): use u' = i*u + j*v, v' = k*u + l*v (integers keep periodicity).
        """
        u, v, _ = self.sep(uv)
        if rot:
            i, j, k, l = rot
            u, v = u * i + v * j, u * k + v * l
        ru, rv = ax / TAU, ay / TAU
        a, c = u * TAU, v * TAU
        vec = self.xyz(a.cos() * ru, a.sin() * ru, c.cos() * rv)
        w = c.sin() * rv
        return (vec, w)

    def noise4(self, t, scale=4.0, detail=4.0, rough=0.5, lac=2.0, dist=0.0, ntype='FBM', color=False):
        vec, w = t
        n = self.node('ShaderNodeTexNoise', {'Vector': vec, 'W': w, 'Scale': scale, 'Detail': detail,
                                             'Roughness': rough, 'Lacunarity': lac, 'Distortion': dist},
                      {'noise_dimensions': '4D', 'noise_type': ntype, 'normalize': True})
        return self.out(n, 'Color') if color else self.out(n, 'Fac')

    def voronoi4(self, t, scale=5.0, feature='F1', rand=1.0, metric='EUCLIDEAN', out='Distance', smooth=1.0):
        vec, w = t
        n = self.node('ShaderNodeTexVoronoi', {'Vector': vec, 'W': w, 'Scale': scale, 'Randomness': rand,
                                               'Smoothness': smooth},
                      {'voronoi_dimensions': '4D', 'feature': feature, 'distance': metric, 'normalize': False})
        if isinstance(out, (list, tuple)):
            return [self.out(n, o) for o in out]
        return self.out(n, out)

    def white1(self, x, color=False):
        n = self.node('ShaderNodeTexWhiteNoise', {'W': x}, {'noise_dimensions': '1D'})
        return self.out(n, 'Color' if color else 'Value')

    def white4(self, t, color=False):
        vec, w = t
        n = self.node('ShaderNodeTexWhiteNoise', {'Vector': vec, 'W': w}, {'noise_dimensions': '4D'})
        return self.out(n, 'Color' if color else 'Value')

    def ridge(self, n):
        """1 - |2n - 1| : sharp ridges along the 0.5 iso-line of a noise."""
        return 1.0 - (n * 2.0 - 1.0).abs()


def blackbody_rgb(kelvin):
    """Linear Rec.709 colour of a blackbody (normalised so max channel = 1).

    Tanner Helland fit in sRGB, converted to linear; good to a few % between 1500-6500 K,
    which is all we need for lantern light.
    """
    t = kelvin / 100.0
    r = 255.0 if t <= 66 else 329.698727446 * ((t - 60) ** -0.1332047592)
    g = 99.4708025861 * math.log(t) - 161.1195681661 if t <= 66 else 288.1221695283 * ((t - 60) ** -0.0755148492)
    bb = 255.0 if t >= 66 else (0.0 if t <= 19 else 138.5177312231 * math.log(t - 10) - 305.0447927307)

    def lin(c):
        c = min(max(c / 255.0, 0.0), 1.0)
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    rgb = [lin(r), lin(g), lin(bb)]
    m = max(rgb)
    return tuple(c / m for c in rgb)


def srgb_to_lin(c):
    c = c / 255.0 if c > 1.0 else c
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hexlin(h):
    h = h.lstrip('#')
    return tuple(srgb_to_lin(int(h[i:i + 2], 16) / 255.0) for i in (0, 2, 4))
