"""Summarize results/raw-*.jsonl into results/summary.csv and print a table."""
import csv, glob, json, statistics, collections, os, re
# "Repairable" amounts: digits right, separator misread ("12,68", "30 50", "1,231. 14"), the kind a converter can fix with a rule.
LOOSE = re.compile(r"\d{1,3}(?:[,.]\s?\d{3})*(?:[.,]\s?|\s)\d{2}(?!\d)")
truth = json.load(open("data/truth.json"))
def repairable(r):
    txt = open(f"results/ocr/{r['engine']}/{r['statement']}__{r['condition']}__p{r['page']}.txt", encoding="utf-8").read()
    exact = collections.Counter(re.sub(r"\D", "", t) for t in re.findall(r"\d{1,3}(?:,\d{3})*\.\d{2}", txt))
    loose = collections.Counter(re.sub(r"\D", "", t) for t in LOOSE.findall(txt))
    found = exact | loose  # an amount counts if either reading finds it
    want = collections.Counter(a.replace(",", "").replace(".", "") for a in truth[r["statement"]]["pages"][r["page"] - 1]["amounts"])
    return [sum(min(n, found[k]) for k, n in want.items()), sum(want.values())]
rows = [json.loads(l) for f in sorted(glob.glob("results/raw-*.jsonl")) for l in open(f)]
for r in rows:
    r["amounts_repairable"] = repairable(r)
meta = {json.load(open(f))["engine"]: json.load(open(f)) for f in glob.glob("results/meta-*.json")}
g = collections.defaultdict(list)
for r in rows:
    g[(r["engine"], r["condition"])].append(r)
    g[(r["engine"], "ALL")].append(r)
out = []
for (eng, cond), rs in sorted(g.items()):
    pct = lambda k: round(100 * sum(r[k][0] for r in rs) / sum(r[k][1] for r in rs), 1)
    secs = [r["seconds"] for r in rs if not r["first_page"]]
    out.append({"engine": eng, "condition": cond, "pages": len(rs), "amounts_pct": pct("amounts"), "amounts_repairable_pct": pct("amounts_repairable"), "dates_pct": pct("dates"),
                "words_pct": pct("words"), "empty_pages": sum(1 for r in rs if r["words"][0] == 0 and r["amounts"][0] == 0),
                "median_s_per_page": round(statistics.median(secs), 2), "version": meta.get(eng, {}).get("version", ""),
                "load_s": meta.get(eng, {}).get("load_seconds", ""), "peak_mb": meta.get(eng, {}).get("peak_rss_mb", "")})
with open("results/summary.csv", "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(out[0])); w.writeheader(); w.writerows(out)
for o in out:
    print(f"{o['engine']:10} {o['condition']:14} amounts {o['amounts_pct']:5}% (repairable {o['amounts_repairable_pct']:5}%) dates {o['dates_pct']:5}% words {o['words_pct']:5}% empty {o['empty_pages']} {o['median_s_per_page']}s/page")
