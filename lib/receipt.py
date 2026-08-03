"""
Thermal POS receipt — 2x supersampling for crisp text, no blur.
"""
from __future__ import annotations

import io
import random
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont

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

# ─── Helpers ──────────────────────────────────────────────────────────────────

def _load(paths, size):
    for p in paths:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            pass
    return None


def _tw(f, t):
    if f is None:
        return len(t) * 9
    try:
        bb = f.getbbox(t)
        return bb[2] - bb[0]
    except Exception:
        return len(t) * 9


def _th(f):
    if f is None:
        return 18
    try:
        bb = f.getbbox("Ag")
        return bb[3] - bb[1]
    except Exception:
        return 18


def _put(draw, xy, text, font, fill):
    draw.text(xy, text, font=font or ImageFont.load_default(), fill=fill)


def _paper_texture(img, strength=4):
    rng = random.Random(13)
    w, h = img.size
    px = img.load()
    for py in range(0, h, 1):
        for x in range(0, w, 1):
            n = rng.randint(-strength, strength)
            r, g, b = px[x, py]
            px[x, py] = (
                max(225, min(255, r + n)),
                max(222, min(255, g + n)),
                max(210, min(255, b + n)),
            )
    return img


def _torn_edge(draw, y, w, seed):
    rng = random.Random(seed)
    step, amp, prev = 5, 3, y
    for x in range(0, w, step):
        ny = y + rng.randint(-amp, amp)
        draw.line([(x, prev), (x + step, ny)], fill=(195, 190, 175), width=3)
        prev = ny


# ─── Receipt builder (internal, works at any scale) ───────────────────────────

