"""
Thermal POS receipt generator — realistic paper look with price, columns, texture.
No emojis (system fonts don't render them on Vercel/Debian).
"""
from __future__ import annotations

import io
import random
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ─── Shop ─────────────────────────────────────────────────────────────────────
SHOP_NAME    = "KHANT DIGITAL PRODUCTS"
SHOP_TAGLINE = "Digital Subscriptions & Services"
SHOP_CONTACT = "@KhantsManagerBot"

# ─── Font paths ───────────────────────────────────────────────────────────────
_BOLD = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeMonoBold.ttf",
    "C:/Windows/Fonts/courbd.ttf",
]
_REG = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
    "/usr/share/fonts/truetype/freefont/FreeMono.ttf",
    "C:/Windows/Fonts/cour.ttf",
]


def _load(paths: list[str], size: int):
    for p in paths:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            pass
    return None


def _w(font, text: str) -> int:
    if font is None:
        return len(text) * 7
    try:
        bb = font.getbbox(text)
        return bb[2] - bb[0]
    except Exception:
        return len(text) * 8


def _h(font, text: str = "Ag") -> int:
    if font is None:
        return 14
    try:
        bb = font.getbbox(text)
        return bb[3] - bb[1]
    except Exception:
        return 14


def _put(draw, xy, text, font, fill=(0, 0, 0)):
    f = font if font is not None else ImageFont.load_default()
    draw.text(xy, text, font=f, fill=fill)


def _add_paper_texture(img: Image.Image, strength: int = 8) -> Image.Image:
    """Add subtle grain to simulate thermal paper texture."""
    rng = random.Random(42)
    w, h = img.size
    pixels = img.load()
    for py in range(0, h, 2):
        for px in range(0, w, 2):
            noise = rng.randint(-strength, strength)
            r, g, b = pixels[px, py]
            r = max(220, min(255, r + noise))
            g = max(218, min(255, g + noise))
            b = max(205, min(255, b + noise))
            pixels[px, py] = (r, g, b)
    return img


def _draw_torn_edge(draw, y: int, w: int, top: bool = True):
    """Draw a micro-serrated edge to simulate torn thermal paper."""
    step = 6
    amp = 3
    prev = y
    rng = random.Random(1 if top else 2)
    for x in range(0, w, step):
        ny = y + rng.randint(-amp, amp)
        draw.line([(x, prev), (x + step, ny)], fill=(210, 205, 190), width=2)
        prev = ny


# ─── Public API ───────────────────────────────────────────────────────────────

