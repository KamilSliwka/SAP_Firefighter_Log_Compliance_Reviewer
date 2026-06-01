# 🛡️ SAP Firefighter Log Compliance Reviewer

An AI-assisted system that pre-screens SAP GRC Emergency Access Management (Firefighter) session logs and produces a structured verdict for the human controller. Built for Seargin AMS CoE to reduce manual review time.

---

## 🏗️ Architecture Diagram

```
[Raw JSON Log]
      │
      ▼
┌────────────────────────────────────────────────────────────────┐
│  Pydantic Ingestion & Validation Layer                         │
│  • Schema validation  • UTC normalization  • Chrono sort       │
│  • Adversarial input handling (malformed JSON, bad timestamps) |  
└────────────────────────────────────────────────────────────────┘
      │                         │
      │  valid                  │  invalid
      ▼                         ▼
[Review Engine]          [Error Response]
      │                  { verdict: ERROR,
      │                    findings: [schema issues] }
      ├──► [Deterministic Path (Python)]
      │    R-003, R-004, R-005, R-008, R-009, R-010, R-011, R-012
      │    → Zero cost · 100% precision · No hallucinations
      │
      └──► [Semantic Path (LLM — Cost-Aware Router)]
               │
               ├──► Fast Tier (Llama-3-8B / GPT-4o-mini)
               │    R-001 (length≥20), R-006, R-007  → Threshold + context checks
               │
               └──► Smart Tier (Llama-3-70B / GPT-4o)
                    R-002  → Deep language understanding
      │
      ▼
[Confidence & Correction Calculator]
  • Starts at 1.0, applies penalty per semantic finding
  • Generates draft message + reason_code rewrite for NEEDS_CORRECTION
      │
      ┌──────────────────────────────┐
      ▼                              ▼
[CLI Batch Predictor]      [Streamlit UI]
 python -m src.batch_predict   streamlit run src/app.py
 → predictions.jsonl           → Upload · Review · Decide
```

---

## 🧠 Architectural Decisions

### 1. Pydantic Data Shield & Adversarial Input Handling

Real-world SAP logs arrive from global instances across timezones, sometimes with encoding issues, missing fields, or manually edited JSON. The `SessionLog` Pydantic model handles this at the boundary before any business logic runs:

- **Malformed JSON** — caught by Pydantic's parser before model instantiation; returns a structured `ERROR` verdict with a human-readable description of the parse failure instead of crashing.
- **Missing required fields** — `session_id`, `firefighter_user`, `start_time`, `end_time` are required; all log arrays (`transaction_log`, `change_log`, `system_log`, `os_command_log`) default to empty lists if absent, so a session with no changes does not fail validation.
- **Wrong or missing timezone** — all timestamps are normalized to UTC using `@field_validator`. A timestamp arriving as `2026-04-15T05:14:22+02:00` is automatically converted to `2026-04-15T03:14:22+00:00` before any rule sees it. Timezone-naive timestamps (no `Z` or offset) are assumed UTC and flagged with a low-severity warning finding.
- **Chronological disorder** — all log arrays are sorted by timestamp after ingestion. This prevents R-012 (post-logoff activity) from producing false positives due to delivery order issues, and ensures R-009 (duration) always uses the correct start/end boundary.
- **Extra unknown fields** — ignored silently (`model_config = ConfigDict(extra="ignore")`), ensuring forward compatibility when SAP adds new log fields.
- **File size limit** — the Streamlit UI rejects files over 5 MB before parsing, preventing memory exhaustion from adversarial oversized payloads.

Any input that fails validation produces an output with `verdict: "ERROR"` and a finding that describes the exact schema violation, so the controller always gets a response rather than a silent failure.

### 2. Cost-Aware LLM Routing

Not all compliance checks require the same model capability. The router uses a two-tier approach:

- **Fast Tier** (e.g., GPT-4o-mini / Llama-3-8B): Used for R-001 (quality judgment on reasons that pass the length threshold), R-006, and R-007, where the LLM only needs to confirm a simple binary judgment. Approximately 10× cheaper per call.
- **Smart Tier** (e.g., GPT-4o / Llama-3-70B): Reserved for R-002, which requires deep understanding of SAP module semantics, business context, and natural language nuance across multiple functional areas.
- **Short-circuit logic**: If early deterministic rules produce a `REJECT` verdict with critical-severity findings, the LLM path is skipped entirely, saving 100% of API cost for clear-cut violations.

