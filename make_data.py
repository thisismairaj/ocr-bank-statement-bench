"""Make fictional "Sample Bank" statements and four scanned versions of each page, with ground truth.

Usage: python make_data.py data/
Writes data/<statement>/<condition>/page-N.png and data/truth.json. Everything is made up; nothing real or private.
"""
import io
import json
import os
import random
import sys
from datetime import date, timedelta

import fitz  # PyMuPDF
import numpy as np
from PIL import Image, ImageFilter
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

OUT = sys.argv[1]
PER_PAGE = 22
MERCH = [("COFFEE CORNER #112", 4.75), ("CITY GROCERY MARKET", 86.40), ("FUEL STOP 55", 52.10),
         ("ONLINE STREAMING SVC", 15.99), ("PHARMACY PLUS", 23.18), ("METRO TRANSIT CARD", 30.00),
         ("HARDWARE DEPOT", 64.27), ("LUNCH BOX DELI", 12.60), ("ELECTRIC UTILITY CO AUTOPAY", 118.33),
         ("MOBILE PHONE BILL", 45.00), ("BOOKSHOP AND CAFE", 27.95), ("ATM WITHDRAWAL MAIN ST", 100.00),
         ("PET SUPPLY OUTLET", 38.60), ("PARKING GARAGE 7", 18.00), ("HOME INSURANCE PREMIUM", 1240.50)]
LONG = ["POS DEBIT CARD PURCHASE 4417 CITY GROCERY MARKET STORE 0193 SPRINGFIELD",
        "ACH DEBIT ELECTRIC UTILITY CO AUTOPAY CUSTOMER ID 000118733 REF 55102",
        "ONLINE TRANSFER TO SAVINGS ACCOUNT ENDING 7781 CONFIRMATION 3FQ9921"]

# 6 statements: two layouts (separate Debit/Credit columns, or one signed Amount column), some with long descriptions.
STATEMENTS = {
    "s1-debitcredit": dict(seed=11, long=False, style="debitcredit"),
    "s2-debitcredit-long": dict(seed=12, long=True, style="debitcredit"),
    "s3-amount": dict(seed=13, long=False, style="amount"),
    "s4-amount-long": dict(seed=14, long=True, style="amount"),
    "s5-debitcredit": dict(seed=15, long=False, style="debitcredit"),
    "s6-amount": dict(seed=16, long=False, style="amount"),
}


def txns(seed, n=40, long_desc=False):
    r = random.Random(seed)
    d = date(2026, 9, 1)
    out = []
    for i in range(n):
        d += timedelta(days=r.choice([0, 1, 1, 2]))
        if i % 9 == 4:
            out.append((d, "PAYROLL DEPOSIT SAMPLE EMPLOYER INC", 2150.00))
            continue
        m, a = r.choice(MERCH)
        a = round(a * r.uniform(0.6, 1.4), 2)
        desc = r.choice(LONG) if long_desc and i % 4 == 1 else m
        out.append((d, desc, -a))
    return out


def money(x):
    return f"{x:,.2f}"


def draw(path, rows, opening, style):
    """Draw the PDF; return per-page ground truth (dates, amounts incl. balances, description words)."""
    c = canvas.Canvas(path, pagesize=letter)
    W, H = letter
    bal = opening
    pages = [rows[i:i + PER_PAGE] for i in range(0, len(rows), PER_PAGE)]
    closing = round(opening + sum(a for _, _, a in rows), 2)
    truth_pages = []
    for pi, pg in enumerate(pages):
        t = {"dates": [], "amounts": [], "words": []}
        c.setFont("Helvetica-Bold", 14)
        c.drawString(50, H - 50, "SAMPLE BANK")
        c.setFont("Helvetica", 9)
        c.drawString(50, H - 64, "Fictional statement for testing only")
        c.drawString(380, H - 50, "Account: XXXX-0000")
        c.drawString(380, H - 62, "Period: 09/01 - 09/30")
        c.drawString(380, H - 74, f"Page {pi + 1} of {len(pages)}")
        y = H - 100
        if pi == 0:
            c.drawString(50, y, f"Beginning balance: {money(opening)}")
            c.drawString(250, y, f"Ending balance: {money(closing)}")
            y -= 24
        c.setFont("Helvetica-Bold", 9)
        heads = [(50, "Date"), (100, "Description"), (380, "Debit"), (440, "Credit"), (510, "Balance")] if style == "debitcredit" \
            else [(50, "Date"), (100, "Description"), (430, "Amount"), (510, "Balance")]
        for x, h in heads:
            c.drawString(x, y, h)
        y -= 16
        c.setFont("Helvetica", 9)
        for d, desc, a in pg:
            bal = round(bal + a, 2)
            ds = d.strftime("%m/%d")
            lines = [desc] if len(desc) <= 48 else [desc[:48], desc[48:]]
            c.drawString(50, y, ds)
            c.drawString(100, y, lines[0])
            if style == "debitcredit":
                c.drawRightString(420 if a < 0 else 480, y, money(abs(a)))
            else:
                c.drawRightString(470, y, money(abs(a)) + "-" if a < 0 else money(a))
            c.drawRightString(560, y, money(bal))
            for extra in lines[1:]:
                y -= 12
                c.drawString(100, y, extra)
            y -= 16
            t["dates"].append(ds)
            t["amounts"] += [money(abs(a)), money(bal)]
            t["words"] += " ".join(lines).split()
        truth_pages.append(t)
        c.showPage()
    c.save()
    return truth_pages, closing