def _build(W, PAD, fonts, colors, order_id, product, plan_name,
           start_date, expiry_date, amt_str, username, date, time_):

    PAPER, INK, DIM, RULE = colors
    F_SHOP, F_HEAD, F_BOLD, F_REG, F_SMALL = fonts

    LH_XL  = _th(F_SHOP)  + 16
    LH_HD  = _th(F_HEAD)  + 14
    LH_REG = _th(F_REG)   + 14
    LH_SM  = _th(F_SMALL) + 10
    LH_TOT = _th(F_BOLD)  + 20
    SEP    = 14

    rows: list[tuple] = []

    def gap(n):          rows.append(("gap", n))
    def rule(t=1):       rows.append(("rule", t))
    def cx(txt, f, lh):  rows.append(("cx", txt, f, lh))
    def kv(l, v, lf, vf): rows.append(("kv", l, v, lf, vf))

    gap(28)
    cx(SHOP_NAME, F_SHOP, LH_XL)
    gap(6)
    cx(SHOP_TAGLINE, F_SMALL, LH_SM)
    gap(18)
    rule(2)
    gap(12)

    kv("DATE",      date,     F_REG,  F_REG)
    kv("TIME",      time_,    F_REG,  F_REG)
    kv("RECEIPT #", order_id, F_REG,  F_BOLD)

    if username:
        d = username if username.startswith("@") else f"@{username}"
        kv("CUSTOMER", d, F_HEAD, F_BOLD)

    gap(14)
    rule(1)
    gap(10)
    rows.append(("col_hdr",))
    gap(8)
    rule(1)
    gap(10)
    rows.append(("item_row", "1", plan_name, amt_str))
    gap(10)
    rule(1)
    gap(10)

    kv("Product",     product.upper(), F_REG, F_REG)
    kv("Start Date",  start_date,      F_REG, F_REG)
    kv("Expiry Date", expiry_date,     F_HEAD, F_BOLD)

    gap(10)
    rule(1)

    if amt_str:
        gap(14)
        rows.append(("total", amt_str))
        gap(14)
        rule(2)
        gap(3)
        rule(2)

    gap(18)
    cx("Thank You for Your Purchase!", F_BOLD, LH_HD)
    gap(6)
    cx(f"Contact: {SHOP_CONTACT}",          F_SMALL, LH_SM)
    cx("Powered by: Khant Digital Products", F_SMALL, LH_SM)
    gap(26)

    # Height
    H = 0
    for r in rows:
        k = r[0]
        if   k == "gap":      H += r[1]
        elif k == "rule":     H += SEP
        elif k == "cx":       H += r[3]
        elif k == "kv":       H += LH_REG
        elif k == "col_hdr":  H += LH_HD
        elif k == "item_row": H += LH_REG
        elif k == "total":    H += LH_TOT
    H += 12

    img  = Image.new("RGB", (W, H), PAPER)
    draw = ImageDraw.Draw(img)
    IW   = W - PAD * 2
    y    = 0

    for r in rows:
        k = r[0]

        if k == "gap":
            y += r[1]

        elif k == "rule":
            my = y + SEP // 2
            draw.line([(PAD, my), (W - PAD, my)], fill=RULE, width=r[1])
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
            vx = max(PAD + _tw(lf, lbl) + 10, W - PAD - vw)
            _put(draw, (vx, y), val, vf, INK)
            y += LH_REG

        elif k == "col_hdr":
            pairs = [("QTY", "L", PAD), ("DESCRIPTION", "C", W // 2), ("AMOUNT", "R", W - PAD)]
            for txt, align, cx_ in pairs:
                tw = _tw(F_HEAD, txt)
                x  = cx_ if align == "L" else (cx_ - tw // 2 if align == "C" else cx_ - tw)
                _put(draw, (x, y), txt, F_HEAD, INK)
            y += LH_HD

        elif k == "item_row":
            _, qty, desc, amt = r
            _put(draw, (PAD, y), qty, F_REG, INK)
            max_w = IW - _tw(F_REG, qty) - (_tw(F_BOLD, amt) if amt else 0) - 30
            d = desc
            while _tw(F_REG, d) > max_w and len(d) > 4:
                d = d[:-2]
            _put(draw, ((W - _tw(F_REG, d)) // 2, y), d, F_REG, INK)
            if amt:
                aw = _tw(F_BOLD, amt)
                _put(draw, (W - PAD - aw, y), amt, F_BOLD, INK)
            y += LH_REG

        elif k == "total":
            _, amt = r
            label, pipe = "TOTAL AMOUNT:", "  |  "
            lw = _tw(F_BOLD, label)
            pw = _tw(F_BOLD, pipe)
            vw = _tw(F_BOLD, amt)
            sx = max(PAD, (W - lw - pw - vw) // 2)
            _put(draw, (sx, y),              label, F_BOLD, INK)
            _put(draw, (sx + lw, y),         pipe,  F_BOLD, DIM)
            _put(draw, (sx + lw + pw, y),    amt,   F_BOLD, INK)
            y += LH_TOT

    return img, H, W


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
    now   = issued_at or datetime.utcnow()
    date  = now.strftime("%d %b %Y").upper()
    time_ = now.strftime("%I:%M %p")
    a     = str(amount).strip() if amount else ""
    amt_str = (a if "MMK" in a.upper() else f"{a} MMK") if a else ""

    # ── Render at 2× resolution, then downsample for crisp text ───────────────
    SCALE = 2
    W_OUT = 480        # final output width
    W     = W_OUT * SCALE
    PAD   = 26 * SCALE

    PAPER = (252, 248, 235)
    INK   = (0, 0, 0)           # pure black — maximum contrast
    DIM   = (65, 60, 50)
    RULE  = (165, 160, 145)

    F_SHOP  = _load(_BOLD, 26 * SCALE)
    F_HEAD  = _load(_BOLD, 17 * SCALE)
    F_BOLD  = _load(_BOLD, 16 * SCALE)
    F_REG   = _load(_REG,  16 * SCALE)
    F_SMALL = _load(_REG,  13 * SCALE)

    img, H, W = _build(
        W, PAD,
        fonts=(F_SHOP, F_HEAD, F_BOLD, F_REG, F_SMALL),
        colors=(PAPER, INK, DIM, RULE),
        order_id=order_id, product=product, plan_name=plan_name,
        start_date=start_date, expiry_date=expiry_date,
        amt_str=amt_str, username=username, date=date, time_=time_,
    )

    # ── Edge shadows (at 2×) ──────────────────────────────────────────────────
    draw = ImageDraw.Draw(img)
    for i in range(10):
        s = 230 - i * 4
        draw.line([(i, 0), (i, H)],                 fill=(s, s - 3, s - 10))
        draw.line([(W - 1 - i, 0), (W - 1 - i, H)], fill=(s, s - 3, s - 10))

    # Torn edges (at 2×)
    _torn_edge(draw, 2, W, seed=1)
    _torn_edge(draw, H - 6, W, seed=2)

    # ── Downsample to output size — LANCZOS gives crisp anti-aliased text ─────
    H_out = H // SCALE
    img   = img.resize((W_OUT, H_out), Image.LANCZOS)

    # ── Subtle paper grain AFTER downsampling (so grain isn't blurred) ────────
    img = _paper_texture(img, strength=3)

    buf = io.BytesIO()
    img.save(buf, format="PNG", dpi=(200, 200))
    buf.seek(0)
    return buf.read()
