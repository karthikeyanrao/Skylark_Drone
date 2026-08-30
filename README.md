# Skylark Deal Tracker

AI agent for Skylark Drones' deal pipeline and work-order operations — powered by **live monday.com data** and a **free LLM** (Google Gemini Flash).

## Stack

| Layer | Choice | Cost |
|-------|--------|------|
| Data | monday.com GraphQL API — live boards | **Free plan** |
| Agent | LLM via OpenAI-compatible endpoint (Gemini Flash default) | **Free tier** |
| UI | Streamlit | **Free / OSS** |
| Hosting | [Streamlit Community Cloud](https://streamlit.io/cloud) | **Free** |
| Libraries | pandas, openai, rapidfuzz, requests, openpyxl | **Free / OSS** |

> **No paid dependencies.** Both monday.com and Google AI Studio operate on a free tier with no credit card required.

## Quick start

### 1 — Get your credentials (both free, no credit card)

**monday.com API token:**
1. Log in → click your profile avatar (bottom-left or top-right)
2. Go to **Developers → API token** (or **Administration → API** / **Connections → Personal API token**)
3. Copy your personal API token

**Board IDs:**
- Open your Deals board in monday.com
- Copy the number from the URL: `https://app.monday.com/boards/`**`1234567890`**
- Repeat for Work Orders board

**LLM API key (pick one):**
- **Google Gemini Flash** (recommended): [aistudio.google.com](https://aistudio.google.com) → *Get API key* → done
- **Cerebras** (alternative): [console.cerebras.ai](https://console.cerebras.ai) → *API Keys → Generate*

### 2 — Configure

```bash
cp .env.example .env
# Fill in MONDAY_API_TOKEN, DEALS_BOARD_ID, WORK_ORDERS_BOARD_ID, LLM_API_KEY
```

### 3 — Run

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Environment variables

```env
# Required
MONDAY_API_TOKEN=your_token
DEALS_BOARD_ID=1234567890
WORK_ORDERS_BOARD_ID=9876543210
LLM_API_KEY=your_gemini_or_cerebras_key

# Optional — defaults shown
LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
LLM_MODEL=gemini-2.5-flash
AGENT_MODE=llm          # llm | analytical (fallback if no key)
DATA_SOURCE=monday      # monday | local (local only for pytest)
```

**Alternate LLM providers** (same `openai` package, just change base URL):
```env
# Cerebras
LLM_BASE_URL=https://api.cerebras.ai/v1
LLM_MODEL=llama3.1-8b

# Groq (if accessible)
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_MODEL=llama-3.3-70b-versatile
```

## Features

- **Live monday.com data:** GraphQL `boards → items_page` query, read-only client, 4-retry backoff
- **AI agent:** interprets open-ended natural language questions, calls pandas tools for numbers, asks clarifying questions for ambiguous queries (revenue definition, energy sector scope)
- **Data resilience layer:** header-row pollution filter, sector canonicalization, billing-status typo lookup (`BIlled` → `Billed`), 5-way status disambiguation, Deal Status/Stage cross-check, null-cause split for financial fields
- **Tools:** `query_deals`, `query_work_orders`, `join_deals_to_work_orders` — aggregation in pandas, not in the LLM
- **Leadership brief:** `/brief` or sidebar button — structured Markdown summary
- **UI:** Clean white + orange theme

## Column mapping (monday.com boards)

### Deals board
| monday.com type | Column |
|-----------------|--------|
| Item name | Deal Name |
| Text | Owner code, Client Code |
| Status | Deal Status, Deal Stage, Closure Probability, Sector/service, Product deal |
| Date | Close Date (A), Tentative Close Date, Created Date |
| Numbers | Masked Deal value |

### Work Orders board
| monday.com type | Column |
|-----------------|--------|
| Item name | Deal name masked |
| Text | Customer Name Code, Serial #, BD/KAM Personnel code, latest invoice no. |
| Status | Execution Status, Invoice Status, WO Status (billed), Billing Status, Collection status, Sector, Nature of Work, etc. |
| Date | Data Delivery Date, Date of PO/LOI, Probable Start/End Date, Last invoice date, Collection Date |
| Numbers | 9 financial + 4 quantity columns |
| Checkbox | Is any Skylark software platform part of deliverables |

> **Work Orders import:** Skip row 1 (blank). Real header is row 2 — use `header=1` when reading Excel.

## Tests

The cleaning and tool tests run against local Excel fixtures (no monday.com required):

```bash
$env:PYTEST_RUNNING=1; pytest tests/ -v      # Windows PowerShell
PYTEST_RUNNING=1 pytest tests/ -v            # Linux / Mac
```

`PYTEST_RUNNING=1` unlocks the Excel fallback path — it is **never** active in the deployed app.

## Deploy (Streamlit Community Cloud — free)

1. Push repo to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect repo, set main file: `app.py`
4. Add secrets (Streamlit UI → *Secrets*):
   ```toml
   MONDAY_API_TOKEN = "..."
   DEALS_BOARD_ID = "..."
   WORK_ORDERS_BOARD_ID = "..."
   LLM_API_KEY = "..."
   ```

## Architecture

```
monday.com GraphQL → loader → cleaning layer → query tools → LLM agent → Streamlit UI
                                    ↓
                              QualityReport
```

See [DECISION_LOG.md](DECISION_LOG.md) for assumptions, trade-offs, and what we'd do differently.
