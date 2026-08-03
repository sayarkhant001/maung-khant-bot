"""
Thermal POS receipt generator.
Downloads DejaVu fonts to /tmp/ on first cold start so text is always crisp.
Pure white background, pure black ink, no effects that wash out text.
"""
from __future__ import annotations

import io
import os
import random
import urllib.request
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont

# ─── Shop ─────────────────────────────────────────────────────────────────────
SHOP_NAME    = "KHANT DIGITAL PRODUCTS"
SHOP_TAGLINE = "Digital Subscriptions & Services"
SHOP_CONTACT = "@KhantsManagerBot"

# ─── Font cache paths ─────────────────────────────────────────────────────────
_CACHE_BOLD = "/tmp/_kdp_bold.ttf"
_CACHE_REG  = "/tmp/_kdp_reg.ttf"

# DejaVu fonts — open source, reliable GitHub CDN
_URL_BOLD = (
    "https://raw.githubusercontent.com/dejavu-fonts/dejavu-fonts"
    "/master/ttf/DejaVuSansMono-Bold.ttf"
)
_URL_REG = (
    "https://raw.githubusercontent.com/dejavu-fonts/dejavu-fonts"
    "/master/ttf/DejaVuSansMono.ttf"
)

# System font fallbacks (in case network is restricted)
_SYS_BOLD = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeMonoBold.ttf",
    "C:/Windows/Fonts/courbd.ttf",
]
_SYS_REG = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
    "/usr/share/fonts/truetype/freefont/FreeMono.ttf",
    "C:/Windows/Fonts/cour.ttf",
]


def _download_fonts():
    """Download fonts to /tmp/ if not already cached. Silent on error."""
    for path, url in [(_CACHE_BOLD, _URL_BOLD), (_CACHE_REG, _URL_REG)]:
        if not os.path.exists(path) or os.path.getsize(path) < 10_000:
            try:
                urllib.request.urlretrieve(url, path)
            except Exception as e:
                print(f"[receipt] Font download failed ({path}): {e}")


def _load(size: int, bold: bool = True) -> ImageFont.FreeTypeFont | None:
    """Load font at given size. Tries cache → system → None."""
    paths = ([_CACHE_BOLD] + _SYS_BOLD) if bold else ([_CACHE_REG] + _SYS_REG)
    for p in paths:
        try:
            f = ImageFont.truetype(p, size)
            return f
        except Exception:
            pass
    return None


def _tw(f, t: str) -> int:
    if f is None:
        return len(t) * 8
    try:
        bb = f.getbbox(t)
        return bb[2] - bb[0]
    except Exception:
        return len(t) * 8


def _th(f) -> int:
    if f is None:
        return 14
    try:
        bb = f.getbbox("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789")
        return bb[3] - bb[1]
    except Exception:
        return 14


def _draw(draw, x, y, text, font, fill=(0, 0, 0)):
    draw.text((x, y), text, font=font or ImageFont.load_default(), fill=fill)


