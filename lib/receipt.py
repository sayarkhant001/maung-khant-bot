"""
Thermal POS receipt — prominent fonts, deliberate spacing, realistic paper.
"""
from __future__ import annotations

import io
import random
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont, ImageFilter

SHOP_NAME    = "KHANT DIGITAL PRODUCTS"
SHOP_TAGLINE = "Digital Subscriptions & Services"
SHOP_CONTACT = "@KhantsManagerBot"

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


def _load(paths, size):
    for p in paths:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            pass
    return None


def _tw(font, text):
    if font is None:
        return len(text) * 9
    try:
        bb = font.getbbox(text)
        return bb[2] - bb[0]
    except Exception:
        return len(text) * 9


def _th(font):
    if font is None:
        return 16
    try:
        bb = font.getbbox("Ag")
        return bb[3] - bb[1]
    except Exception:
        return 16


def _put(draw, xy, text, font, fill=(0, 0, 0)):
    f = font if font is not None else ImageFont.load_default()
    draw.text(xy, text, font=f, fill=fill)


def _paper_texture(img, strength=6):
    rng = random.Random(7)
    w, h = img.size
    px = img.load()
    for py in range(h):
        for x in range(0, w, 2):
            n = rng.randint(-strength, strength)
            r, g, b = px[x, py]
            px[x, py] = (
                max(218, min(255, r + n)),
                max(215, min(255, g + n)),
                max(202, min(255, b + n)),
            )
    return img


def _torn_edge(draw, y, w, seed):
    rng = random.Random(seed)
    step, amp = 5, 4
    prev = y
    for x in range(0, w, step):
        ny = y + rng.randint(-amp, amp)
        draw.line([(x, prev), (x + step, ny)], fill=(200, 196, 182), width=2)
        prev = ny


