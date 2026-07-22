# Organization Capital Intelligence

Evidence-backed system that turns an official organization URL into:

1. A complete **Organization Intelligence Profile**
2. An evidence-backed map of **capital projects** and **pre-RFQ / pre-RFP opportunities**

It does **not** treat “find one budget PDF → extract projects” as the product. Instead it runs:

```text
Organization URL
→ canonical organization identification
→ organization and responsibility mapping
→ official source discovery
→ document inventory
→ source-role classification
→ selection of anchor project sources
→ inexpensive project index
→ project-to-document mapping
→ targeted document extraction
→ cross-source evidence consolidation
→ procurement and incumbent validation
→ pre-RFQ/pre-RFP classification
→ selective deep enrichment
```

The organization intelligence stage determines where and how capital projects must be found.

## Supported organization types

Cities, counties, water/wastewater districts, utility authorities, airports, ports, transit agencies, school districts, public universities, public hospitals, state agencies, housing authorities, park districts, transportation authorities, joint powers authorities, and other public / quasi-public organizations.

Strategies guide discovery; they do not hard-block unexpected structures.

## Architecture

```text
org_intel/
  cli.py                 CLI entry
  config.py              Settings + run config
  database.py            SQLite/Postgres-compatible checkpoints + cost ledger
  schemas/               Pydantic v2 models
  strategies/            OrganizationType strategies
  discovery/             Identity, org map, sources, documents, financial profile
  retrieval/             HTTP/HTML/PDF/Playwright + cache + robots
  documents/             Classification, PDF pages, OCR hooks, linking
  projects/              Anchor, index, mapping, extraction, opportunities
  procurement/           Portals, solicitations, awards, incumbents
  contacts/              Stakeholder map + email validation rules
  llm/                   Provider-independent router (GLM default, mock offline)
  exports/               JSON, Markdown, Excel
  refresh/               Change detection + incremental refresh
  quality/               Validation plan, confidence, research gaps
  pipeline/              Checkpointed orchestrator
```

### LLM roles

| Role | Purpose |
|------|---------|
| `cheap_classifier` | Source/document/type classification |
| `structured_extractor` | Targeted field extraction |
| `reasoning_model` | Conflicts, incumbents, opportunity assessment |
| `ocr_model` | Low-text page OCR (when configured) |
| `json_repair_model` | JSON repair |

Deterministic local processing is used for crawling, PDF text, page indexes, hashing, matching, and change detection. Expensive models are used only for ambiguous/complex work.

## Installation

Python 3.11+ required.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Optional: JS-rendered pages
playwright install chromium
```

Copy environment template:

```bash
cp .env.example .env
```

## Environment variables

| Variable | Description |
|----------|-------------|
| `ORG_INTEL_GLM_API_KEY` | GLM / Z.AI API key (never commit) |
| `ORG_INTEL_GLM_BASE_URL` | Default `https://open.bigmodel.cn/api/paas/v4` |
| `ORG_INTEL_GLM_CHEAP_MODEL` | Default `glm-4-flash` |
| `ORG_INTEL_GLM_STRUCTURED_MODEL` | Default `glm-4-air` |
| `ORG_INTEL_GLM_REASONING_MODEL` | Default `glm-4-plus` |
| `ORG_INTEL_MAX_COST_USD` | Hard cost ceiling |
| `ORG_INTEL_MAX_DOCUMENTS` | Document processing cap |
| `ORG_INTEL_MAX_PAGES` | Page indexing cap |
| `ORG_INTEL_OFFICIAL_SOURCES_ONLY` | Prefer official sources |
| `ORG_INTEL_CACHE_DIR` | Download/LLM cache directory |
| `ORG_INTEL_DATABASE_URL` | Default SQLite; Postgres URL compatible |
| `ORG_INTEL_RESPECT_ROBOTS` | Honor robots.txt |

If no API key is configured, the system uses a mock LLM provider and still runs deterministic discovery/extraction.

## CLI

```bash
python -m org_intel run \
  --org-url "https://www.como.gov" \
  --output-dir "./outputs/columbia-mo" \
  --mode full \
  --resume
```

### Modes

| Mode | Behavior |
|------|----------|
| `discover` | Identity, org map, source registry, document inventory |
| `project-map` | Anchor selection + inexpensive project index |
| `full` | Discovery through opportunity assessment + exports |
| `refresh` | Revisit known sources; reprocess only changes |
| `deep-enrich` | Deep research for selected `--project-id` / filters |

### Useful flags

```bash
--org-name
--org-type
--force
--max-cost-usd 25
--max-documents 200
--max-pages 5000
--max-searches 100
--max-workers 4
--official-sources-only / --no-official-sources-only
--include-third-party-sources
--project-id W0280
--project-category water
--min-project-value 1000000
--include-completed
--log-level INFO
--keep-intermediate
```

## Exact commands

### Discovery only

```bash
python -m org_intel run \
  --org-url "https://www.como.gov" \
  --output-dir "./outputs/columbia-mo" \
  --mode discover \
  --max-cost-usd 5
```

### Full Columbia analysis