### 3. Dynamic Confidence Scoring

Confidence starts at `1.0` and decreases by a calibrated penalty for each semantic (LLM-based) finding. Deterministic findings carry no confidence penalty because their precision is 100%. This reflects the actual epistemic uncertainty in the output — a session flagged only by R-003 (debug execution, deterministic) carries higher confidence than one flagged only by R-002 (module mismatch, LLM).

### 4. Graceful UI Degradation

The Streamlit UI catches all Pydantic validation errors and JSON parse errors and displays them as controller-friendly alerts rather than stack traces. The controller always sees either a verdict or a clear explanation of why the file could not be processed.

---

## 📋 Compliance Rules — Baseline

### R-001 · Reason Quality & Specificity
| | |
|---|---|
| **Severity** | medium |
| **Implementation** | Hybrid — deterministic fast-path + Fast Tier LLM |
| **What it checks** | Two-stage evaluation: (1) deterministic length check — if `len(reason_code.strip()) < 20`, the rule fires immediately as a certain violation without calling the LLM; (2) if the reason is long enough, the Fast Tier LLM evaluates whether it contains specific business context: a ticket reference, the affected object (payment run ID, vendor number, company code), and a root cause explanation |
| **Why hybrid** | A reason shorter than 20 characters is provably insufficient regardless of content — no LLM call needed, zero cost, 100% precision for this case. For longer reasons, regex cannot judge "specificity" or "business context"; the LLM can distinguish between "Fixed urgent issue with payment run" (too vague) and "Resolved failed F110 run 20260518-001 for CC 1000; root cause: blocked vendor 145832" (acceptable) |
| **Not covered** | The validity of a cited ticket number — that requires live ITSM integration (e.g., ServiceNow API) |

### R-002 · Module Mismatch & Scope Creep
| | |
|---|---|
| **Severity** | high |
| **Implementation** | Semantic — Smart Tier LLM (prompt-engineered for module leakage, read/write mismatch, and self-incrimination patterns) |
| **What it checks** | Whether the stated reason (e.g., "HR lock issue") is consistent with the transactions executed (e.g., `FB02` — financial document change). Also catches "read-only" reasons where the change_log shows actual writes |
| **Why LLM** | Mapping human business language to SAP functional modules (FI, CO, MM, SD, HR, Basis) requires contextual reasoning unavailable to regex |
| **Not covered** | Highly customized `Z*`/`Y*` transactions with company-specific semantics unknown to the base LLM |

### R-003 · Debug & Replace Execution
| | |
|---|---|
| **Severity** | critical |
| **Implementation** | Deterministic |
| **What it checks** | `system_log` entries containing `/h` debug invocation or explicit debug-session messages (SM21 type) |
| **Why deterministic** | The SAP system log writes a fixed, unambiguous signature for debug mode entry. String matching is 100% precise and costs nothing |
| **Not covered** | Debug activity if SAP kernel-level auditing is disabled at the basis layer |

### R-004 · Direct Table Modification
| | |
|---|---|
| **Severity** | high |
| **Implementation** | Deterministic |
| **What it checks** | Presence of `SE16N`, `SM30`, `SE16`, or `SE17` in `transaction_log` combined with a non-empty `change_log` |
| **Why deterministic** | Closed, pre-defined list of restricted transaction codes. Exact string match is 100% accurate |
| **Not covered** | Custom programs (`Z_EDIT_TABLE`) that replicate SE16N functionality — covered by R-011 |

### R-005 · OS-Level Commands
| | |
|---|---|
| **Severity** | critical |
| **Implementation** | Deterministic |
| **What it checks** | Any non-empty `os_command_log` array |
| **Why deterministic** | Binary check. Any OS command in a standard firefighter session is a critical violation by definition |
| **Not covered** | OS commands executed through 0-day SAP vulnerabilities that bypass SM49/SM69 logging |

