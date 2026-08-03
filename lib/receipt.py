"""
Generate a thermal-style receipt PNG image using Pillow.
Shop: Khant Digital Products  |  @KhantsManagerBot
"""
from __future__ import annotations

import io
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont

# ─── Shop Identity ────────────────────────────────────────────────────────────
SHOP_NAME     = "KHANT DIGITAL PRODUCTS"
SHOP_USERNAME = "@KhantsManagerBot"

# ─── Font Paths (tried in order; Vercel runs Debian/Ubuntu) ───────────────────
_MONO_FONTS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
    "/usr/share/fonts/truetype/freefont/FreeMonoBold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeMono.ttf",
    "C:/Windows/Fonts/courbd.ttf",
    "C:/Windows/Fonts/cour.ttf",
]

_SANS_FONTS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/arial.ttf",
]


def _font(paths: list[str], size: int) -> ImageFont.ImageFont:
    for p in paths:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            pass
    # Ultimate fallback — PIL bitmap (no anchor support)
    return None  # handled below


def _draw_text(draw: ImageDraw.ImageDraw, xy, text, font, fill, anchor=None):
    """Wrapper that falls back gracefully when anchor is not supported."""
    if font is None:
        # PIL default bitmap font — no anchor / truetype features
        fallback = ImageFont.load_default()
        draw.text(xy, text, font=fallback, fill=fill)
        return
    try:
        draw.text(xy, text, font=font, fill=fill, anchor=anchor)
    except Exception:
        draw.text(xy, text, font=font, fill=fill)


# ─── Public API ───────────────────────────────────────────────────────────────

def generate_receipt(
    order_id: str,
    product: str,
    plan_name: str,
    start_date: str,
    expiry_date: str,
    username: str = "",
    issued_at: str | None = None,
) -> bytes:
    """
    Return PNG bytes of a thermal-style receipt.

    Parameters
    ----------
    order_id    : Subscription / order ID
    product     : e.g. "ZOOM" or "CANVA"
    plan_name   : e.g. "Zoom 30 Days"
    start_date  : "YYYY-MM-DD"
    expiry_date : "YYYY-MM-DD"
    username    : Customer Telegram username (without @)
    issued_at   : Issue datetime string; defaults to now
    """
    issued = issued_at or datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    # ── Fonts ─────────────────────────────────────────────────────────────────
    f_shop   = _font(_SANS_FONTS,  22)   # shop name
    f_sub    = _font(_SANS_FONTS,  13)   # sub-header
    f_label  = _font(_MONO_FONTS,  13)   # row labels
    f_value  = _font(_MONO_FONTS,  13)   # row values
    f_small  = _font(_MONO_FONTS,  11)   # small footer text

    # ── Layout constants ──────────────────────────────────────────────────────
    W       = 480          # width in pixels
    PAD     = 28           # horizontal padding
    LINE    = 28           # row height
    BG      = (254, 253, 249)  # warm paper white
    FG      = (20,  20,  20)
    MID     = (90,  90,  90)
    LIGHT   = (170, 170, 170)

    # ── Build row definitions ─────────────────────────────────────────────────
    # Each row: (kind, payload)
    # kind: "gap" | "title" | "label" | "kv" | "sep" | "center"
    rows: list[tuple] = [
        ("gap",    14),
        ("title",  SHOP_NAME),
        ("center", SHOP_USERNAME),
        ("gap",    10),
        ("sep",    "═"),
        ("center", "✦  OFFICIAL RECEIPT  ✦"),
        ("sep",    "═"),
        ("gap",    10),
    ]

    if username:
        disp = f"@{username}" if not username.startswith("@") else username
        rows.append(("kv", ("Customer", disp)))

    rows += [
        ("kv",  ("Order ID",  order_id)),
        ("kv",  ("Product",   product.upper())),
        ("kv",  ("Plan",      plan_name)),
        ("gap", 6),
        ("sep", "─"),
        ("kv",  ("Start Date", start_date)),
        ("kv",  ("Expiry",     expiry_date)),
        ("sep", "─"),
        ("gap", 8),
        ("kv",  ("Issued",    issued)),
        ("gap", 10),
        ("sep", "═"),
        ("gap", 6),
        ("center", "Thank you for your purchase! 🙏"),
        ("center", "Khant Digital Products • @KhantsManagerBot"),
        ("gap", 14),
    ]

    # ── Calculate height ──────────────────────────────────────────────────────
    H = PAD * 2
    for kind, payload in rows:
        if kind == "gap":
            H += payload
        else:
            H += LINE

    # ── Draw image ────────────────────────────────────────────────────────────
    img  = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    # subtle edge shadow
    for i in range(4):
        shade = 200 + i * 12
        draw.rectangle([i, i, W - 1 - i, H - 1 - i], outline=(shade, shade, shade))

    # perforation holes at top & bottom
    hole_r = 4
    for hx in range(16, W - 10, 20):
        draw.ellipse([hx - hole_r, 2, hx + hole_r, 2 + hole_r * 2], fill=LIGHT)
        draw.ellipse([hx - hole_r, H - 2 - hole_r * 2, hx + hole_r, H - 2], fill=LIGHT)

    y = PAD
    inner_w = W - PAD * 2
    dash_cols = max(1, inner_w // 8)

    for kind, payload in rows:
        if kind == "gap":
            y += payload

        elif kind == "title":
            _draw_text(draw, (W // 2, y), payload, f_shop, FG, anchor="mt")
            y += LINE

        elif kind == "center":
            _draw_text(draw, (W // 2, y), payload, f_sub, MID, anchor="mt")
            y += LINE

        elif kind == "sep":
            _draw_text(draw, (PAD, y), payload * dash_cols, f_small, LIGHT)
            y += LINE

        elif kind == "kv":
            label, value = payload
            _draw_text(draw, (PAD, y),     f"{label}:",  f_label, MID, anchor="lt")
            _draw_text(draw, (W - PAD, y), value,        f_value, FG,  anchor="rt")
            y += LINE

    # ── Encode ────────────────────────────────────────────────────────────────
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.read()