# ─── Public ───────────────────────────────────────────────────────────────────

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
    now   = issued_at or datetime.utcnow()
    date  = now.strftime("%d %b %Y").upper()
    time_ = now.strftime("%I:%M %p")

    # Format price
    amt_str = ""
    if amount:
        a = str(amount).strip()
        amt_str = a if "MMK" in a.upper() else f"{a} MMK"

    # ── Canvas ────────────────────────────────────────────────────────────────
    W     = 480
    PAD   = 26
    PAPER = (252, 248, 235)     # warm cream
    INK   = (12, 12, 12)        # strong black ink
    DIM   = (75, 70, 60)        # secondary labels
    RULE  = (175, 170, 155)     # separator lines

    # ── Fonts — deliberately large & bold ─────────────────────────────────────
    F_SHOP  = _load(_BOLD, 24)   # shop name — largest
    F_HEAD  = _load(_BOLD, 16)   # column headers, section labels
    F_BOLD  = _load(_BOLD, 15)   # bold data (expiry, total)
    F_REG   = _load(_REG,  15)   # regular data rows
    F_SMALL = _load(_REG,  13)   # sub-text, footer

    # Line heights — generous padding between rows
    LH_XL  = _th(F_SHOP)  + 14   # shop name line
    LH_HD  = _th(F_HEAD)  + 12   # header row
    LH_REG = _th(F_REG)   + 12   # regular row
    LH_SM  = _th(F_SMALL) + 8    # small row
    LH_TOT = _th(F_BOLD)  + 16   # total amount row
    SEP    = 10                   # separator line height slot

    # ── Row definitions ───────────────────────────────────────────────────────
    rows: list[tuple] = []

    def gap(n):         rows.append(("gap", n))
    def rule(t=1):      rows.append(("rule", t))
    def cx(txt, f, lh): rows.append(("cx", txt, f, lh))
    def kv(lbl, val, lf=None, vf=None):
        rows.append(("kv", lbl, val, lf or F_REG, vf or F_REG))
    def kvb(lbl, val):  rows.append(("kv", lbl, val, F_HEAD, F_BOLD))

    gap(22)
    cx(SHOP_NAME,    F_SHOP,  LH_XL)
    gap(4)
    cx(SHOP_TAGLINE, F_SMALL, LH_SM)
    gap(16)

    rule(2)
    gap(10)

    kv("DATE",       date)
    kv("TIME",       time_)
    kv("RECEIPT #",  order_id, F_REG, F_BOLD)

    if username:
        d = username if username.startswith("@") else f"@{username}"
        kvb("CUSTOMER", d)

    gap(10)
    rule(1)
    gap(8)

    # Column header
    rows.append(("col_hdr",))
    gap(6)
    rule(1)
    gap(8)

    # Item row
    rows.append(("item_row", "1", plan_name, amt_str))
    gap(8)
    rule(1)
    gap(8)

    # Subscription details
    kv("Product",     product.upper())
    kv("Start Date",  start_date)
    kvb("Expiry Date", expiry_date)
    gap(8)
    rule(1)

    # Total
    if amt_str:
        gap(12)
        rows.append(("total", amt_str))
        gap(12)
        rule(2)
        gap(2)
        rule(2)

    # Footer
    gap(14)
    cx("Thank You for Your Purchase!", F_BOLD,  LH_HD)
    gap(4)
    cx(f"Contact: {SHOP_CONTACT}",     F_SMALL, LH_SM)
    cx("Powered by: Khant Digital Products", F_SMALL, LH_SM)
    gap(22)

    # ── Compute height ─────────────────────────────────────────────────────────
    H = 0
    for r in rows:
        k = r[0]
        if k == "gap":      H += r[1]
        elif k == "rule":   H += SEP
        elif k == "cx":     H += r[3]
        elif k == "kv":     H += LH_REG
        elif k == "col_hdr":H += LH_HD
        elif k == "item_row":H += LH_REG
        elif k == "total":  H += LH_TOT

    H += 10  # bottom clearance for torn edge

    # ── Draw ──────────────────────────────────────────────────────────────────
    img  = Image.new("RGB", (W, H), PAPER)
    draw = ImageDraw.Draw(img)

    y = 0
    IW = W - PAD * 2

    for r in rows:
        k = r[0]

        if k == "gap":
            y += r[1]

        elif k == "rule":
            thick = r[1]
            my = y + SEP // 2
            draw.line([(PAD, my), (W - PAD, my)], fill=RULE, width=thick)
            y += SEP

        elif k == "cx":
            _, txt, f, lh = r
            tw = _tw(f, txt)
            _put(draw, (max(PAD, (W - tw) // 2), y), txt, f, INK)
            y += lh

        elif k == "kv":
            _, lbl, val, lf, vf = r
            _put(draw, (PAD, y), lbl, lf, DIM)
            vw = _tw(vf, val)
            vx = max(PAD + _tw(lf, lbl) + 8, W - PAD - vw)
            _put(draw, (vx, y), val, vf, INK)
            y += LH_REG

        elif k == "col_hdr":
            cols = [("QTY", PAD), ("DESCRIPTION", W // 2), ("AMOUNT", W - PAD)]
            anchors = ["left", "center", "right"]
            for i, (txt, cx_) in enumerate(cols):
                tw = _tw(F_HEAD, txt)
                if anchors[i] == "left":
                    _put(draw, (cx_, y), txt, F_HEAD, INK)
                elif anchors[i] == "center":
                    _put(draw, (cx_ - tw // 2, y), txt, F_HEAD, INK)
                else:
                    _put(draw, (cx_ - tw, y), txt, F_HEAD, INK)
            y += LH_HD

        elif k == "item_row":
            _, qty, desc, amt = r
            # QTY
            _put(draw, (PAD, y), qty, F_REG, INK)
            # DESCRIPTION — centred, truncated
            max_w = IW - _tw(F_REG, qty) - (_tw(F_BOLD, amt) if amt else 0) - 24
            d = desc
            while _tw(F_REG, d) > max_w and len(d) > 4:
                d = d[:-2]
            dw = _tw(F_REG, d)
            _put(draw, ((W - dw) // 2, y), d, F_REG, INK)
            # AMOUNT
            if amt:
                aw = _tw(F_BOLD, amt)
                _put(draw, (W - PAD - aw, y), amt, F_BOLD, INK)
            y += LH_REG

        elif k == "total":
            _, amt = r
            label = "TOTAL AMOUNT:"
            pipe  = "  |  "
            value = amt
            lw = _tw(F_BOLD, label)
            pw = _tw(F_BOLD, pipe)
            vw = _tw(F_BOLD, value)
            total_w = lw + pw + vw
            sx = max(PAD, (W - total_w) // 2)
            _put(draw, (sx, y),          label, F_BOLD, INK)
            _put(draw, (sx + lw, y),     pipe,  F_BOLD, DIM)
            _put(draw, (sx + lw + pw, y),value, F_BOLD, INK)
            y += LH_TOT

    # ── Realism effects ───────────────────────────────────────────────────────
    # Edge depth shadows
    for i in range(8):
        s = 228 - i * 4
        draw.line([(i, 0), (i, H)],           fill=(s, s - 3, s - 10))
        draw.line([(W - 1 - i, 0), (W - 1 - i, H)], fill=(s, s - 3, s - 10))

    # Torn paper edges
    _torn_edge(draw, 2, W, seed=1)
    _torn_edge(draw, H - 5, W, seed=2)

    # Grain texture
    img = _paper_texture(img, strength=5)

    # Slight blur — removes synthetic sharpness
    img = img.filter(ImageFilter.GaussianBlur(radius=0.5))

    buf = io.BytesIO()
    img.save(buf, format="PNG", dpi=(200, 200))
    buf.seek(0)
    return buf.read()
