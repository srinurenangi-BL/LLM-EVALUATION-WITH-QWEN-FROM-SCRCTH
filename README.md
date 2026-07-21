# Semester Code Submission Evaluator

Automated grading pipeline that evaluates student code submissions (from `Stage-1.xlsx`) against a mandated semester programming language, using a locally-hosted LLM (`qwen2.5-coder:7b-instruct` via Ollama) for grading.

---

## Overview

For each student submission, the pipeline:

1. Verifies the code is written in the semester's mandated language.
2. If it isn't → scores it `0` across all criteria, with no grading call made.
3. If it is → grades it for completeness, code quality, and approach using the LLM, and computes a weighted `overall_score`.
4. After all rows are processed, generates a class-wide summary (common errors, strengths, weaknesses, recommendations).

The mandated language is controlled by a single constant:

```python
SEMESTER_LANGUAGE = "Java"
```

---

## Why this isn't "just an LLM call"

A 7B-parameter local model is a capable grader, but it is **not reliable enough on its own** to also decide pass/fail on language compliance — asking one model to both judge language and produce exact structured scores compounds two different failure modes: misjudging edge-case code, and drifting from the required JSON format. To get this reliable, the pipeline separates those concerns into two isolated stages.

### Stage 1 — Deterministic Language Detection (no LLM involved)

Language compliance is decided **before** any grading call is made, using pure static analysis — no generative model, no hallucination risk:

1. **Regex signature matching** — each supported language has a weighted set of strong syntactic markers (e.g. Java: `public class`, `System.out.println(`; Python: `def ...():`, `self`; C++: `#include <iostream>`, `std::`). The submission is scored against every language's signature set.
2. **Pygments lexer fallback** — if the regex pass is inconclusive (low or tied scores), a secondary deterministic check using Pygments' lexer-guessing heuristic is used as a cross-check. Still not an LLM — a well-established, reproducible static analysis library.
3. **Manual review fallback** — if both signals are inconclusive (e.g. a 3-line snippet with no distinguishing syntax), the system does **not guess**. It's flagged for human review rather than risking a wrong auto-pass or auto-fail.

If the detected language doesn't match `SEMESTER_LANGUAGE`, the row is scored `0` with a fixed critical-failure message, and **the grading LLM call is skipped entirely** for that row.

### Stage 2 — Grading (LLM, but hardened)

Only code that passes the language gate reaches the LLM. That call is hardened in several ways:

| Safeguard | What it prevents |
|---|---|
| **JSON Schema–constrained decoding** (Ollama `format` as a schema, not just `"json"`) | The model is structurally prevented from omitting required fields or returning the wrong data type — enforced at the token-generation level. |
| **Post-decode validation** | Even schema-valid responses are checked for realistic values (scores within 0–10, non-empty feedback) before being accepted. |
| **Automatic retry (up to 2x)** | If validation fails, the model is re-prompted with the specific error instead of the invalid result being used. |
| **Adaptive self-consistency** | See below. |
| **Score arithmetic recomputed in Python** | `overall_score` is never trusted from the model — always recomputed from the three component scores via the fixed formula, so LLM arithmetic drift can never affect final grades. |

#### Adaptive self-consistency

Each submission is graded **once** by default. That single pass's `overall_score` is checked against a borderline band:

```python
BORDERLINE_SCORE_LOW  = 6.0
BORDERLINE_SCORE_HIGH = 9.0
```

- **Outside this band** (clearly strong or clearly weak) → the single pass is trusted, no extra compute spent.
- **Inside this band** → two additional passes are run and merged via **median** score, since single-pass noise near a grading cutoff is the case most likely to change the outcome. If the passes disagree by more than `SCORE_VARIANCE_FLAG_THRESHOLD` (2.5 points), the row is explicitly flagged `[FLAGGED FOR MANUAL REVIEW]` in the feedback rather than silently averaged away.

This keeps compute reasonable on modest hardware while still catching the noise that matters most — right around the pass/fail boundary — instead of paying a 3x cost on every row regardless of how clear-cut it is.

---

## What this guarantees vs. what it doesn't

