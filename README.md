# Moss Inference: hands-on review

**One-page report:** [ONE_PAGER.md](ONE_PAGER.md) · [PDF](Moss_Review_Vikas_Tiwari.pdf)

Everything here was run against `https://inference.moss.dev/v1` on 2026-11-25 from Pune, India
(â‰ˆ34 ms round trip to the API edge). Raw request/response JSON for every call is in `logs/` (auth redacted).
Result tables are in `results/` and combined in [`results/REPORT.md`](results/REPORT.md).

## Run it

```bash
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt
cp .env.example .env            # add MOSS_PROJECT_ID / MOSS_PROJECT_KEY
.venv/Scripts/python run_all.py # or one script: inference_compat, inference_edge, inference_latency,
                                #   inference_retrieval, tasks_break, tasks_real
```
Each browser task is capped at `TASK_COST_CAP` ($0.25), and the run stops when task spending reaches `SPEND_CAP_USD` ($6).
The full run spent about $0.50 on tasks plus a few cents on inference.

| Script | What it checks |
|---|---|
| `inference_compat.py` | Stock OpenAI SDK, with only base_url and key changed: models, chat, streaming, tools, tool round-trip, json_schema, Responses (13 checks) |
| `inference_edge.py` | 32 bad or edge inputs, each against the documented error, plus a 25-request burst against the rate limit |
| `inference_latency.py` | Streaming TTFT and total time, 20 runs Ã— 5 models over a keep-alive connection; reply-cache effect |
| `latency_sysprompt_check.py` | Does `X-Moss-System-Prompt: off` change fastlane TTFT? |
| `network_rtt.py` | Baseline round trip (`GET /models`) so TTFT can be separated from network time |
| `inference_retrieval.py` | Index of 10 fictional facts; 11 questions with and without `X-Moss-Indexes`, auto-graded |
| `index_buildtime.py` | Real index build time and job status fields |
| `tasks_break.py` | 18 validation cases, auth, idempotency, cancel (early and while running), files, path traversal, budget and runtime enforcement, queue cap |
| `tasks_real.py` | Graded browser tasks: Wikipedia on fast, balanced and advanced; multi-page shop; login form; impossible goal; prompt injection; unsatisfiable schema |

## Headline results

**Inference API**
- **Drop-in compatibility: 13/13 pass.** The stock OpenAI SDK worked for chat, streaming, tools (including a tool-result round trip), `json_schema` and Responses on fastlane, GPT, Claude and Gemini.
- **Retrieval works very well.** With the index attached, fastlane and Claude Haiku each answered **11/11** correctly, against **1/11 and 0/11** without it. `X-Moss-Retrieve-Ms` was **10 ms**, and total latency went *down* with the index (fastlane 587 â†’ 569 ms p50).
- **fastlane is the fastest model tested, but it doesn't meet "under 200 ms TTFT" from India.** TTFT p50 was **486 ms** (p95 603) over a reused connection with a 34 ms network round trip, so roughly 450 ms is spent server-side. The vendor models measured 1.1â€“1.4 s p50.
  Turning `X-Moss-System-Prompt` off made no difference (p50 about 450 ms either way).
- **The reply cache doesn't speed up fastlane.** A repeated prompt on gpt-6-luna went from 1522 ms to 525 ms; on fastlane it went from 479 ms to 522 ms.
- **gemini-3.5-flash-lite is not really streamed**: TTFT â‰ˆ total time (1378 / 1395 ms), and p95 was 6.2 s.
- **Index builds are fast** (10 docs in 3.4 s server-side), but the portal says builds take "a few minutes".

**Tasks API**
- **All 6 graded tasks came back correct**, counting one my grader initially got wrong (see below): Wikipedia lookup (all 3 tiers), multi-page shop, login form, and resisting a prompt injection ("RED-99" planted in page text; the agent reported the real code).
- **moss-fast gave the same correct answer at about a tenth of the cost**: $0.006 and 22 s, against $0.064/47 s on balanced and $0.067/25 s on advanced. balanced was *slower* than advanced on this task (one run each).
- **Validation is excellent: 18/18 bad bodies rejected with precise messages.** That includes `file:///etc/passwd` and `javascript:` start URLs. Idempotency behaves exactly as documented, and path traversal on `/files` returns 404.