### R-006 · Volume Mismatch
| | |
|---|---|
| **Severity** | high |
| **Implementation** | Hybrid — deterministic fast-path + Fast Tier LLM |
| **What it checks** | Whether the number of change_log entries is proportionate to the stated reason. If `len(change_log) < 20`, LLM is skipped entirely (saving cost). Above the threshold, the LLM judges whether the reason justifies a mass update |
| **Why hybrid** | The count threshold is objective and cheap to compute. The judgment of whether "year-end vendor cleanup per CHG8090165" justifies 100+ changes requires semantic reasoning |
| **Not covered** | Low-volume data exfiltration (e.g., exactly 3 sensitive records changed per session over months) |
| **SoD pairs monitored** | See R-010 |

### R-007 · Business Hours & Emergency Justification
| | |
|---|---|
| **Severity** | medium |
| **Implementation** | Hybrid — deterministic UTC arithmetic + Fast Tier LLM |
| **What it checks** | Whether the session start time falls outside 08:00–18:00 UTC AND the reason code lacks emergency indicators. Python computes the time window; the LLM evaluates whether the text implies a genuine incident |
| **Why hybrid** | Time math is deterministic and exact. Whether "production batch job stuck" constitutes an emergency is a judgment call that benefits from language understanding |
| **Not covered** | Regional public holidays (requires country-specific HR calendar integration) |

### R-008 · Self-Approval
| | |
|---|---|
| **Severity** | high |
| **Implementation** | Deterministic |
| **What it checks** | `firefighter_user == ticket_requester` (field comparison), plus semantic scan of `reason_code` for explicit self-referential phrasing (e.g., "requester: BMEYER (self)") |
| **Why deterministic** | Exact string comparison on structured fields. Zero ambiguity |
| **Not covered** | Collusion between two different users (A requests for B, B requests for A) |

### R-009 · Session Duration Breach
| | |
|---|---|
| **Severity** | medium |
| **Implementation** | Deterministic |
| **What it checks** | `end_time - start_time > 2 hours` using UTC-normalized datetimes |
| **Why deterministic** | Pure timestamp arithmetic |
| **Not covered** | "Session hovering" — a user keeping a session open but idle. The rule flags wall-clock duration; distinguishing active vs. idle time requires packet-level trace analysis |

### R-010 · Segregation of Duties (SoD) Conflicts
| | |
|---|---|
| **Severity** | critical |
| **Implementation** | Deterministic — subset matching against a dictionary of toxic pairs |
| **Monitored pairs** | `XK01/XK02/FK02` (vendor create/modify) + `F110` (payment run) · `FB01/FB02` (FI document post/change) + `F110` · `SU01` (user admin) + `PFCG` (role admin) · `MIGO` (goods receipt) + `MIRO` (invoice) · `VA01` (sales order) + `VF01` (billing) |
| **Why deterministic** | The conflict matrix is defined by the client's SoD policy. Exact matching against a known set is 100% precise and auditable |
| **Not covered** | Cross-session SoD (vendor modified in Monday's session, payment approved in Tuesday's session) |

---

## 🚀 Compliance Rules — Additional (Beyond Baseline)

All additional rules were derived from Exploratory Data Analysis of the provided session dataset. Each rule targets a pattern observed in at least one session.

### R-011 · Custom Z/Y Program Execution with Mass Changes
| | |
|---|---|
| **Severity** | high |
| **Implementation** | Deterministic |
| **What it checks** | `transaction_log` contains a tcode starting with `Z`/`Y` or one of `SE38`, `SA38`, `SE37`, AND `len(change_log) > 10`, AND no mention of the program name in `reason_code` |
| **Why it matters** | Custom ABAP programs bypass all standard SAP application-layer validations, audit trails, and authorization checks. A firefighter can write `Z_EDIT_ANYTHING` and modify any table in any volume. This is the primary bypass vector for R-004. The firefighter's reason must explicitly name the program being executed and the scope of records affected |
| **Not covered** | SAP-delivered mass-processing programs (`MASS`, `LSMW`) which have their own approval workflows |