**Guaranteed (structural/deterministic — cannot fail):**
- Language compliance decisions are 100% reproducible and hallucination-free.
- Output JSON always matches the required schema.
- Scores are always within valid range.
- `overall_score` arithmetic is always correct.
- Genuinely ambiguous code is flagged for humans instead of auto-graded incorrectly.

**Not guaranteed (inherent to any LLM, including larger ones):**
- The *qualitative accuracy* of grading judgment (e.g. catching a subtle logic bug) still depends on the model's coding ability. Self-consistency reduces random noise in scoring, but doesn't raise the model's underlying competence. For higher grading accuracy specifically, the only lever is a stronger model — this architecture makes the pipeline **reliable**, not the grading **smarter**.

---

## Model context window

`qwen2.5-coder:7b-instruct` natively supports a 32,768-token context window. However:

- **Ollama defaults `num_ctx` to 2048 tokens** unless explicitly overridden, which can silently truncate long prompts.
- This project sets `num_ctx` explicitly via `MODEL_MAX_CONTEXT` to avoid that.
- The value is tuned to the actual hardware running it, not the model's theoretical max — see below.

```python
MODEL_MAX_CONTEXT = 4096
```

Real prompts in this pipeline (master prompt + question + one code submission) run roughly 600–2000 tokens, so 4096 gives comfortable headroom without requiring more VRAM than a typical laptop GPU has available.

### Why not the full 32768?

On hardware with limited VRAM (e.g. a 4GB GPU), the 7B model's weights alone use most of the available VRAM. Pushing the KV cache to a 32K context on top of that forces Ollama to offload layers to CPU, which can turn a few-second grading call into a much slower one — especially painful when running an entire class batch. If you're running on a GPU with significantly more VRAM (12GB+), `MODEL_MAX_CONTEXT` can be raised safely.

---

## Setup

### Prerequisites
- Python 3.10+ (avoid brand-new Python releases like 3.14 until third-party packages catch up — you may hit `ModuleNotFoundError` issues even after `pip install` due to interpreter/venv path mismatches)
- [Ollama](https://ollama.com) installed and running locally
- The `qwen2.5-coder:7b-instruct` model pulled:
  ```bash
  ollama pull qwen2.5-coder:7b-instruct
  ```

### Install dependencies

```bash
pip install pandas requests pygments openpyxl
```

> If `pip install` reports a package as "already satisfied" but the script still raises `ModuleNotFoundError`, your terminal's `python`/`pip` are likely pointing at two different interpreters. Force it explicitly:
> ```bash
> python -m pip install <package>
> ```

### Input file

Place `Stage-1.xlsx` in the same directory as the script, with at minimum these columns:

| Column | Description |
|---|---|
| `QSN No` | Question number |
| `User ID` | Student identifier |
| `Question` | Question text |
| `Actual Code` | Student's submitted code |

---

## Usage

```bash
python evaluate_submissions.py
```

The script will:
1. Load and validate the spreadsheet.
2. Run the language gate + grading loop per row, printing live progress.
3. Generate and print a class-wide summary report at the end.

---

## Configuration reference

| Constant | Purpose | Default |
|---|---|---|
| `SEMESTER_LANGUAGE` | The single control point for the mandated language | `"Java"` |
| `MODEL_MAX_CONTEXT` | Ollama `num_ctx`, tuned to available hardware | `4096` |
| `BORDERLINE_SCORE_LOW` / `BORDERLINE_SCORE_HIGH` | Score band that triggers adaptive self-consistency rechecks | `6.0` – `9.0` |
| `BORDERLINE_RECHECK_RUNS` | Total passes (including the first) used for the median when a row is borderline | `3` |
| `SCORE_VARIANCE_FLAG_THRESHOLD` | Cross-run disagreement that triggers a manual-review flag | `2.5` |
| `MAX_RETRIES` | Retries on schema-invalid LLM responses | `2` |

---

## Known limitations

- Language detection signatures currently cover Java, Python, C, C++, C#, JavaScript, and TypeScript. Add more entries to `LANGUAGE_SIGNATURES` / `LANGUAGE_ALIASES` for other languages.
- Extremely short or minimal-syntax code snippets may be flagged for manual review rather than auto-classified — this is intentional (see Stage 1 above), not a bug.
- Grading quality is bounded by the underlying 7B model's coding judgment; this pipeline maximizes *reliability*, not raw grading intelligence.