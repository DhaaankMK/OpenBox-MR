"""Identidade visual do OpenBox MR (baseada no azul-real do logo da Khyros Studio)."""

BG = (5, 7, 16)
ACCENT = (52, 84, 255)        # azul Khyros
ACCENT_HI = (110, 140, 255)
CYAN = (0, 222, 255)
MAGENTA = (255, 84, 214)
GREEN = (70, 255, 160)
AMBER = (255, 196, 70)
RED = (255, 72, 92)
TEXT = (238, 242, 255)
MUTED = (146, 156, 196)
DIM = (86, 96, 140)

GLASS = (10, 14, 34, 150)
GLASS_HI = (18, 26, 62, 190)
GLASS_BORDER = (120, 140, 255, 70)
GLASS_BORDER_HI = (150, 175, 255, 190)


def lerp(a, b, t):
    return a + (b - a) * t


def mix(c1, c2, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(lerp(c1[i], c2[i], t)) for i in range(3))
