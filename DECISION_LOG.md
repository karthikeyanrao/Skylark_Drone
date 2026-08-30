# Decision Log — Skylark Deal Tracker

## Assumptions

1. **Revenue is ambiguous by design.** The source data has three distinct financial concepts — deal value won (`Masked Deal value`), billed value, and collected amount. We resolve this via a single clarifying question per session, not a silent default that could mislead leadership.

2. **"Not yet billed" nulls are business state, not data loss.** Work order financial fields are 52–92% null because records populate at different pipeline stages. The null-cause classifier splits `not_applicable_yet` vs `true_gap` rather than collapsing everything into "missing."

3. **monday.com is the runtime data source — not optional.** The assignment explicitly states: *"Important: Do not hardcode CSV data. Your agent must query monday.com dynamically."* Local Excel files are retained only as pytest fixtures for the offline cleaning tests; they are never the active data source in the deployed app.

4. **An LLM is the runtime agent — not optional.** The assignment requires an AI agent that can "interpret founder-level business questions" and "ask clarifying questions when needed." Keyword routing alone cannot satisfy this. Google Gemini Flash is the default LLM (free, no credit card); the analytical engine is a fallback for environments with no API key.

5. **Closure Probability is categorical.** Despite the column name, values are High/Medium/Low text. The glossary blocks numeric aggregation.

6. **Sector canonical set is fixed at six values.** DSP, Tender, and other non-sector labels are flagged for review, not silently bucketed.

## Trade-offs

| Decision | Chosen | Alternative | Why |
|----------|--------|-------------|-----|
| LLM | Google Gemini 2.5 Flash (default, free tier) | Claude/Anthropic API (paid) | Assignment requires AI agent; Gemini free tier has no credit card requirement. Analytical engine retained as no-key fallback. |
| LLM client | `openai` package + `base_url` swap | Provider-specific SDKs | Single dependency, works with Gemini / Cerebras / Groq / any OpenAI-compatible endpoint. |
| Data source | monday.com live GraphQL (default) | Local Excel | Assignment explicitly forbids hardcoded CSV/Excel as runtime source. Excel retained as pytest fixture only (`PYTEST_RUNNING=1`). |
| Integration | Direct GraphQL API | monday hosted MCP | MCP returns generic raw rows; cleaning logic (header filter, status disambiguation) belongs in testable Python, not the prompt. |
| UI/hosting | Streamlit single-process | FastAPI + React | Speed to demo. Streamlit Community Cloud is free and link-testable. Documented as first thing to split in production. |
| Join key | Client Code / Customer Name Code | Display name fuzzy match | Masked deal names (Scooby-Doo, Sakura) make display names unreliable. Client codes are the primary join; fuzzy name is fallback. |

## What we'd do differently with more time

1. **Backend/frontend split** — FastAPI agent service behind Slack/email/dashboard integrations.
2. **Eval set** — Golden tests for ambiguous queries ("energy sector pipeline", "revenue this quarter") with expected clarifying questions and answers.
3. **Scoped read-only API token** — if monday.com supports granular permissions.
4. **Fix upstream** — resolve Deal Status/Stage disagreements in monday.com itself, not just flag downstream.
5. **Proper auth** — Streamlit Cloud demo is public; production needs SSO.

## Leadership update interpretation

The `/brief` mode delivers an on-demand structured snapshot:

- **Pipeline** — open deals by sector/stage with masked values
- **Revenue/won** — won deal totals with explicit note that billed ≠ collected
- **Ops** — execution + invoice status distributions
- **Risks** — stuck billing/invoices, Deal Status/Stage mismatches, non-canonical sectors

All computed deterministically in Python with QualityReport caveats appended — LLM narrates; pandas computes.

## Data resilience spec (implemented)

| Issue | Handling |
|-------|----------|
| Embedded header rows in Deals | Drop rows where ≥2 cells equal column header |
| `BIlled` typo in Billing Status | Canonical lookup table from observed values |
| 5 status columns | All exposed with one-line descriptions; never merged |
| Closure Probability as text | Glossary entry; no numeric aggregation |
| Sector drift (DSP, Tender) | 6-value canonical set; outliers flagged |
| Financial nulls | Null-cause split: not-applicable-yet vs true-gap |
| Deal Status vs Stage mismatch | Cross-check; flagged in QualityReport |

## Cost summary

| Component | Monthly cost |
|-----------|-------------|
| monday.com free plan | **$0** |
| Google AI Studio (Gemini Flash free tier) | **$0** |
| Streamlit Community Cloud | **$0** |
| All libraries (OSS) | **$0** |
