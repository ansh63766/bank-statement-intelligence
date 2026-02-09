# Bank Statement Intelligence API

A production-grade, highly resilient data pipeline and API that parses bank statement PDFs (digital or scanned), extracts all transactions, categorizes them using a hybrid regex + LLM strategy, computes financial health signals, and generates a creditworthiness score.

This system mirrors the underwriting pipelines used by leading fintech credit engines (such as CRED or KreditBee) to evaluate borrower credit risk.

---

## Key Features

1. **Self-Healing Multi-Parser Factory**:
   - Automatically detects if the statement PDF is digital text or a scanned image.
   - Employs dedicated rule-based parsers for major Indian banks: **SBI, HDFC, ICICI, Axis**.
   - Dynamically maps tabular layouts without hardcoded column indices, handling layout changes gracefully.
   - Automatically falls back to an LLM-based parsing engine on rule-based failures or unknown bank layouts.
2. **Native Scanned OCR Fallback (Vision)**:
   - Uses PyMuPDF (`fitz`) to rasterize scanned PDF pages to PNGs in memory and sends them directly to an LLM Vision model (no external C-library binaries like Tesseract or Poppler required).
3. **Pluggable LLM Provider Wrapper**:
   - Built to interact with **OpenRouter, OpenAI, DeepInfra, and Google AI Studio** using their OpenAI-compatible endpoints. Allows seamless provider switching via environment variables.
   - Features automated retries with exponential backoff on rate limits (429) or transient gateway errors.
4. **Batched Transaction Categorizer**:
   - Screens descriptions with deterministic rules for speed and cost savings.
   - Collects remaining low-confidence items, batches them (up to 40 at a time), and sends them to the LLM in a single call to minimize latency and token usage.
5. **Advanced Financial Signal Engine**:
   - **Income stability**: Evaluates payroll credit frequency, timing variance (standard deviation of credit days), and volume.
   - **Debt Service**: Calculates total EMIs and credit card outflow to output the EMI-to-income ratio.
   - **Balance liquidity**: Performs a mathematically correct **daily forward-fill** to calculate the Average Daily Balance (ADB) across all statement days, counting low-balance days.
   - **Negative Risk Triggers**: Detects NSF declines, overdraft usage, and cheque bounces.
6. **Weighted Credit Scoring Algorithm**:
   - Generates a creditworthiness score (0–100) and maps it to a qualitative rating (**GOOD, FAIR, POOR**) with detailed justifications.

---

## Directory Structure

```
e:\Project 1\
├── .env.example
├── .gitignore
├── README.md
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── main.py                # FastAPI entry point
│   ├── config.py              # Settings validator (Pydantic Settings)
│   ├── models/
│   │   ├── statements.py      # Transaction and statement schemas
│   │   └── underwriting.py    # Signals and credit scoring schemas
│   ├── parsers/
│   │   ├── base.py            # Base abstract class with parsers utilities
│   │   ├── pdf_detector.py    # Text vs scanned layout detector
│   │   ├── sbi_parser.py
│   │   ├── hdfc_parser.py
│   │   ├── icici_parser.py
│   │   ├── axis_parser.py
│   │   ├── llm_parser.py      # LLM OCR & text extraction
│   │   └── parser_factory.py  # Self-healing parser selector
│   ├── categorizer/
│   │   ├── rules.py           # Fast regex rules
│   │   ├── llm.py             # Batch LLM categorizer
│   │   └── engine.py          # Orchestrator
│   ├── signals/
│   │   └── engine.py          # Balance forward-fill and aggregates
│   ├── underwriting/
│   │   └── score.py           # Weighted credit score & rating
│   └── utils/
│       ├── llm_client.py      # OpenAI-compatible API client
│       └── pdf.py             # PyMuPDF image renderer
└── tests/                     # 100% Mocked unit & integration tests
```

---

## Setup & Installation

### Prerequisites
- Python 3.12+
- Git

### 1. Clone the repository and initialize virtual environment
```bash
# In the workspace directory
python -m venv .venv
```

Activate the virtual environment:
- **Windows (PowerShell)**:
  ```powershell
  .venv\Scripts\Activate.ps1
  ```
- **Linux/macOS**:
  ```bash
  source .venv/bin/activate
  ```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables
Copy `.env.example` to `.env` and fill in your keys:
```bash
cp .env.example .env
```

Parameters in `.env`:
- `LLM_PROVIDER`: Choose from `openrouter`, `openai`, `deepinfra`, or `google`.
- `OPENROUTER_API_KEY` / `OPENROUTER_MODEL`: Fill in details if using OpenRouter (e.g. `google/gemini-2.5-flash:free`).
- `GOOGLE_API_KEY` / `GOOGLE_MODEL`: Fill in details if using Google AI Studio directly.

---

## Running the Application

Start the FastAPI local development server:
```bash
python src/main.py
```

The server will start at `http://localhost:8000`. You can access the auto-generated Swagger UI at `http://localhost:8000/docs` to test endpoints interactively.

---

## API Endpoints Reference

### 1. Health Check
- **Endpoint**: `/api/v1/health`
- **Method**: `GET`
- **Response**:
  ```json
  {
    "status": "healthy",
    "service": "Bank Statement Intelligence"
  }
  ```

### 2. Analyze Statement
- **Endpoint**: `/api/v1/analyze`
- **Method**: `POST`
- **Payload**: `multipart/form-data` with key `file` containing the PDF statement.
- **Response Schema**:
  ```json
  {
    "creditworthiness_score": 85,
    "rating": "GOOD",
    "justifications": [
      "Positive: Strong average daily balance maintained (above Rs. 50,000).",
      "Positive: Zero active EMI outflow detected, maximizing credit headroom.",
      "Positive: Stable, recurring monthly salary credits detected.",
      "Positive: Clean history with zero bounces, NSF declines, or overdraft charges."
    ],
    "income_signals": {
      "total_salary": 65000.0,
      "salary_frequency": "Monthly",
      "salary_dates": ["2026-04-01", "2026-05-01"],
      "other_credits": 12000.0,
      "income_stability_score": 100.0
    },
    "spending_signals": {
      "total_debits": 42000.0,
      "discretionary_spending": 28000.0,
      "essential_spending": 14000.0,
      "spending_volatility": 1.24,
      "cash_withdrawal_ratio": 0.05,
      "top_spending_categories": {
        "Food": 8200.0,
        "Shopping": 12800.0,
        "Utilities": 4200.0,
        "Others": 16800.0
      }
    },
    "debt_signals": {
      "total_emi": 0.0,
      "emi_to_income_ratio": 0.0,
      "loan_payments_count": 0
    },
    "balance_signals": {
      "average_daily_balance": 52400.0,
      "minimum_balance": 32000.0,
      "ending_balance": 45000.0,
      "monthly_closing_balances": {
        "2026-04": 38000.0,
        "2026-05": 45000.0
      },
      "low_balance_days": 0
    },
    "negative_signals": {
      "cheque_bounce_count": 0,
      "overdraft_occurrences": 0,
      "nsf_count": 0
    }
  }
  ```

---

## Running Tests

Run the test suite using `pytest` to verify the rule engine, signal calculation, and API router.
```bash
pytest -v
```
All tests mock LLM responses to enable fast, offline, and token-free local validation.
