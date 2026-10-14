# Rooba Note

**Your money, reckoned — a local-first personal finance desktop app.**

Rooba Note is a native desktop dashboard for your Indian bank statements. Drop in a
statement, and it extracts, categorises, and visualises your transactions, then
produces deterministic forecasts and anomaly flags — all on your own machine.
No accounts, no cloud, no telemetry, no AI services: nothing ever leaves your computer.

---

## Highlights

- **Statement import** — drag-and-drop PDF / XLS / XLSX bank statements; overlapping
  uploads are de-duplicated automatically.
- **Statements browser** — every transaction with search, account/category/type
  filters, month-range slider, and pagination.
- **Categorisation** — edit a transaction's category (or mark it as an internal
  transfer) inline, with a filterable category picker.
- **Analytics** — cash-flow forecast, per-category spending forecast, runway, and
  anomaly flags (category spikes, duplicate charges, first-time large payments).
- **Category manager** — add, rename, and delete the categories you assign to.
- **100% local & deterministic** — same data in, same numbers out; reproducible by
  design.

## Screens

| Page | What it does |
| --- | --- |
| **Dashboard** | Browse and filter transactions; inline category assignment and transfer flagging. |
| **Statements** | All transactions across every statement, with a two-handle month-range filter and pagination. |
| **Analytics** | Cash-flow and spending forecasts, transfers excluded from totals, and anomaly flags. |
| **Upload Statement** | Drop zone for importing bank statements, with progress and de-duplication feedback. |
| **Settings** | Manage the category list used across the app. |

## Architecture

Rooba Note is a self-contained **PySide6 (Qt6)** front end with a bundled,
deterministic analytics core. Everything runs **locally**: no HTTP server, no
network calls, no CORS, and no external code folders.

```
┌──────────────────────────────────────────────┐
│  Rooba Note (PySide6)                         │
│  pbs_qt/pages/*      (UI)                      │
│  pbs_qt/core.py      (data-access bridge) ─────┼──▶ pbs_qt/_core/  (bundled core)
│  pbs_qt/charts.py    (custom charts)           │     ├─ database.py  (SQLAlchemy + SQLite)
└──────────────────────────────────────────────┘     ├─ parsers/     (ICICI, HDFC)
                                                      ├─ categorizer.py / transfers.py
                                                      ├─ analytics.py (forecasts, anomalies)
                                                      └─ service.py   (ingest + dedup)
                                                              │
                                                     data/pbs.db  (local SQLite)
```

- **UI** — `pbs_qt/` (pages, widgets, charts, theme).
- **Data bridge** — `pbs_qt/core.py` opens a short-lived SQLAlchemy session per call.
- **Core** — vendored under `pbs_qt/_core/`; independent of any other folder.

### Statement support

| Bank | Format | Notes |
| --- | --- | --- |
| ICICI | PDF (text-based) | Column-aware extraction via `pdfplumber`. |
| HDFC | XLS / XLSX | Tabular parsing via `xlrd`. |

> Statements must be **text-based** PDFs (no scanned images / OCR).

## Requirements

- **Python 3.11+** (developed against 3.14)
- A desktop environment capable of running Qt6
- Python packages (see `requirements.txt`): PySide6, SQLAlchemy, numpy, pdfplumber,
  xlrd, pypdf, pytest

## Getting started

The app is self-contained — no other project folder is required.

```bash
cd source/qt6

# 1. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the app
python run.py
```

You can also launch it as a module:

```bash
python -m pbs_qt
```

On first run the app creates a local SQLite database and seeds a default category
list.

### Where your data lives

| Running from | Database & staged files |
| --- | --- |
| Source (`python run.py`) | `source/qt6/data/pbs.db` |
| Packaged build (`.exe`, `.app`, AppImage) | a per-user data directory, e.g. `%APPDATA%\RoobaNote` (Windows), `~/Library/Application Support/RoobaNote` (macOS), `~/.local/share/RoobaNote` (Linux) |
| Portable / custom | wherever `ROOBA_DATA_DIR` points |

Set `ROOBA_DATA_DIR` to force a location (useful for a portable USB install).

### Running the tests

```bash
cd source/qt6
pytest
```

## Project layout

```
qt6/
├─ run.py                  # entry point: python run.py
├─ requirements.txt
├─ pbs_qt/
│  ├─ __main__.py          # python -m pbs_qt
│  ├─ main.py              # QApplication bootstrap + theme
│  ├─ main_window.py       # sidebar + stacked pages, cross-page data wiring
│  ├─ core.py              # data-access bridge (owns the data directory)
│  ├─ theme.py             # colour palette + Qt stylesheet
│  ├─ widgets.py           # cards, badges, stat tiles, category picker
│  ├─ charts.py            # custom-painted cash-flow and sparkbar charts
│  ├─ range_slider.py      # two-handle month-range slider
│  ├─ _core/               # bundled deterministic core (vendored)
│  │  ├─ database.py       # SQLAlchemy models + SQLite
│  │  ├─ parsers/          # ICICI, HDFC statement parsers
│  │  ├─ categorizer.py / transfers.py
│  │  ├─ analytics.py      # forecasts + anomalies
│  │  └─ service.py        # ingest + de-duplication
│  └─ pages/
│     ├─ dashboard.py
│     ├─ statements.py
│     ├─ analytics.py
│     ├─ upload.py
│     └─ settings.py
├─ data/                   # local SQLite DB + staging (gitignored)
└─ tests/
```

## Privacy & determinism

- **No network calls** at runtime — parsing, categorisation, and forecasting are all
  local.
- **No AI / LLM** — every insight is produced by transparent statistical rules.
- **Deterministic** — identical input data yields identical output, every run.
- **Transfers excluded** — money moved between your own accounts is flagged and kept
  out of income/spending totals.

## Status

Actively developed. Current focus: richer analytics and KPI-style insights on top of
the existing forecasts. See the project `wiki/plans/` for the roadmap.