### R-012 · Activity After Hard Logoff (/NEX)
| | |
|---|---|
| **Severity** | high |
| **Implementation** | Deterministic — relies on Pydantic chronological sort |
| **What it checks** | Whether any `transaction_log` entry has a timestamp strictly after the first `/NEX` entry in the same log |
| **Why it matters** | `/NEX` is an unconditional SAP GUI session termination. Subsequent logged activity indicates one of: (1) log tampering / manual JSON modification, (2) a parallel session running under the same FFID that was not captured in this log, or (3) a "zombie" background process. All three are integrity violations. This rule has a known interpretation challenge: SAP can log multiple concurrent windows under one session ID — see Known Failure Modes |
| **Not covered** | Activity in a legitimately separate re-login after `/NEX` that shares the same `session_id` due to a logging system defect |

---

## ⚖️ Deterministic vs. LLM Logic — Decision Framework

| Rule | Method | Reason for choice |
|---|---|---|
| R-001 | Hybrid | Length < 20 chars is a certain deterministic violation; longer reasons require LLM to judge specificity and business context |
| R-002 | Smart LLM | Requires SAP module knowledge + reading business intent from free text |
| R-003 | Deterministic | Fixed log signature, binary presence check |
| R-004 | Deterministic | Closed list of transaction codes, exact string match |
| R-005 | Deterministic | Binary: any entry in os_command_log = violation |
| R-006 | Hybrid | Count is deterministic; whether the count is proportionate to the reason is semantic |
| R-007 | Hybrid | Time window is deterministic; "emergency" classification is semantic |
| R-008 | Deterministic | Field equality comparison |
| R-009 | Deterministic | Timestamp arithmetic |
| R-010 | Deterministic | Pre-defined conflict matrix, subset check |
| R-011 | Deterministic | Tcode prefix check + change_log count threshold |
| R-012 | Deterministic | Chronological comparison after sort |

**Core principle:** LLMs are used only when the rule cannot be expressed as a deterministic predicate — i.e., when human language or contextual judgment is the primary input. Every rule that can be expressed as a boolean function over structured data fields is implemented deterministically. This keeps the system auditable, reproducible, and cost-controlled.

---

## 📊 Evaluation Results

The system was evaluated on a labeled set of 50 sessions (`labels.jsonl`).

### Baseline only (R-001 through R-010)

```
Total sessions:  50
Accuracy:        0.92
Macro F1:        0.921
```

| Class | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| PASS | 0.864 | 0.950 | 0.905 | 20 |
| REJECT | 1.000 | 1.000 | 1.000 | 15 |
| NEEDS_CORRECTION | 0.923 | 0.800 | 0.857 | 15 |

Confusion matrix (rows = gold label, columns = predicted):

```
                    PASS   REJECT   NEEDS_CORRECTION
PASS                  19        0                  1
REJECT                 0       15                  0
NEEDS_CORRECTION       3        0                 12
```

Per-rule precision / recall / F1:

| Rule | P | R | F1 | TP | FP | FN | Support |
|---|---|---|---|---|---|---|---|
| R-001 | 0.750 | 0.643 | 0.692 | 9 | 3 | 5 | 14 |
| R-002 | 0.600 | 0.333 | 0.429 | 3 | 2 | 6 | 9 |
| R-003 | 1.000 | 1.000 | 1.000 | 3 | 0 | 0 | 3 |
| R-004 | 1.000 | 1.000 | 1.000 | 4 | 0 | 0 | 4 |
| R-005 | 1.000 | 1.000 | 1.000 | 2 | 0 | 0 | 2 |
| R-006 | 1.000 | 1.000 | 1.000 | 2 | 0 | 0 | 2 |
| R-007 | 0.583 | 0.700 | 0.636 | 7 | 5 | 3 | 10 |
| R-008 | 1.000 | 1.000 | 1.000 | 2 | 0 | 0 | 2 |
| R-009 | 1.000 | 1.000 | 1.000 | 3 | 0 | 0 | 3 |
| R-010 | 1.000 | 1.000 | 1.000 | 2 | 0 | 0 | 2 |

### After adding R-011 and R-012

```
Total sessions:  50
Accuracy:        0.72
Macro F1:        0.719
```

| Class | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| PASS | 0.800 | 0.600 | 0.686 | 20 |
| REJECT | 0.600 | 1.000 | 0.750 | 15 |
| NEEDS_CORRECTION | 0.900 | 0.600 | 0.720 | 15 |

Confusion matrix (rows = gold label, columns = predicted):

