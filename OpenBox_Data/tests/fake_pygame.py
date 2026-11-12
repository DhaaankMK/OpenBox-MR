"""Pygame 'de mentira' (API mínima) só para testes de fumaça sem janela/SDL. NÃO é usado no jogo."""
import sys
import types

import numpy as np


import numbers


def _chk_color(c, where=""):
    if not isinstance(c, (tuple, list)) or len(c) not in (3, 4):
        raise TypeError(f"{where}: cor inválida {c!r}")
    for v in c:
        if isinstance(v, bool) or not isinstance(v, numbers.Integral) or not 0 <= int(v) <= 255:
            raise TypeError(f"{where}: componente de cor inválido {v!r} em {c!r}")


def _chk_int(v, what, where=""):
    if isinstance(v, bool) or not isinstance(v, numbers.Integral):
        raise TypeError(f"{where}: {what} precisa ser int, veio {type(v).__name__} ({v!r})")


def _chk_num(v, what, where=""):
    if not isinstance(v, numbers.Real):
        raise TypeError(f"{where}: {what} não é número ({v!r})")


def _chk_pt(p, where=""):
    if hasattr(p, "x") and hasattr(p, "y"):
        return
    if not isinstance(p, (tuple, list)) or len(p) != 2:
        raise TypeError(f"{where}: ponto inválido {p!r}")
    _chk_num(p[0], "x", where)
    _chk_num(p[1], "y", where)