def _draw_center(draw, W, y, text, font, fill=(0, 0, 0)):
    tw = _tw(font, text)
    _draw(draw, max(0, (W - tw) // 2), y, text, font, fill)


def _torn_edge(draw, y: int, W: int, seed: int):
    rng = random.Random(seed)
    step, amp, prev = 6, 3, y
    for x in range(0, W, step):
        ny = y + rng.randint(-amp, amp)
        draw.line([(x, prev), (x + step, ny)], fill=(210, 205, 195), width=2)
        prev = ny


# ─── Main ─────────────────────────────────────────────────────────────────────

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
    # Download fonts on first call
    _download_fonts()

    now    = issued_at or datetime.utcnow()
    date_s = now.strftime("%d %b %Y").upper()
    time_s = now.strftime("%I:%M %p")

    a = str(amount).strip() if amount else ""
    amt = (a if "MMK" in a.upper() else f"{a} MMK") if a else ""

    # ── Canvas ────────────────────────────────────────────────────────────────
    W     = 520
    PAD   = 28

    # Pure white background — maximum contrast
    BG    = (255, 255, 255)
    INK   = (0,   0,   0)       # pure black
    GRAY  = (90,  90,  90)      # labels
    LINE  = (180, 180, 180)     # separator lines

    # ── Fonts — all at comfortable reading sizes ───────────────────────────────
    F_TITLE = _load(22, bold=True)   # shop name
    F_HEAD  = _load(16, bold=True)   # column headers, CUSTOMER
    F_BOLD  = _load(15, bold=True)   # key data, expiry, total
    F_REG   = _load(15, bold=False)  # regular rows
    F_SUB   = _load(13, bold=False)  # tagline, footer

    # ── Row heights (font height + padding) ───────────────────────────────────
    H_TITLE = _th(F_TITLE) + 14
    H_HEAD  = _th(F_HEAD)  + 12
    H_REG   = _th(F_REG)   + 12
    H_SUB   = _th(F_SUB)   + 10
    H_TOT   = _th(F_BOLD)  + 18
    H_SEP   = 12

    # ── Measure total canvas height ───────────────────────────────────────────
    def measure(rows):
        h = 0
        for r in rows:
            k = r[0]
            if   k == "gap":   h += r[1]
            elif k == "sep":   h += H_SEP
            elif k == "title": h += H_TITLE
            elif k == "head":  h += H_HEAD
            elif k == "reg":   h += H_REG
            elif k == "sub":   h += H_SUB
            elif k == "total": h += H_TOT
        return h + 10  # torn edge clearance

    customer = (username if username.startswith("@") else f"@{username}") if username else ""

    rows = [
        ("gap",   24),
        ("title", SHOP_NAME),
        ("gap",    4),
        ("sub",   SHOP_TAGLINE),
        ("gap",   16),
        ("sep",   2),
        ("gap",   10),
        ("reg",   "DATE",       date_s,          GRAY, INK),
        ("reg",   "TIME",       time_s,          GRAY, INK),
        ("reg",   "RECEIPT #",  order_id,        GRAY, INK),
    ]
    if customer:
        rows.append(("head", "CUSTOMER", customer, GRAY, INK))

    rows += [
        ("gap",   12),
        ("sep",   1),
        ("gap",    8),
        ("cols",),
        ("gap",    6),
        ("sep",   1),
        ("gap",    8),
        ("item",  "1", plan_name, amt),
        ("gap",    8),
        ("sep",   1),
        ("gap",    8),
        ("reg",   "Product",     product.upper(), GRAY, INK),
        ("reg",   "Start Date",  start_date,      GRAY, INK),
        ("head",  "Expiry Date", expiry_date,     GRAY, INK),
        ("gap",    8),
        ("sep",   1),
    ]

    if amt:
        rows += [
            ("gap",   14),
            ("total", amt),
            ("gap",   14),
            ("sep",   2),
            ("gap",    2),
            ("sep",   2),
        ]

    rows += [
        ("gap",   16),
        ("head",  "", "Thank You for Your Purchase!", GRAY, INK),
        ("gap",    4),
        ("sub",   f"Contact: {SHOP_CONTACT}"),
        ("sub",   "Powered by: Khant Digital Products"),
        ("gap",   22),
    ]

    H = measure(rows)

    img  = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    y    = 0

    for r in rows:
        k = r[0]

        if k == "gap":
            y += r[1]

        elif k == "sep":
            thick = r[1]
            my = y + H_SEP // 2
            draw.line([(PAD, my), (W - PAD, my)], fill=LINE, width=thick)
            y += H_SEP

        elif k == "title":
            _draw_center(draw, W, y, r[1], F_TITLE, INK)
            y += H_TITLE

        elif k == "sub":
            _draw_center(draw, W, y, r[1], F_SUB, GRAY)
            y += H_SUB

        elif k == "reg":
            _, lbl, val, lc, vc = r
            _draw(draw, PAD, y, lbl, F_REG, lc)
            vw = _tw(F_REG, val)
            vx = max(PAD + _tw(F_REG, lbl) + 10, W - PAD - vw)
            _draw(draw, vx, y, val, F_REG, vc)
            y += H_REG

        elif k == "head":
            _, lbl, val, lc, vc = r
            if lbl:
                _draw(draw, PAD, y, lbl, F_HEAD, lc)
            vw = _tw(F_BOLD, val)
            if lbl:
                vx = max(PAD + _tw(F_HEAD, lbl) + 10, W - PAD - vw)
            else:
                vx = max(PAD, (W - vw) // 2)
            _draw(draw, vx, y, val, F_BOLD, vc)
            y += H_HEAD

        elif k == "cols":
            pairs = [("QTY", PAD, "L"), ("DESCRIPTION", W // 2, "C"), ("AMOUNT", W - PAD, "R")]
            for txt, cx, align in pairs:
                tw = _tw(F_HEAD, txt)
                x  = cx if align == "L" else (cx - tw // 2 if align == "C" else cx - tw)
                _draw(draw, x, y, txt, F_HEAD, INK)
            y += H_HEAD

        elif k == "item":
            _, qty, desc, price = r
            _draw(draw, PAD, y, qty, F_REG, INK)
            max_w = W - PAD * 2 - _tw(F_REG, qty) - (_tw(F_BOLD, price) if price else 0) - 20
            d = desc
            while _tw(F_REG, d) > max_w and len(d) > 4:
                d = d[:-2]
            _draw(draw, (W - _tw(F_REG, d)) // 2, y, d, F_REG, INK)
            if price:
                pw = _tw(F_BOLD, price)
                _draw(draw, W - PAD - pw, y, price, F_BOLD, INK)
            y += H_REG

        elif k == "total":
            _, price = r
            label, pipe = "TOTAL AMOUNT:", "  |  "
            lw = _tw(F_BOLD, label)
            pw = _tw(F_BOLD, pipe)
            vw = _tw(F_BOLD, price)
            sx = max(PAD, (W - lw - pw - vw) // 2)
            _draw(draw, sx,           y, label, F_BOLD, INK)
            _draw(draw, sx + lw,      y, pipe,  F_BOLD, GRAY)
            _draw(draw, sx + lw + pw, y, price, F_BOLD, INK)
            y += H_TOT

    # Torn paper edges (subtle)
    _torn_edge(draw, 2, W, seed=1)
    _torn_edge(draw, H - 6, W, seed=2)

    buf = io.BytesIO()
    img.save(buf, format="PNG", dpi=(200, 200))
    buf.seek(0)
    return buf.read()