```bash
python -m org_intel run \
  --org-url "https://www.como.gov" \
  --org-name "City of Columbia, Missouri" \
  --org-type city \
  --output-dir "./outputs/columbia-mo" \
  --mode full \
  --max-cost-usd 25 \
  --max-documents 200 \
  --official-sources-only \
  --resume
```

### Incremental refresh

```bash
python -m org_intel run \
  --org-url "https://www.como.gov" \
  --output-dir "./outputs/columbia-mo" \
  --mode refresh \
  --resume
```

### Deep enrichment for selected projects

```bash
python -m org_intel run \
  --org-url "https://www.como.gov" \
  --output-dir "./outputs/columbia-mo" \
  --mode deep-enrich \
  --project-id W0280 \
  --resume
```

### Offline / fixture-style local verification

```bash
pip install -e ".[dev]"
python -m pytest tests -q
```

## Cost controls and caching

- Downloads and LLM responses are cached (content hash + response hash).
- Unchanged documents are not reprocessed on refresh.
- OCR is limited to relevant low-text pages.
- Completed / cancelled / in-construction projects are not deeply enriched unless requested.
- `--max-cost-usd` is enforced with a cost ledger; runs stop safely and remain resumable.
- Partial outputs are written when the budget is reached.

## Checkpoints and resume

Checkpoints are persisted after each major phase under `output-dir/checkpoints/` and in SQLite.

Resume verifies organization URL compatibility, skips completed phases, retries incomplete work, and can rebuild exports without repeating research.

## Outputs

JSON:

- `organization_profile.json`
- `source_registry.json`
- `document_inventory.json`
- `financial_capital_profile.json`
- `organization_relationships.json`
- `project_index.json`
- `project_source_map.json`
- `projects_full.json`
- `opportunities.json`
- `incumbent_vendor_analysis.json`
- `contacts.json`
- `validation_plan.json`
- `research_gaps.json`
- `change_history.json`
- `cost_ledger.json`
- `run_manifest.json`

Reports:

- `organization_intelligence.md`
- `capital_projects.xlsx`

### Evidence model

Every major field can carry evidence with URL, quote, page/section, confidence, and provenance:

- `stated`
- `calculated`
- `inferred`
- `unknown`

Reports visually distinguish inferred content from confirmed fact. Absence of an incumbent is reported as `no_incumbent_identified_in_researched_sources`, never “no incumbent exists.”

Emails are never manufactured. Organization email patterns are stored separately and are not confirmed individual emails.

## How to add a new organization strategy

1. Add an enum value in `org_intel/schemas/enums.py` if needed.
2. Register an `OrganizationStrategy` in `org_intel/strategies/registry.py` with:
   - department terminology
   - capital source terms
   - governance / procurement / master-plan / financial terms
   - project categories
   - path hints
3. Add fixture coverage under `tests/fixtures/`.

Strategies guide discovery; classifiers still accept unexpected sources.

## How to add a procurement portal adapter

1. Add a `SourceRole` if the portal is new.
2. Extend portal regexes in `org_intel/discovery/source_classifier.py`.
3. Optionally add fetch/parse logic under `org_intel/procurement/` for structured solicitation pages.
4. Keep official third-party hosts labeled `official_third_party_host`.

## Troubleshooting

| Issue | What to try |
|-------|-------------|
| No projects found | Check whether a CIP/registry/budget source was discovered; inspect `anchor_selection.json` |
| JS-only portal empty | Install Playwright browsers; source will be flagged as `js_only_source` |
| Cost limit stop | Raise `--max-cost-usd` and rerun with `--resume` |
| Resume URL mismatch | Use the same `--org-url` / output directory |
| PDF text empty | Scanned PDF; OCR markers appear and research gaps are recorded |
| Identity ambiguity | Review `ambiguity_notes` and supply `--org-name` / `--org-type` |

## Known limitations

- Live third-party bid portals often require Playwright and site-specific adapters.
- Vision OCR for scanned PDFs depends on provider image upload support; low-text pages are flagged when OCR is unavailable.
- Without `ORG_INTEL_GLM_API_KEY`, LLM enrichment uses the mock provider (deterministic heuristics still run).
- Secondary news sources are not used as silent evidence replacements.

## Ethical and access considerations

- Prefer official public sources.
- Respect `robots.txt` when enabled.
- Use a descriptive user agent.
- Do not bypass authentication walls.
- Cache responsibly; do not hammer public sites.
- Never commit API keys or credentials.

## Tests

```bash
python -m pytest tests -q
```

Coverage includes domain detection, disambiguation, strategies, source/document/record classification, PDF indexing, project matching, generic-name merge prevention, vendor normalization, email status, phase/procurement/opportunity rules, budget conflict preservation, cost limits, cache, refresh, schemas, Excel, and resume.

Synthetic fixtures: municipality, water district, university, airport authority.

## What could not be tested without external credentials

- Live GLM / Z.AI structured extraction quality on real pages
- Live Columbia (como.gov) end-to-end crawl against the public internet in this environment
- Authenticated procurement portals
- Production Playwright rendering of complex Granicus/Legistar/OpenGov boards
- Real OCR model vision calls for scanned engineering plan sets