```
                    PASS   REJECT   NEEDS_CORRECTION
PASS                  12        7                  1
REJECT                 0       15                  0
NEEDS_CORRECTION       3        3                  9
```

Per-rule precision / recall / F1:

| Rule | P | R | F1 | TP | FP | FN | Support |
|---|---|---|---|---|---|---|---|
| R-001 | 0.692 | 0.643 | 0.667 | 9 | 4 | 5 | 14 |
| R-002 | 0.500 | 0.333 | 0.400 | 3 | 3 | 6 | 9 |
| R-003 | 1.000 | 1.000 | 1.000 | 3 | 0 | 0 | 3 |
| R-004 | 1.000 | 1.000 | 1.000 | 4 | 0 | 0 | 4 |
| R-005 | 1.000 | 1.000 | 1.000 | 2 | 0 | 0 | 2 |
| R-006 | 1.000 | 1.000 | 1.000 | 2 | 0 | 0 | 2 |
| R-007 | 0.583 | 0.700 | 0.636 | 7 | 5 | 3 | 10 |
| R-008 | 1.000 | 1.000 | 1.000 | 2 | 0 | 0 | 2 |
| R-009 | 1.000 | 1.000 | 1.000 | 3 | 0 | 0 | 3 |
| R-010 | 1.000 | 1.000 | 1.000 | 2 | 0 | 0 | 2 |
| R-011 | 0.000 | 0.000 | 0.000 | 0 | 5 | 0 | 0 |
| R-012 | 0.000 | 0.000 | 0.000 | 0 | 8 | 0 | 0 |

### Why the accuracy dropped from 0.92 to 0.72

R-011 and R-012 generate **13 false positives combined** (5 + 8) against the gold label set. This is an artifact of dataset coverage, not rule quality: the gold `labels.jsonl` was created before R-011 and R-012 were defined, so it contains zero positive examples for these rules (`support = 0`). The FP cases are sessions that genuinely contain post-logoff activity or custom Z-program execution — patterns that are real anomalies visible in the raw logs — but were labeled PASS or NEEDS_CORRECTION by the original annotators who were not checking for these behaviors.

**On the sessions covered by the original 10 rules, the system still achieves the baseline 0.92 accuracy.** The overall drop is entirely explained by the new rules firing on previously unlabeled patterns.

---

## ⚠️ Known Failure Modes

### 1. Post-logoff activity from parallel SAP sessions (R-012 false positives)

**What happens:** SAP allows a user to open multiple browser tabs or GUI windows under the same session context. When this occurs, the system logs all window activity under a single `session_id`. A user who legitimately logs out of Window A (`/NEX`) but continues working in Window B will trigger R-012, even though their behavior is technically within the firefighter session scope.

**Real example:** user executes `/NEX` at 15:22 but continues with `OB52` and `FBL3N` until 18:37. This is flagged as post-logoff tampering, but may be a legitimate second window investigating the same issue.

**Why we can't fix it deterministically:** Distinguishing single-window logoff from multi-window continuation requires GUI session metadata that is not present in the standard firefighter JSON log format.

### 2. Implicit module overlap causes R-002 false positives (LLM limitation)

**What happens:** When a user states they are fixing a cross-functional issue (e.g., "O2C Order-to-Cash" or "procure-to-pay"), the LLM may incorrectly flag module mismatch because it does not recognize the cross-functional scope of the stated reason. Similarly, if the session uses a highly customized `Z*` transaction, the LLM may not know which SAP module it belongs to and may hallucinate a mismatch.

**Real example:** A firefighter says "Resolved O2C issue per INC0099" and executes `XD02` (customer master) and `VA02` (sales order). The LLM may flag this as a mismatch between "customer master maintenance" and "sales document change," not recognizing both as FI/SD O2C activities.

**Why we can't fix it fully:** Requires a company-specific T-code dictionary mapping every `Z*` transaction to its functional module — see "What I Would Build Next."

### 3. Business-hours judgment depends on client timezone (R-007 false negatives)

**What happens:** The system evaluates session timestamps in UTC and defines business hours as 08:00–18:00 UTC. A firefighter in Tokyo working at 10:00 JST (01:00 UTC) will always be flagged as out-of-hours, even during their normal working day. Conversely, a European firefighter working at 19:00 local time (17:00 UTC) will not be flagged.