class Rect:
    __slots__ = ("x", "y", "w", "h")

    def __init__(self, *a):
        if len(a) == 1:
            a = tuple(a[0]) if isinstance(a[0], Rect) else a[0]
        if len(a) == 2:
            (x, y), (w, h) = a
        else:
            x, y, w, h = a
        self.x, self.y, self.w, self.h = int(x), int(y), int(w), int(h)

    def __iter__(self):
        return iter((self.x, self.y, self.w, self.h))

    def __eq__(self, o):
        return tuple(self) == tuple(o)

    def __repr__(self):
        return f"Rect({self.x},{self.y},{self.w},{self.h})"

    width = property(lambda s: s.w, lambda s, v: setattr(s, "w", int(v)))
    height = property(lambda s: s.h, lambda s, v: setattr(s, "h", int(v)))
    left = property(lambda s: s.x, lambda s, v: setattr(s, "x", int(v)))
    top = property(lambda s: s.y, lambda s, v: setattr(s, "y", int(v)))
    right = property(lambda s: s.x + s.w, lambda s, v: setattr(s, "x", int(v) - s.w))
    bottom = property(lambda s: s.y + s.h, lambda s, v: setattr(s, "y", int(v) - s.h))
    centerx = property(lambda s: s.x + s.w // 2, lambda s, v: setattr(s, "x", int(v) - s.w // 2))
    centery = property(lambda s: s.y + s.h // 2, lambda s, v: setattr(s, "y", int(v) - s.h // 2))
    size = property(lambda s: (s.w, s.h), lambda s, v: (setattr(s, "w", int(v[0])), setattr(s, "h", int(v[1]))))

    def _set(self, ax, ay, v):
        ox, oy = v
        self.x = int(ox) if ax == 0 else int(ox) - self.w // 2 if ax == 1 else int(ox) - self.w
        self.y = int(oy) if ay == 0 else int(oy) - self.h // 2 if ay == 1 else int(oy) - self.h

    topleft = property(lambda s: (s.x, s.y), lambda s, v: s._set(0, 0, v))
    topright = property(lambda s: (s.right, s.y), lambda s, v: s._set(2, 0, v))
    midtop = property(lambda s: (s.centerx, s.y), lambda s, v: s._set(1, 0, v))
    midleft = property(lambda s: (s.x, s.centery), lambda s, v: s._set(0, 1, v))
    midright = property(lambda s: (s.right, s.centery), lambda s, v: s._set(2, 1, v))
    center = property(lambda s: (s.centerx, s.centery), lambda s, v: s._set(1, 1, v))
    bottomleft = property(lambda s: (s.x, s.bottom), lambda s, v: s._set(0, 2, v))
    midbottom = property(lambda s: (s.centerx, s.bottom), lambda s, v: s._set(1, 2, v))
    bottomright = property(lambda s: (s.right, s.bottom), lambda s, v: s._set(2, 2, v))

    def collidepoint(self, x, y=None):
        if y is None:
            x, y = x
        return self.x <= x < self.x + self.w and self.y <= y < self.y + self.h

    def inflate(self, dx, dy):
        return Rect(self.x - dx // 2, self.y - dy // 2, self.w + dx, self.h + dy)

    def move(self, dx, dy):
        return Rect(self.x + dx, self.y + dy, self.w, self.h)

    def copy(self):
        return Rect(self.x, self.y, self.w, self.h)

    def clip(self, o):
        o = Rect(o)
        x0, y0 = max(self.x, o.x), max(self.y, o.y)
        x1, y1 = min(self.right, o.right), min(self.bottom, o.bottom)
        return Rect(x0, y0, max(0, x1 - x0), max(0, y1 - y0))

    def clamp_ip(self, o):
        o = Rect(o)
        self.x = max(o.x, min(self.x, o.right - self.w))
        self.y = max(o.y, min(self.y, o.bottom - self.h))


class Surface:
    __slots__ = ("_size",)        # como o pygame real: não aceita atributos extras

    def __init__(self, size, flags=0):
        if size[0] < 0 or size[1] < 0:
            raise ValueError("Invalid resolution for Surface")
        self._size = (int(size[0]), int(size[1]))

    def get_size(self): return self._size
    def get_width(self): return self._size[0]
    def get_height(self): return self._size[1]
    def get_rect(self, **kw):
        r = Rect(0, 0, *self._size)
        for k, v in kw.items():
            setattr(r, k, v)
        return r
    def fill(self, color, rect=None, special_flags=0):
        _chk_color(color, "Surface.fill")

    def blit(self, source, dest, area=None, special_flags=0):
        if not isinstance(source, Surface):
            raise TypeError(f"blit: origem inválida {type(source).__name__}")
        _chk_pt(dest, "blit")

    def subsurface(self, r):
        r = Rect(r)
        if r.x < 0 or r.y < 0 or r.right > self._size[0] or r.bottom > self._size[1] or r.w < 0 or r.h < 0:
            raise ValueError("subsurface rectangle outside surface area")
        return Surface((r.w, r.h))

    def copy(self): return Surface(self._size)

    def set_alpha(self, a, flags=0):
        if a is not None:
            _chk_int(a, "alpha", "set_alpha")
            if not 0 <= a <= 255:
                raise ValueError("alpha fora de 0..255")
    def convert_alpha(self): return self
    def convert(self): return self


class Font:
    def __init__(self, path, size):
        _chk_int(size, "tamanho da fonte", "Font")
        self.size_ = size

    def render(self, text, aa, color, bg=None):
        if not isinstance(text, str):
            raise TypeError("render: texto precisa ser str")
        _chk_color(color, "Font.render")
        return Surface((len(text) * (self.size_ // 2 + 1), self.size_ + 4))

    def size(self, text): return (len(str(text)) * (self.size_ // 2 + 1), self.size_ + 4)


class Clock:
    def tick(self, fps=0): return 16
    def get_fps(self): return 60.0


class Sound:
    def __init__(self, *a): pass
    def play(self): pass
    def set_volume(self, v): pass


class _FakeModule(types.ModuleType):
    def __getattr__(self, name):
        if name.startswith("K_"):
            return 2000 + (sum(ord(c) * (i + 1) for i, c in enumerate(name)) % 5000)
        if name.isupper():
            return 1
        raise AttributeError(name)


def install():
    m = _FakeModule("pygame")
    consts = {"SRCALPHA": 1, "SCALED": 2, "FULLSCREEN": 4, "RESIZABLE": 8, "BLEND_RGB_ADD": 1, "BLEND_RGBA_MULT": 2,
              "QUIT": 256, "KEYDOWN": 768, "MOUSEBUTTONDOWN": 1025}
    for i, name in enumerate("ESCAPE SPACE RETURN LEFT RIGHT F1 F3 F11 F12 g c t p r h q w e a s d f 1 2 3 4".split()):
        consts["K_" + name] = 1000 + i
    m.__dict__.update(consts)
    m.Rect, m.Surface = Rect, Surface
    m.init = lambda: (6, 0)
    m.quit = lambda: None
    m.error = Exception
    ns = types.SimpleNamespace
    noop = lambda *a, **k: None

    def _surf(s_, w):
        if not isinstance(s_, Surface):
            raise TypeError(f"{w}: primeiro argumento não é Surface")

    def d_circle(surf, color, center, radius, width=0, **k):
        _surf(surf, "circle"); _chk_color(color, "circle"); _chk_pt(center, "circle"); _chk_num(radius, "raio", "circle"); _chk_int(width, "width", "circle")

    def d_rect(surf, color, rect, width=0, **k):
        _surf(surf, "rect"); _chk_color(color, "rect"); _chk_int(width, "width", "rect")
        for kk in ("border_radius",):
            if kk in k:
                _chk_int(k[kk], kk, "rect")
        if not hasattr(rect, "x"):
            if len(rect) == 4:
                [_chk_num(v, "rect", "rect") for v in rect]
            else:
                raise TypeError(f"rect inválido {rect!r}")

    def d_line(surf, color, a, b, width=1):
        _surf(surf, "line"); _chk_color(color, "line"); _chk_pt(a, "line"); _chk_pt(b, "line"); _chk_int(width, "width", "line")

    def d_lines(surf, color, closed, pts, width=1):
        _surf(surf, "lines"); _chk_color(color, "lines"); _chk_int(width, "width", "lines")
        if len(pts) < 2:
            raise ValueError("lines precisa de ao menos 2 pontos")
        [_chk_pt(p, "lines") for p in pts]

    def d_polygon(surf, color, pts, width=0):
        _surf(surf, "polygon"); _chk_color(color, "polygon"); _chk_int(width, "width", "polygon")
        if len(pts) < 3:
            raise ValueError("polygon precisa de ao menos 3 pontos")
        [_chk_pt(p, "polygon") for p in pts]

    def d_ellipse(surf, color, rect, width=0):
        _surf(surf, "ellipse"); _chk_color(color, "ellipse"); _chk_int(width, "width", "ellipse")

    def d_arc(surf, color, rect, a0, a1, width=1):
        _surf(surf, "arc"); _chk_color(color, "arc"); _chk_int(width, "width", "arc")

    m.draw = ns(circle=d_circle, rect=d_rect, line=d_line, lines=d_lines, polygon=d_polygon, ellipse=d_ellipse, arc=d_arc)
    m.font = ns(Font=Font, match_font=lambda *a, **k: None, SysFont=lambda *a, **k: Font(None, 16))
    m.display = ns(set_mode=lambda size, *a, **k: Surface(size), flip=noop, set_caption=noop, set_icon=noop, toggle_fullscreen=noop)
    def frombuffer(b, size, fmt):
        bpp = {"RGB": 3, "RGBA": 4}[fmt]
        if len(b) != size[0] * size[1] * bpp:
            raise ValueError("Buffer length does not equal format and resolution size")
        return Surface(size)
    m.image = ns(load=lambda p: Surface((512, 512)), frombuffer=frombuffer, save=noop)
    def smooth(s_, size):
        _chk_int(size[0], "largura", "smoothscale"); _chk_int(size[1], "altura", "smoothscale")
        if size[0] <= 0 or size[1] <= 0:
            raise ValueError("smoothscale: tamanho inválido")
        return Surface(size)
    m.transform = ns(smoothscale=smooth, rotate=lambda s_, deg: Surface(s_.get_size()), scale=smooth)
    state = {"events": []}
    m.event = ns(get=lambda: state.pop("pending", []) if "pending" in state else [])
    m._state = state
    m.mouse = ns(get_pos=lambda: (640, 360), get_pressed=lambda: (False, False, False))
    m.mixer = ns(get_init=lambda: (44100, -16, 2), init=noop, pre_init=noop, Sound=Sound)
    m.sndarray = ns(make_sound=lambda arr: Sound())
    m.time = ns(Clock=Clock, get_ticks=lambda: 1234)

    def mk(size):
        return Surface((size[0], size[1]))
    m.surfarray = ns(
        array3d=lambda s: np.zeros((s.get_width(), s.get_height(), 3), np.uint8),
        pixels3d=lambda s: np.zeros((s.get_width(), s.get_height(), 3), np.uint8),
        pixels_alpha=lambda s: np.zeros((s.get_width(), s.get_height()), np.uint8),
        make_surface=lambda arr: Surface((arr.shape[0], arr.shape[1])),
    )
    m.math = ns(Vector2=None)
    sys.modules["pygame"] = m
    return m