def generate_receipt(
    order_id: str,
    product: str,
    plan_name: str,
    start_date: str,
    expiry_date: str,
    amount: str = "",
    username: str = "",
    issued_at: datetime | None = None,
) -> bytes:
    """
    Generate a realistic thermal receipt PNG.

    Parameters
    ----------
    order_id    : Subscription / order ID string
    product     : e.g. "ZOOM" or "CANVA"
    plan_name   : e.g. "Zoom Pro 30 Days"
    start_date  : "YYYY-MM-DD"
    expiry_date : "YYYY-MM-DD"
    amount      : Price string e.g. "5,000" or "5000 MMK" (optional)
    username    : Customer @username (without @)
    issued_at   : datetime; defaults to UTC now
    """
    now = issued_at or datetime.utcnow()
    date_str = now.strftime("%d %b %Y").upper()
    time_str = now.strftime("%I:%M %p")

    # Format amount
    if amount:
        amt_str = str(amount).strip()
        if "MMK" not in amt_str.upper():
            amt_str = f"{amt_str} MMK"
        amt_display = amt_str
    else:
        amt_display = ""

    # ── Canvas ────────────────────────────────────────────────────────────────
    W   = 400          # narrow thermal roll width
    PAD = 22
    IW  = W - PAD * 2  # inner width

    # Thermal paper color — warm off-white / cream
    PAPER = (253, 249, 238)
    INK   = (15, 15, 15)     # near-black ink
    DIM   = (100, 95, 85)    # secondary text
    RULE  = (190, 185, 170)  # separator line colour

    # ── Fonts ─────────────────────────────────────────────────────────────────
    f_xl   = _load(_BOLD, 19)  # shop name
    f_lg   = _load(_BOLD, 15)  # section headers
    f_md   = _load(_BOLD, 13)  # bold body
    f_reg  = _load(_REG,  13)  # regular body
    f_sm   = _load(_REG,  11)  # small footer

    LH  = _h(f_reg) + 8   # normal line height
    BH  = _h(f_xl)  + 10  # xl line height
    SH  = _h(f_sm)  + 6   # small line height

    # ── Rows ──────────────────────────────────────────────────────────────────
    # (kind, *payload)
    rows: list[tuple] = [
        ("gap",   20),
        ("cx",    SHOP_NAME, f_xl),
        ("gap",   2),
        ("cx",    SHOP_TAGLINE, f_sm),
        ("gap",   12),
        ("rule",  2),
        ("gap",   8),
        ("kv",    "DATE",      date_str,  f_reg, f_reg),
        ("kv",    "TIME",      time_str,  f_reg, f_reg),
        ("kv",    "RECEIPT #", order_id,  f_reg, f_md),
    ]

    if username:
        disp = username if username.startswith("@") else f"@{username}"
        rows.append(("kv", "CUSTOMER", disp, f_md, f_md))

    rows += [
        ("gap",   10),
        ("rule",  1),
        ("gap",   5),
        # Column header row
        ("cols",),
        ("gap",   5),
        ("rule",  1),
        ("gap",   6),
        # Item row: QTY | DESCRIPTION | AMOUNT
        ("item",  "1", plan_name, amt_display),
        ("gap",   6),
        ("rule",  1),
    ]

    # Details block
    rows += [
        ("gap",   5),
        ("kv",    "Product",     product.upper(), f_reg, f_reg),
        ("kv",    "Start Date",  start_date,      f_reg, f_reg),
        ("kv",    "Expiry Date", expiry_date,      f_reg, f_md),
        ("gap",   5),
        ("rule",  1),
    ]

    # Total block
    if amt_display:
        rows += [
            ("gap",   8),
            ("total", amt_display),
            ("gap",   8),
            ("rule",  2),
            ("rule",  2),
        ]
    else:
        rows += [
            ("gap",   4),
            ("rule",  2),
        ]

    # Footer
    rows += [
        ("gap",   10),
        ("cx",    "Thank You for Your Purchase!", f_md),
        ("gap",   4),
        ("cx",    f"Contact: {SHOP_CONTACT}", f_sm),
        ("cx",    "Powered by: Khant Digital Products", f_sm),
        ("gap",   20),
    ]

    # ── Height calculation ─────────────────────────────────────────────────────
    H = 0
    for row in rows:
        k = row[0]
        if k == "gap":
            H += row[1]
        elif k == "cx":
            fnt = row[2]
            H += _h(fnt) + 8
        elif k == "rule":
            H += 8
        elif k in ("cols", "item"):
            H += LH
        elif k == "total":
            H += _h(f_lg) + 14
        else:  # kv
            H += LH

    H += 10  # bottom torn edge clearance

    # ── Draw ──────────────────────────────────────────────────────────────────
    img  = Image.new("RGB", (W, H), PAPER)
    draw = ImageDraw.Draw(img)

    y = 0
    for row in rows:
        k = row[0]

        if k == "gap":
            y += row[1]

        elif k == "cx":           # centred text
            text, fnt = row[1], row[2]
            tw = _w(fnt, text)
            x  = max(PAD, (W - tw) // 2)
            _put(draw, (x, y), text, fnt, INK)
            y += _h(fnt) + 8

        elif k == "rule":         # horizontal rule
            thick = row[1]
            draw.line([(PAD, y + 3), (W - PAD, y + 3)], fill=RULE, width=thick)
            y += 8

        elif k == "kv":           # label + right-aligned value
            _, label, value, lf, vf = row
            _put(draw, (PAD, y), label, lf, DIM)
            vw = _w(vf, value)
            vx = W - PAD - vw
            # Ensure value doesn't overlap label
            lw = _w(lf, label) + PAD + 6
            vx = max(lw, vx)
            _put(draw, (vx, y), value, vf, INK)
            y += LH

        elif k == "cols":         # column header
            qty_col   = "QTY"
            desc_col  = "DESCRIPTION"
            amt_col   = "AMOUNT"
            _put(draw, (PAD, y),                       qty_col,  f_md, INK)
            dw = _w(f_md, desc_col)
            _put(draw, ((W - dw) // 2, y),            desc_col, f_md, INK)
            aw = _w(f_md, amt_col)
            _put(draw, (W - PAD - aw, y),              amt_col,  f_md, INK)
            y += LH

        elif k == "item":         # data row: qty | description | amount
            _, qty, desc, amt = row
            # Quantity
            _put(draw, (PAD, y), qty, f_reg, INK)
            # Description (centered, truncated to fit)
            max_desc_w = IW - _w(f_reg, qty) - _w(f_reg, amt) - 20
            # Truncate description if too long
            d = desc
            while _w(f_reg, d) > max_desc_w and len(d) > 5:
                d = d[:-2]
            dw = _w(f_reg, d)
            _put(draw, ((W - dw) // 2, y), d, f_reg, INK)
            # Amount
            if amt:
                aw = _w(f_md, amt)
                _put(draw, (W - PAD - aw, y), amt, f_md, INK)
            y += LH

        elif k == "total":        # TOTAL AMOUNT line
            label = "TOTAL AMOUNT:"
            value = row[1]
            pipe  = " | "
            full  = f"{label}{pipe}{value}"
            fw = _w(f_lg, full)
            x  = max(PAD, (W - fw) // 2)
            _put(draw, (x, y),                    label,         f_lg, INK)
            _put(draw, (x + _w(f_lg, label), y),  pipe,          f_lg, DIM)
            _put(draw, (x + _w(f_lg, label + pipe), y), value,   f_lg, INK)
            y += _h(f_lg) + 14

    # ── Paper effects ──────────────────────────────────────────────────────────
    # Subtle shadow on left & right edges (depth illusion)
    for i in range(6):
        shade = 230 - i * 4
        draw.line([(i, 0), (i, H)], fill=(shade, shade - 2, shade - 8))
        draw.line([(W - 1 - i, 0), (W - 1 - i, H)], fill=(shade, shade - 2, shade - 8))

    # Torn top & bottom edges
    _draw_torn_edge(draw, 0, W, top=True)
    _draw_torn_edge(draw, H - 4, W, top=False)

    # Paper grain texture
    img = _add_paper_texture(img, strength=5)

    # Very slight blur for realism (removes pixel-perfect artificiality)
    img = img.filter(ImageFilter.GaussianBlur(radius=0.4))

    buf = io.BytesIO()
    img.save(buf, format="PNG", dpi=(200, 200))
    buf.seek(0)
    return buf.read()
