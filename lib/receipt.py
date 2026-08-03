"""
Thermal receipt generator — narrow, authentic POS-style receipt.
No emojis (system fonts don't render them). Uses draw.line() for dividers.
Shop: Khant Digital Products | @KhantsManagerBot
"""
from __future__ import annotations

import io
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont

# ─── Shop Identity ────────────────────────────────────────────────────────────
SHOP_NAME    = "KHANT DIGITAL PRODUCTS"
SHOP_TAGLINE = "Digital Subscriptions & Services"
SHOP_CONTACT = "@KhantsManagerBot"

# ─── Font Paths (Vercel = Debian; Windows fallback) ───────────────────────────
_BOLD = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeMonoBold.ttf",
    "C:/Windows/Fonts/courbd.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]
_REG = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
    "/usr/share/fonts/truetype/freefont/FreeMono.ttf",
    "C:/Windows/Fonts/cour.ttf",
    "C:/Windows/Fonts/arial.ttf",
]


def _load(paths: list[str], size: int) -> ImageFont.FreeTypeFont | None:
    for p in paths:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            pass
    return None  # caller handles None -> load_default()


def _w(font, text: str) -> int:
    """Return pixel width of text for the given font."""
    if font is None:
        return len(text) * 7
    try:
        bb = font.getbbox(text)
        return bb[2] - bb[0]
    except Exception:
        return len(text) * 8


def _put(draw: ImageDraw.ImageDraw, xy, text: str, font, fill):
    """Draw text; falls back to default bitmap font if font is None."""
    f = font if font is not None else ImageFont.load_default()
    draw.text(xy, text, font=f, fill=fill)


# ─── Public ───────────────────────────────────────────────────────────────────

def generate_receipt(
    order_id: str,
    product: str,
    plan_name: str,
    start_date: str,
    expiry_date: str,
    username: str = "",
    issued_at=None,
) -> bytes:
    """
    Generate a POS thermal-style receipt image and return PNG bytes.
    """
    # ── Date / time ───────────────────────────────────────────────────────────
    now = issued_at if isinstance(issued_at, datetime) else datetime.utcnow()
    date_str = now.strftime("%d %b %Y").upper()
    time_str = now.strftime("%I:%M %p")

    # ── Canvas constants ──────────────────────────────────────────────────────
    W    = 420          # thermal paper width (px) — deliberately narrow
    PAD  = 18           # left / right margin
    IW   = W - PAD * 2 # inner text width
    BG   = (255, 255, 255)
    FG   = (0, 0, 0)
    DIM  = (80, 80, 80)
    LN   = (160, 160, 160)   # separator line colour

    LH   = 22  # normal line height
    BH   = 28  # bold / large line height
    SH   = 18  # small line height

    # ── Fonts ─────────────────────────────────────────────────────────────────
    f_xl   = _load(_BOLD, 21)   # shop name
    f_bold = _load(_BOLD, 13)   # headers, labels, totals
    f_reg  = _load(_REG,  13)   # normal rows
    f_sm   = _load(_REG,  11)   # footer, sub-text

    # ── Content rows ──────────────────────────────────────────────────────────
    # Each: (kind, *args)
    rows: list[tuple] = []

    # Header block
    rows += [
        ("gap",     16),
        ("cxl",     SHOP_NAME),          # centred XL bold
        ("gap",     3),
        ("csm",     SHOP_TAGLINE),        # centred small dim
        ("gap",     12),
        ("rule",),
        ("gap",     8),
        ("kv_r",    "DATE",      date_str),
        ("kv_r",    "TIME",      time_str),
        ("kv_r",    "RECEIPT #", order_id),
    ]

    if username:
        disp = username if username.startswith("@") else f"@{username}"
        rows.append(("kv_b",    "CUSTOMER",  disp))

    # Item block
    rows += [
        ("gap",  8),
        ("rule",),
        ("gap",  4),
        ("cols", "ITEM", "DETAIL"),
        ("gap",  4),
        ("rule",),
        ("gap",  4),
        ("kv_r", "Product",    product.upper()),
        ("kv_r", "Plan",       plan_name),
        ("kv_r", "Start Date", start_date),
        ("kv_b", "Expiry Date",expiry_date),
        ("gap",  6),
        ("rule",),
    ]

    # Status / total block
    rows += [
        ("gap",  8),
        ("kv_b", "STATUS", "ACTIVE"),
        ("gap",  8),
        ("rule",),
        ("rule",),
    ]

    # Footer
    rows += [
        ("gap",   10),
        ("cb",    "Thank You for Your Purchase!"),
        ("gap",    4),
        ("csm",   f"Contact: {SHOP_CONTACT}"),
        ("csm",   "Powered by: Khant Digital Products"),
        ("gap",   16),
    ]

    # ── Calculate total height ─────────────────────────────────────────────────
    H = 0
    for row in rows:
        k = row[0]
        if k == "gap":
            H += row[1]
        elif k == "cxl":
            H += BH
        elif k in ("rule",):
            H += 10
        elif k == "csm":
            H += SH
        else:
            H += LH

    # ── Draw ──────────────────────────────────────────────────────────────────
    img  = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    y = 0
    for row in rows:
        k = row[0]

        if k == "gap":
            y += row[1]

        elif k == "cxl":          # centred extra-large bold
            text = row[1]
            tw   = _w(f_xl, text)
            x    = max(PAD, (W - tw) // 2)
            _put(draw, (x, y), text, f_xl, FG)
            y += BH

        elif k == "cb":           # centred bold medium
            text = row[1]
            tw   = _w(f_bold, text)
            x    = max(PAD, (W - tw) // 2)
            _put(draw, (x, y), text, f_bold, FG)
            y += LH

        elif k == "csm":          # centred small dim
            text = row[1]
            tw   = _w(f_sm, text)
            x    = max(PAD, (W - tw) // 2)
            _put(draw, (x, y), text, f_sm, DIM)
            y += SH

        elif k == "rule":         # horizontal rule
            mid = y + 5
            draw.line([(PAD, mid), (W - PAD, mid)], fill=LN, width=1)
            y += 10

        elif k == "cols":         # column headers (ITEM | DETAIL)
            _, left, right = row
            _put(draw, (PAD, y), left,  f_bold, FG)
            rw = _w(f_bold, right)
            _put(draw, (W - PAD - rw, y), right, f_bold, FG)
            y += LH

        elif k == "kv_r":         # key-value regular
            _, label, value = row
            _put(draw, (PAD, y), label, f_reg, DIM)
            vw = _w(f_reg, value)
            vx = max(PAD + _w(f_reg, label) + 4, W - PAD - vw)
            _put(draw, (vx, y), value, f_reg, FG)
            y += LH

        elif k == "kv_b":         # key-value bold
            _, label, value = row
            _put(draw, (PAD, y), label, f_bold, FG)
            vw = _w(f_bold, value)
            vx = max(PAD + _w(f_bold, label) + 4, W - PAD - vw)
            _put(draw, (vx, y), value, f_bold, FG)
            y += LH

    # Jagged / perforated top and bottom edges (dashed lines)
    dash = 6
    for bx in range(0, W, dash * 2):
        draw.rectangle([bx, 0, bx + dash - 1, 3], fill=(220, 220, 220))
        draw.rectangle([bx, H - 3, bx + dash - 1, H - 1], fill=(220, 220, 220))

    buf = io.BytesIO()
    img.save(buf, format="PNG", dpi=(200, 200))
    buf.seek(0)
    return buf.read()
