"""Run one OCR engine over every page image and score it against the ground truth.

Usage: python run_bench.py <engine> data/ results/
Engines: tesseract, easyocr, paddleocr. Each engine runs with its default English settings on CPU.
Writes results/raw-<engine>.jsonl (one line per page), results/ocr/<engine>/... (the raw text) and results/meta-<engine>.json.
"""
import collections
import json
import os
import re
import resource
import sys
import time

ENGINE, DATA, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
AMOUNT = re.compile(r"\d{1,3}(?:,\d{3})*\.\d{2}")
DATE = re.compile(r"\b\d{2}/\d{2}\b")


def load():
    if ENGINE == "tesseract":
        import subprocess
        import pytesseract
        version = subprocess.run(["tesseract", "--version"], capture_output=True, text=True).stdout.split("\n")[0]
        return (lambda p: pytesseract.image_to_string(p, lang="eng")), version
    if ENGINE == "easyocr":
        import easyocr
        reader = easyocr.Reader(["en"], gpu=False, verbose=False)
        return (lambda p: "\n".join(reader.readtext(p, detail=0))), "easyocr " + easyocr.__version__
    if ENGINE == "paddleocr":
        import paddleocr
        ocr = paddleocr.PaddleOCR(lang="en", device="cpu")  # defaults; needs paddlepaddle 3.1.1 (see Dockerfile)
        def run(p):
            texts = []
            for res in ocr.predict(p):
                texts += list(res["rec_texts"])
            return "\n".join(texts)
        return run, "paddleocr " + paddleocr.__version__
    raise SystemExit("unknown engine " + ENGINE)


def recall(truth, found):
    """Share of ground-truth items found, counting repeats (a multiset match)."""
    t, f = collections.Counter(truth), collections.Counter(found)
    hit = sum(min(n, f[k]) for k, n in t.items())
    return hit, sum(t.values())


def main():
    truth = json.load(open(os.path.join(DATA, "truth.json")))
    os.makedirs(os.path.join(OUT, "ocr", ENGINE), exist_ok=True)
    t0 = time.perf_counter()
    ocr, version = load()
    load_s = time.perf_counter() - t0
    raw = os.path.join(OUT, f"raw-{ENGINE}.jsonl")
    done = set()
    if os.path.exists(raw):  # resume: keep pages already scored
        for line in open(raw):
            r = json.loads(line)
            done.add((r["statement"], r["condition"], r["page"]))
    out = open(raw, "a")
    first = True  # the first page of every run includes warm-up, so it is left out of the speed figures
    for stmt in sorted(truth):
        for cond in sorted(os.listdir(os.path.join(DATA, stmt))):
            for pi, page in enumerate(truth[stmt]["pages"]):
                if (stmt, cond, pi + 1) in done:
                    continue
                img = os.path.join(DATA, stmt, cond, f"page-{pi + 1}.png")
                t1 = time.perf_counter()
                text = ocr(img)
                secs = time.perf_counter() - t1
                with open(os.path.join(OUT, "ocr", ENGINE, f"{stmt}__{cond}__p{pi + 1}.txt"), "w") as fh:
                    fh.write(text)
                up = text.upper()
                a_hit, a_n = recall(page["amounts"], AMOUNT.findall(text))
                d_hit, d_n = recall(page["dates"], DATE.findall(text))
                w_hit, w_n = recall([w.upper() for w in page["words"]], re.findall(r"[A-Z0-9#]+", up))
                out.write(json.dumps({"engine": ENGINE, "statement": stmt, "condition": cond, "page": pi + 1,
                                      "seconds": round(secs, 3), "first_page": first,
                                      "amounts": [a_hit, a_n], "dates": [d_hit, d_n], "words": [w_hit, w_n]}) + "\n")
                out.flush()
                first = False
                print(f"{ENGINE} {stmt} {cond} p{pi + 1}: amounts {a_hit}/{a_n} dates {d_hit}/{d_n} words {w_hit}/{w_n} {secs:.2f}s", flush=True)
    peak_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    json.dump({"engine": ENGINE, "version": version, "load_seconds": round(load_s, 2), "peak_rss_mb": round(peak_mb),
               "cpu_threads_visible": os.cpu_count()}, open(os.path.join(OUT, f"meta-{ENGINE}.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