## Bugs and mismatches found

| # | Area | What happened | Evidence |
|---|---|---|---|
| 1 | Tasks | **`max_cost_usd: 0.01` was overspent 2.4Ã—**: `model_usd` reached $0.0238 before `budget_exceeded`. The cap seems to be checked only after a model call finishes. | `results/tasks_break.md`, `logs/*task_final_lim_budget*` |
| 2 | Tasks | **The 20-task queue cap isn't enforced**: 22 rapid creates all returned 202 with `status: queued`, and none got 429 `too_many_queued_tasks`. | `logs/*tb_q*.json` |
| 3 | Tasks | **A failed schema still reports `status: completed`.** A schema that can't be satisfied (`minimum: 100, maximum: 10`) was accepted at creation, the agent spent 41 s and 5 steps on it, and the task ended `completed` with `verification.passed: false`. Code that only checks status treats it as success. This matches the docs, but the docs make it easy to miss. | `results/tasks_real.md` |
| 4 | Tasks | **An impossible goal ends `completed` with a refusal text**, not `failed: no_answer`. The agent also refused on privacy grounds instead of saying the site has no such information. | `logs/*task_final_impossible*` |
| 5 | Tasks | Cancelling immediately after create: the task was already `running`, took 18 s to reach `cancelled`, and was billed $0.004. | `results/tasks_break.md` |
| 6 | Index | **Creating a 4th index failed with "usage limit has been reached; billing must be updated"** although credits remained and inference still worked. Deleting one index fixed it immediately, so this looks like an index-count limit with a billing error message. | run transcript; `index_buildtime.py` |
| 7 | Inference | **Chat Completions silently accepts unknown fields** (`foo: 1` â†’ 200), while Responses rejects them (`400 foo is not supported`). Typos like `max_token` go unnoticed. | `results/edge.md` |
| 8 | Inference | **Bad Moss headers are silently ignored**: `X-Moss-Indexes: ",,,"` â†’ 200, `X-Moss-Retrieve: banana` â†’ 200, `X-Moss-Provider-Key` on fastlane â†’ 200. | `results/edge.md` |
| 9 | Inference | The 32-index limit: 33 copies of one real index â†’ 200 (not enforced on duplicates); 33 unknown names â†’ 403, not the documented 400. Existence is checked before the count. | `results/edge.md` + manual retest |
| 10 | Inference | Misleading errors: Claude + `json_object` says "response_format is not supported", but `json_schema` works fine. A bad BYOK key says "The model rejected the prompt". | `results/edge.md` |
| 11 | Inference | Internal serving-engine wording leaks into errors: "max_model_len=262144", "At most 0 image(s) may be provided in one prompt". | `results/edge.md` |
| 12 | Inference | Over 4 MB, the server returns 413 but closes the connection before reading the body, so Python `requests` sees `ConnectionAbortedError` instead of a 413 (curl gets 413 with exit 55). | `logs/*edge_413*` |
| 13 | SDK | Python SDK `JobStatus` and `IndexInfo` print as `<builtins.JobStatus object at 0xâ€¦>`, so status can't be inspected without reading the source. | `index_buildtime.py` |
| 14 | Docs | `docs.usemoss.dev` serves an expired TLS certificate; the docs now live at `docs.moss.dev`. | â€” |

Things that worked exactly as documented: auth errors, unknown model, parameter ranges (with very clear messages naming the parameter, value and allowed range), refused vendor parameters, `previous_response_id`/`background`/built-in tools rejected, MCP `http://` and `127.0.0.1` URLs rejected (SSRF guard), rate limiting (exactly 10 of 25 burst requests succeeded, the rest got 429 with `Retry-After: 1`), context-length rejection in 0.9 s, files 409 before finish, cancel and idempotency semantics.

## Caveats
- The latency numbers come from one location (India) on one evening, 20 runs per model. The "under 200 ms" claim may hold closer to Moss's servers or "on supported workloads".
- The task comparisons are n = 1 per tier.
- The `impossible_goal` row in `results/tasks_real.md` shows FAIL from the first run because the grader missed the curly apostrophe in "canâ€™t". The grader is fixed; the agent's actual output is quoted in the table.