def add_noise(a, sigma, rng):
    return np.clip(a + rng.normal(0, sigma, a.shape), 0, 255)


def condition(img300, name, rng):
    """Turn a clean 300 dpi page (greyscale PIL image) into one scan condition."""
    w, h = img300.size
    if name == "A-clean-scan":  # good flatbed scan
        return img300.rotate(0.3, resample=Image.BICUBIC, fillcolor=255)
    if name == "B-office-scan":  # 200 dpi office scanner, tilted, a little noise
        im = img300.resize((w * 2 // 3, h * 2 // 3), Image.LANCZOS).rotate(1.0, resample=Image.BICUBIC, fillcolor=255)
        im = im.filter(ImageFilter.GaussianBlur(0.4))
        return Image.fromarray(add_noise(np.asarray(im, dtype=np.float32), 8, rng).astype(np.uint8))
    if name == "C-photocopy":  # 150 dpi copy of a copy: blur, noise, grey paper, faded ink
        im = img300.resize((w // 2, h // 2), Image.LANCZOS).rotate(0.8, resample=Image.BICUBIC, fillcolor=255)
        im = im.filter(ImageFilter.GaussianBlur(0.8))
        a = np.asarray(im, dtype=np.float32)
        a = 70 + a * (155 / 255)  # ink becomes grey, paper becomes light grey
        return Image.fromarray(add_noise(a, 15, rng).astype(np.uint8))
    if name == "D-phone-photo":  # photo of the page: perspective, uneven light, blur, JPEG
        im = img300.resize((w * 2 // 3, h * 2 // 3), Image.LANCZOS)
        W2, H2 = im.size
        dx, dy = W2 * 0.04, H2 * 0.03
        # map output corners to input quad (top edge narrower than bottom, like a phone held slightly back)
        coeffs = find_coeffs([(0, 0), (W2, 0), (W2, H2), (0, H2)],
                             [(dx, dy), (W2 - dx * 0.5, dy * 1.5), (W2, H2), (0, H2 - dy * 0.5)])
        im = im.transform((W2, H2), Image.PERSPECTIVE, coeffs, Image.BICUBIC, fillcolor=255)
        a = np.asarray(im, dtype=np.float32)
        yy, xx = np.mgrid[0:H2, 0:W2]
        light = 0.62 + 0.38 * (xx / W2) * (0.6 + 0.4 * yy / H2)  # darker toward the top-left corner
        a = add_noise(a * light, 6, rng)
        im = Image.fromarray(a.astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.7))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=70)
        return Image.open(io.BytesIO(buf.getvalue())).convert("L")
    raise ValueError(name)


def find_coeffs(out_pts, in_pts):
    m = []
    for (x, y), (u, v) in zip(out_pts, in_pts):
        m.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        m.append([0, 0, 0, x, y, 1, -v * x, -v * y])
    A = np.array(m, dtype=np.float64)
    B = np.array([p for pt in in_pts for p in pt], dtype=np.float64)
    return np.linalg.solve(A, B).tolist()


CONDITIONS = ["A-clean-scan", "B-office-scan", "C-photocopy", "D-phone-photo"]

if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    truth = {}
    for name, cfg in STATEMENTS.items():
        rows = txns(cfg["seed"], 40, cfg["long"])
        pdf = os.path.join(OUT, f"{name}.pdf")
        pages, closing = draw(pdf, rows, 1250.00, cfg["style"])
        truth[name] = {"style": cfg["style"], "closing": closing, "pages": pages}
        doc = fitz.open(pdf)
        for pi, page in enumerate(doc):
            clean = Image.open(io.BytesIO(page.get_pixmap(dpi=300).tobytes("png"))).convert("L")
            for ci, cond in enumerate(CONDITIONS):
                rng = np.random.default_rng(cfg["seed"] * 100 + pi * 10 + ci)
                d = os.path.join(OUT, name, cond)
                os.makedirs(d, exist_ok=True)
                condition(clean, cond, rng).save(os.path.join(d, f"page-{pi + 1}.png"))
    json.dump(truth, open(os.path.join(OUT, "truth.json"), "w"), indent=1)
    n = sum(len(v["pages"]) for v in truth.values())
    print(f"{len(truth)} statements, {n} pages, {n * len(CONDITIONS)} page images")
