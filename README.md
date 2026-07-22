# Budget Project Extractor

Production-ready Python application that extracts every capital, infrastructure, facility, technology, and major equipment project from large public-sector budget PDFs using the Z.AI GLM API.

It produces:

1. A complete machine-readable JSON file (pretty + compact)
2. A professionally formatted Excel workbook

Designed for 400–600 page budget books, with checkpointed resumable processing, OCR fallback, schema validation, JSON repair, and conservative duplicate consolidation.

## Purpose

Municipal and agency budget documents often scatter capital-project details across executive summaries, CIP tables, department narratives, bond schedules, and appendices. This tool walks the full PDF page-by-page, extracts project records with source-page provenance, consolidates duplicates, and exports analyst-ready outputs.

## Architecture

```text
PDF acquire/inspect
  -> native text extraction (PyMuPDF) with <<<PDF_PAGE_N>>> markers
  -> OCR fallback for low-text pages (Z.AI glm-ocr /layout_parsing)
  -> overlapping text chunks (default 20 pages, 2-page overlap)
  -> Pass A: GLM chunk extraction + validation + repair + checkpoints
  -> Pass B: deterministic + optional GLM duplicate consolidation
  -> JSON + Excel exporters
```

Key packages:

* `budget_extractor/pdf_processor.py` – download, inspect, extract, chunk
* `budget_extractor/ocr_client.py` – OCR with cache and size/page limits
* `budget_extractor/glm_client.py` – official `zai-sdk` chat completions
* `budget_extractor/extraction.py` – two-pass orchestrator
* `budget_extractor/deduplication.py` – conservative merge logic
* `budget_extractor/excel_exporter.py` / `json_exporter.py` – outputs

## Installation

Python 3.11+ required.

```bash
python -m venv .venv
```

macOS / Linux:

```bash
source .venv/bin/activate
```

Windows:

```bash
.venv\Scripts\activate
```

Install the package and dependencies:

```bash
pip install -e ".[dev]"
```

## Environment setup

Copy the example env file:

macOS / Linux:

```bash
cp .env.example .env
```

Windows (Command Prompt):

```bat
copy .env.example .env
```

Windows (PowerShell):

```powershell
Copy-Item .env.example .env
```

Edit `.env` and set your key:

```env
ZAI_API_KEY=your_key_here
ZAI_BASE_URL=https://api.z.ai/api/paas/v4
GLM_MODEL=glm-5.2
GLM_REASONING_EFFORT=high
GLM_MAX_OUTPUT_TOKENS=32768
PDF_CHUNK_PAGES=20
PDF_OVERLAP_PAGES=2
OCR_CHUNK_PAGES=20
MAX_API_RETRIES=5
REQUEST_TIMEOUT_SECONDS=600
```

### How to obtain a Z.AI API key

