# Free OCR on scanned bank statements: Tesseract vs EasyOCR vs PaddleOCR

A small, repeatable test of three free OCR engines on scanned bank statements, on a laptop CPU with no GPU.
Six fictional "Sample Bank" statements (40 transactions each, 12 pages) are rendered in four scan conditions
(clean scan, office scan, photocopy, phone photo) = 48 page images. Each engine reads every page with its default
English settings, and the text is scored against the known ground truth.

Write-up: [Best free OCR for scanned bank statements](https://statementconverteronline.com/blog/free-ocr-scanned-bank-statements)

## Results (all 48 pages)

| | Tesseract 5.5.0 | EasyOCR 1.7.2 | PaddleOCR 3.7.0 |
|---|---|---|---|
| Amounts read exactly | 87.3% | 91.4% | 96.1% |
| Amounts, digits right but separator misread | 87.5% | 97.4% | 97.1% |
| Dates (MM/DD) | 66.9% | 98.2% | 66.4% (100% with a dropped first digit restored) |
| Description words | 73.6% | 98.4% | 99.7% |
| Pages with no text at all | 4 | 0 | 0 |
| Median seconds per page | 2.8 | 40.7 | 125.4 |
| Peak memory | 71 MB | 4,440 MB | 4,871 MB |

Per condition and engine: `results/summary.csv`. Per page: `results/raw-<engine>.jsonl`. The raw OCR text of every
page: `results/ocr/<engine>/`.

Machine: Intel Core i5-10310U (4 cores, 8 threads), 32 GB RAM, no GPU, Docker on Windows (WSL2).

## Run it yourself

```bash
docker build -t ocr-bench .
docker run --rm -v "$PWD:/bench" ocr-bench python make_data.py data/          # statements + 48 page images + data/truth.json
for e in tesseract easyocr paddleocr; do
  docker run --rm -v "$PWD:/bench" -v ocr-models:/root ocr-bench python run_bench.py $e data/ results/
done
python summarize.py                                                              # results/summary.csv
```

`run_bench.py` resumes: pages already in `results/raw-<engine>.jsonl` are skipped. The first page of every run is left
out of the speed figures (model warm-up).

## Scoring

- **Amounts:** every transaction amount and running balance on the page, as printed (`1,231.14`), counted with repeats.
- **Repairable amounts:** every digit right but the separator misread (`12,68`, `30 50`, `1,231. 14`).
- **Dates:** `MM/DD` as printed. PaddleOCR often drops the first digit (`9/26`, `0/01`); with that restored its dates are 100%.
- **Words:** the description words on the page.

## PaddlePaddle version trap

`paddlepaddle` 3.3.1 crashed on CPU on the first page:
`NotImplementedError: (Unimplemented) ConvertPirAttribute2RuntimeAttribute not support [pir::ArrayAttribute<pir::DoubleAttribute>]`.
`enable_mkldnn=False` works around it at about 235 s per page. The Dockerfile pins `paddlepaddle==3.1.1`, which runs normally.

## What this does not cover

Real bank statements and real scanners (the scan conditions are simulated with Pillow), other fonts, layouts and
languages, image clean-up before OCR, tuned settings, GPUs, and turning the text into columns. Speeds are rough: the
EasyOCR and PaddleOCR runs were interrupted once and resumed.

## License

MIT
