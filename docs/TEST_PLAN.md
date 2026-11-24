# Test cases and execution evidence

Run from the project root:

```powershell
python -m pytest -v
```

The tests are offline and use a fake generator where needed. Expected/actual outcomes below reflect the latest local run: all listed automated tests passed. A live Anthropic request is deliberately not part of automated tests because it requires private credentials and may incur API charges.

| ID | Input / scenario | Expected | Actual |
|---|---|---|---|
| T01 | Valid lead and interaction; create and approve a draft | CRUD and status update persist | Pass |
| T02 | Lead with empty required name/programme | `ValueError`; no lead inserted | Pass |
| T03 | Malformed email | `ValueError` | Pass |
| T04 | Interaction with empty message | `ValueError` | Pass |
| T05 | Interaction for nonexistent lead | `LookupError` | Pass |
| T06 | Unsupported interaction direction | `ValueError` before insert | Pass |
| T07 | Clean and tokenize text containing punctuation and a URL | Message token is retained | Pass |
| T08 | Tokenize fee question plus URL | Punctuation/URL removed; normalized tokens returned | Pass |
| T09 | Inbound beginner/weekend enquiry | Stage and both preferences detected | Pass |
| T10 | Inbound fee and recording questions | Both question topics remain open | Pass |
| T11 | Fee question plus outbound fee mention; recording question remains | Fee addressed by topic heuristic; recording open | Pass |
| T12 | Empty NLP message list | `New Enquiry`, zero tokens | Pass |
| T13 | String-only enquiry asking for weekend details | Schedule marked open | Pass |
| T14 | Valid structured output with approved fact ID | Accepted | Pass |
| T15 | Output references unknown fact ID | Rejected with `ValueError` | Pass |
| T16 | Output message is blank | Rejected with `ValueError` | Pass |
| T17 | Factual claim has no citations | Rejected with `ValueError` | Pass |
| T18 | Claim cites a valid fact omitted from `fact_ids_used` | Rejected with `ValueError` | Pass |
| T19 | Malformed review notes | Rejected with `ValueError` | Pass |
| T20 | Missing Anthropic API key | Clear config error before network call | Pass |
| T21 | Anthropic-shaped response contains JSON and model metadata | Validated output and response model/ID returned | Pass |
| T22 | Anthropic request raises a network error | Surfaced as `LLMError`; no success fallback | Pass |
| T23 | End-to-end fake provider returns valid output | NLP, Anthropic metadata and pending SQLite draft traceable | Pass |
| T24 | Unsupported draft channel | Rejected before generator call | Pass |
| T25 | Initialize synthetic demo data twice | Exactly one sample lead, 3 interactions and 5 approved facts | Pass |
| T26 | Exit a database connection context | SQLite connection is closed | Pass |
| T27 | Change the selected draft channel | A draft from the previous context is cleared | Pass |
| T28 | Provider fails before returning a draft | No draft is persisted | Pass |
| T29 | Learning-interest text mentions AI Engineering | Stage is Interested and AI Engineering preference is detected | Pass |
| T30 | AI Engineering demo seed is initialized | Exactly five approved synthetic AI Engineering facts are available | Pass |
| T31 | Programme has no approved facts | Generator is not called and no draft is persisted | Pass |

For manual live verification, run one successful Anthropic draft and one configuration/API failure as described in `DEMO_SCRIPT.md`. Never add a real API key to test fixtures or evidence.