1. Sign in at the [Z.AI open platform](https://z.ai/)
2. Create an API key in the API Keys management page
3. Put the key in `.env` as `ZAI_API_KEY`
4. Do not commit `.env` or paste keys into tickets/logs

This application uses the general Z.AI endpoint (`https://api.z.ai/api/paas/v4`), not a coding-plan endpoint.

## CLI

Help:

```bash
python -m budget_extractor --help
```

### Local PDF

```bash
python -m budget_extractor \
  --input "/path/to/budget_report.pdf" \
  --output-dir "./outputs" \
  --model "glm-5.2" \
  --chunk-pages 20 \
  --overlap-pages 2 \
  --resume
```

### Public PDF URL

```bash
python -m budget_extractor \
  --input "https://www.como.gov/archive/2025/09/fy26-final-adopted-budget-book.pdf" \
  --output-dir "./outputs" \
  --resume
```

### Useful options

| Flag | Meaning |
|---|---|
| `--ocr auto\|always\|never` | OCR policy for scanned/low-text pages |
| `--resume` | Continue from checkpoints |
| `--force` | Reprocess completed chunks |
| `--start-page` / `--end-page` | Limit page range |
| `--max-workers` | API concurrency (keep low; default 1) |
| `--keep-intermediate` | Keep extracted full text under `output/intermediate` |
| `--log-level` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |

## OCR modes

* `auto` (default): OCR only pages that look empty/corrupted/low-text
* `always`: OCR every selected page
* `never`: never call OCR

OCR uses `POST {ZAI_BASE_URL}/layout_parsing` with model `glm-ocr`, default max 20 pages/chunk, subdivision for large files, and checkpoint caching.

## Resume instructions

Checkpoints live under:

```text
outputs/
  run_manifest.json
  checkpoints/
    chunk_0001_input.txt
    chunk_0001_raw_response.json
    chunk_0001_validated.json
    chunk_0001_status.json
```

Resume safely:

```bash
python -m budget_extractor --input budget.pdf --output-dir outputs --resume
```

Resume verifies document hash and configuration compatibility, skips completed chunks, retries failed chunks, and reuses OCR cache entries.

## Output files

For an input stem such as `fy26-final-adopted-budget-book`:

```text
fy26-final-adopted-budget-book_capital_projects.json
fy26-final-adopted-budget-book_capital_projects.min.json
fy26-final-adopted-budget-book_capital_projects.xlsx
```

JSON includes document metadata, summary totals, projects, validation issues, duplicate audit, and run statistics.

### Excel sheets

1. **Summary** – document info, counts, totals, distributions, legend
2. **Projects** – one row per final project
3. **Annual Funding** – project × fiscal year rows
4. **Funding Sources** – discrete funding sources
5. **Contacts** – responsible contacts
6. **Evidence** – page-cited excerpts
7. **Budget Conflicts** – conflicting figures
8. **Validation Issues** – quality/validation findings
9. **Duplicate Audit** – merge / keep-separate decisions
10. **Run Log** – staged processing events

## Testing

```bash
pytest
```

Tests mock GLM/OCR calls and generate a synthetic PDF fixture at runtime. No API key is required for the unit/integration suite.

## API cost and token-use considerations

* Do not send an entire 400–600 page PDF in one prompt.
* Default chunking (20 pages, 2 overlap) balances recall and cost.
* `reasoning_effort=high` and large `max_output_tokens` improve extraction quality but increase spend.
* Resume/`--start-page`/`--end-page` help control cost while iterating.
* Keep `--max-workers` at 1–2 to reduce rate-limit retries.

## Troubleshooting

| Symptom | What to try |
|---|---|
| `Missing ZAI_API_KEY` | Create `.env` from `.env.example` and set the key |
| Download is not a PDF | Confirm the URL returns application/pdf |
| Encrypted PDF | Provide an unencrypted export |
| Many OCR pages | Expected for scanned books; use `--ocr auto` |
| Chunk failed validation | Inspect `checkpoints/*_raw_response.json`; re-run with `--resume` |
| Excel locked | Close the workbook and re-export |
| Rate limits / timeouts | Lower `--max-workers`, rely on retries, resume later |

Exit codes:

* `0` – success
* `1` – fatal configuration/runtime error
* `2` – completed with one or more failed chunks (partial outputs written)
* `130` – interrupted

## Known limitations

* OCR page mapping is best-effort when the OCR service returns a single undifferentiated markdown blob for a multi-page chunk.
* GLM may miss projects buried in unusual table layouts; overlapping chunks and repair reduce but do not eliminate this risk.
* Duplicate consolidation is intentionally conservative and may leave uncertain pairs for human review.
* Summary budget totals use `total_project_budget` only and do not sum annual appropriations into that master total.

## Security notes

* Never commit `.env` or API keys.
* The CLI logs only a masked key form.
* Raw model responses may contain document content; protect the `outputs/` directory accordingly.
* Use least-privilege storage for downloaded budget PDFs.

## Example: Columbia FY26 budget book

```bash
python -m budget_extractor \
  --input "https://www.como.gov/archive/2025/09/fy26-final-adopted-budget-book.pdf" \
  --output-dir "./outputs/como-fy26" \
  --model "glm-5.2" \
  --chunk-pages 20 \
  --overlap-pages 2 \
  --ocr auto \
  --resume \
  --keep-intermediate \
  --log-level INFO
```

For a cheaper smoke test on the first pages only:

```bash
python -m budget_extractor \
  --input "https://www.como.gov/archive/2025/09/fy26-final-adopted-budget-book.pdf" \
  --output-dir "./outputs/como-fy26-smoke" \
  --start-page 1 \
  --end-page 20 \
  --resume
```
