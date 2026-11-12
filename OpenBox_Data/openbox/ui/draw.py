"""Primitivas de desenho: texto com cache, retângulos translúcidos, vidro fosco (blur da câmera) e brilho."""
from __future__ import annotations

import math

import numpy as np
import pygame

from .. import theme as T

BLUR = None  # superfície (RGBA) com a câmera desfocada, atualizada a cada frame pelo app


def set_blur(surface):
    global BLUR
    BLUR = surface


# ------------------------------------------------------------------ fontes / texto
_FONT_NAMES = ["segoeui", "inter", "helveticaneue", "sfprotext", "roboto", "notosans", "dejavusans", "arial"]
_font_paths: dict = {}
_fonts: dict = {}
_texts: dict = {}
_ANCHORS = {"tl": "topleft", "tr": "topright", "tc": "midtop", "c": "center", "ml": "midleft",
            "mr": "midright", "bl": "bottomleft", "bc": "midbottom", "br": "bottomright"}


def _font_path(bold: bool):
    if bold not in _font_paths:
        path = None
        for name in _FONT_NAMES:
            try:
                path = pygame.font.match_font(name, bold=bold)
            except Exception:
                path = None
            if path:
                break
        _font_paths[bold] = path
    return _font_paths[bold]


def font(size: int, bold: bool = False):
    key = (int(size), bool(bold))
    f = _fonts.get(key)
    if f is None:
        f = pygame.font.Font(_font_path(bold), int(size))
        _fonts[key] = f
    return f


def _render(s, size, color, bold):
    key = (s, int(size), tuple(color), bool(bold))
    img = _texts.get(key)
    if img is None:
        if len(_texts) > 700:
            _texts.clear()
        img = font(size, bold).render(s, True, color)
        _texts[key] = img
    return img


def text(surf, s, pos, size=20, color=T.TEXT, bold=False, anchor="tl", alpha=255, shadow=False):
    s = str(s)
    img = _render(s, size, color, bold)
    r = img.get_rect()
    setattr(r, _ANCHORS[anchor], (int(pos[0]), int(pos[1])))
    if shadow:
        sh = _render(s, size, (0, 0, 0), bold)
        sh.set_alpha(int(alpha * 0.55))
        surf.blit(sh, (r.x + 1, r.y + 2))
    img.set_alpha(int(alpha))
    surf.blit(img, r)
    return r


def text_width(s, size=20, bold=False) -> int:
    return font(size, bold).size(str(s))[0]


def spaced(surf, s, pos, size=20, color=T.TEXT, bold=True, spacing=6, anchor="tl", alpha=255):
    """Texto com espaçamento entre letras (títulos estilo HUD)."""
    widths = [text_width(ch, size, bold) + spacing for ch in s]
    total = sum(widths) - spacing
    x = pos[0] - (total / 2 if anchor == "tc" else total if anchor == "tr" else 0)
    for ch, w in zip(s, widths):
        text(surf, ch, (x, pos[1]), size, color, bold, "tl", alpha)
        x += w
    return total


def wrap(s, size, width, bold=False):
    words, lines, cur = str(s).split(), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if text_width(trial, size, bold) <= width or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


# ------------------------------------------------------------------ formas translúcidas
_rr_cache: dict = {}
_mask_cache: dict = {}


def rrect(surf, rect, color, radius=12, width=0):
    rect = pygame.Rect(rect)
    if rect.w <= 1 or rect.h <= 1:
        return
    key = (rect.w, rect.h, tuple(color), radius, width)
    img = _rr_cache.get(key)
    if img is None:
        if len(_rr_cache) > 500:
            _rr_cache.clear()
        img = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(img, color, img.get_rect(), width, border_radius=radius)
        _rr_cache[key] = img
    surf.blit(img, rect.topleft)


def _mask(w, h, radius):
    key = (w, h, radius)
    m = _mask_cache.get(key)
    if m is None:
        if len(_mask_cache) > 200:
            _mask_cache.clear()
        m = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(m, (255, 255, 255, 255), m.get_rect(), border_radius=radius)
        _mask_cache[key] = m
    return m


def glass(surf, rect, radius=16, tint=T.GLASS, border=T.GLASS_BORDER, accent=None):
    """Painel de vidro fosco: mostra a câmera desfocada por trás + tinta + borda."""
    rect = pygame.Rect(rect)
    if rect.w <= 2 or rect.h <= 2:
        return
    if BLUR is not None:
        clip = rect.clip(BLUR.get_rect())
        if clip.w > 2 and clip.h > 2:
            tmp = BLUR.subsurface(clip).copy()
            if clip == rect:
                tmp.blit(_mask(rect.w, rect.h, radius), (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            surf.blit(tmp, clip.topleft)
    rrect(surf, rect, tint, radius)
    rrect(surf, rect, border, radius, 1)
    if accent:
        rrect(surf, (rect.x + radius, rect.y, max(2, rect.w - radius * 2), 2), (*accent, 220), 1)


# ------------------------------------------------------------------ brilho aditivo
_glows: dict = {}


def glow(surf, pos, radius, color, k=1.0):
    radius = max(4, int(round(radius / 4.0)) * 4)
    kq = max(1, int(round(k * 4)))
    key = (tuple(color), radius, kq)
    sp = _glows.get(key)
    if sp is None:
        if len(_glows) > 400:
            _glows.clear()
        size = radius * 2
        yy, xx = np.mgrid[0:size, 0:size]
        d = np.hypot(xx - radius + 0.5, yy - radius + 0.5) / radius
        f = np.clip(1.0 - d, 0.0, 1.0) ** 2 * (kq / 4.0)
        arr = np.zeros((size, size, 3), dtype=np.uint8)
        for c in range(3):
            arr[..., c] = np.clip(color[c] * f, 0, 255)
        sp = pygame.surfarray.make_surface(arr)
        _glows[key] = sp
    surf.blit(sp, (int(pos[0]) - radius, int(pos[1]) - radius), special_flags=pygame.BLEND_RGB_ADD)


def neon_line(layer, p1, p2, color, width=3, halo=True):
    """Linha com halo (para camada SRCALPHA)."""
    p1 = (int(p1[0]), int(p1[1]))
    p2 = (int(p2[0]), int(p2[1]))
    if halo:
        pygame.draw.line(layer, (*color, 46), p1, p2, width * 4)
        pygame.draw.line(layer, (*color, 90), p1, p2, width * 2)
    pygame.draw.line(layer, (*T.mix(color, (255, 255, 255), 0.55), 255), p1, p2, width)


def ring(surf, center, radius, color, width=2, alpha=255):
    r = int(radius)
    if r < 2:
        return
    size = r * 2 + width * 2 + 2
    img = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.circle(img, (*color, int(alpha)), (size // 2, size // 2), r, width)
    surf.blit(img, (int(center[0]) - size // 2, int(center[1]) - size // 2))


def arc(surf, center, radius, color, frac, width=4, alpha=255):
    """Arco de progresso (0..1) começando no topo."""
    frac = max(0.0, min(1.0, frac))
    if frac <= 0:
        return
    r = int(radius)
    size = r * 2 + width * 2 + 2
    img = pygame.Surface((size, size), pygame.SRCALPHA)
    rect = pygame.Rect(width + 1, width + 1, r * 2, r * 2)
    start = math.pi / 2
    pygame.draw.arc(img, (*color, int(alpha)), rect, start - frac * math.tau, start, width)
    surf.blit(img, (int(center[0]) - size // 2, int(center[1]) - size // 2))