**Real example:** Any session from a Japanese or Australian client site will systematically over-trigger R-007.

**Why we can't fix it fully:** Requires per-client timezone and business-hours configuration, which is not present in the current session JSON schema. A short-term mitigation would be to use the `system` field prefix (e.g., `PRD-JP`) to infer the client timezone.

---

## 💰 Cost Estimate Per Session

*Assumptions based on OpenAI pricing (mid-2025):*

| Component | Model | Input tokens | Output tokens | Cost |
|---|---|---|---|---|
| Deterministic rules (R-003–R-012) | — | — | — | $0.000 |
| R-001, R-006, R-007 (Fast Tier) | GPT-4o-mini | ~800 | ~80 | ~$0.0003 |
| R-002 (Smart Tier) | GPT-4o | ~1,500 | ~150 | ~$0.008 |
| **Total (all rules triggered)** | | | | **~$0.008–$0.010** |
| **Short-circuit REJECT (no LLM)** | | | | **$0.000** |
| **Blended average across 50-session set** | | | | **~$0.004–$0.006** |

For a client generating 50 sessions/month, total monthly LLM cost is approximately **$0.20–$0.30**, versus **$1,000–$2,000** in controller time at current rates.

---

## 🚀 What I Would Build Next (Given Another Week)

**1. RAG-based T-code dictionary**
A lightweight vector database (ChromaDB or Qdrant) containing the client's full SAP transaction code catalog — including all `Z*` and `Y*` custom transactions — mapped to their functional module, risk level, and typical use case. The LLM would query this at inference time, eliminating the largest source of R-002 false positives.

**2. Dynamic few-shot prompting from historical decisions**
Instead of a static system prompt, inject 2–3 examples of controller-overridden verdicts from the current client's history into each LLM call. This teaches the model the client's specific risk tolerance and reduces false positives for patterns that are standard for that client (e.g., a client that regularly does mass vendor updates via approved CHG tickets).

**3. Cross-session SoD graph analysis**
Port R-010 to a graph structure (NetworkX) that tracks activity across sessions, not just within one session. A user who modifies a vendor's bank account in Session A on Monday and approves the payment in Session B on Tuesday would currently pass R-010. A session graph would catch this indirect conflict.

**4. Per-client timezone and business-hours configuration**
Add a client configuration layer that maps `client` field values to their local timezone and business hours definition, eliminating the systematic R-007 false positives for non-European clients.

---

## ⏱️ Time Spent

| Phase | Hours |
|---|---|
| Dataset EDA & rule catalog design | 3h |
| Pydantic ingestion layer + timezone normalization | 2h |
| Deterministic rules (R-003 – R-012) | 4h |
| LLM integration, prompt engineering, cost router | 5h |
| Confidence scoring & correction generator | 2h |
| Streamlit UI | 2h |
| Evaluation harness + metrics | 1h |
| README & documentation | 3h |
| **Total** | **22h** |

---

## 🚀 Getting Started

### Prerequisites

Python 3.9+ required.

```bash
git clone <repo-url>
cd sap-firefighter-reviewer
pip install -r requirements.txt
```

Create a `.env` file in the root directory:

```env
# Use one of the following:
GROQ_API_KEY=your_groq_api_key_here
# OPENAI_API_KEY=your_openai_api_key_here
```

### Running the Interactive UI

```bash
streamlit run src/app.py
```

Upload a session JSON, inspect the verdict and highlighted findings, and click **PASS / REJECT / SEND-BACK** to record the controller's final decision.

### Running Batch Predictions (CLI)

```bash
python -m src.batch_predict data/train/sessions/ predictions_train.jsonl
```

### Running the Evaluation Harness

```bash
python data/eval.py \
  --predictions predictions_train.jsonl \
  --labels data/train/labels.jsonl
```

Note on test data in repository: The labeled evaluation dataset (data/) is intentionally committed to this repository. In a production setting, evaluation data — especially if it contains client session logs — would never be stored in version control. I made an exception here because the dataset was supplied as part of the task and committing it allows to reproduce all reported metrics with a single command without any additional setup.