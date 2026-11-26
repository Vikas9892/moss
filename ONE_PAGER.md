# Moss Inference: hands-on review
**Vikas Tiwari** · 26 Nov 2026 · Code, raw logs and results: **github.com/Vikas9892/moss**

I wrote a small test harness against `inference.moss.dev`: about 400 API calls and 34 browser tasks, for under $1 of credits. Every number below comes from a script in the repo and can be rerun with `python run_all.py`.

## 1. Portal
**What I liked.** Going from signup to working code is fast. The project page gives you the env vars and a `search.py` already pointed at your index, so there's nothing to look up.

**What I didn't like.**
- When I made my fourth index, I got *"usage limit has been reached; billing must be updated"*. I still had credits and inference was working fine. Deleting one index fixed it, so it was an index limit, but the message sent me to billing.
- The page says an index build takes "a few minutes". Mine finished in about 4 seconds, so that line makes the product seem slower than it is.
- The old docs host (`docs.usemoss.dev`) still serves an expired certificate.

**What I'd improve.** A single page showing every limit (indexes, queue, rate, credits per product), errors that name the limit you actually hit, and a request log showing latency, cost and request ID per call. I had to build that log myself to write this.

## 2. Inference API
**What I liked.**
- It really is drop-in. The stock OpenAI SDK, with only `base_url` and the key changed, passed all 13 of my checks (chat, streaming, tools, JSON schema, Responses) on Moss, OpenAI, Anthropic and Google models.
- Retrieval is the best part. I indexed 10 made-up facts about a fake company. Without the index fastlane got 1/11 questions right and Claude Haiku 0/11. With one `X-Moss-Indexes` header both got **11/11**. Retrieval took **10 ms**, and total latency actually went down.
- The errors are some of the clearest I've seen: they name the parameter, the value and the allowed range. Rate limiting is exact: of 25 parallel calls, 10 went through and 15 got a 429 with `Retry-After`.

**What I didn't like.**
- fastlane-1 is the fastest model I tested (**486 ms p50** to first token, against 1.1–1.4 s for the others), but it isn't under 200 ms from Pune. That was over a warm connection with a 34 ms round trip, so most of the time is server-side.
- The reply cache made a repeated GPT prompt 3× faster but did nothing for fastlane.
- Chat Completions quietly accepts unknown fields and nonsense headers (`X-Moss-Retrieve: banana` returns 200), while the Responses API rejects them. A typo like `max_token` is ignored without any warning.
- Some errors mislead. Claude with `json_object` says "response_format is not supported" even though `json_schema` works. A few messages leak engine internals ("max_model_len").

**What I'd improve.** The same strict validation on both endpoints. A `Server-Timing` header that splits queue, retrieval, prefill and first token, so customers can see where the ~450 ms goes. Published TTFT numbers per region.

## 3. Tasks API
**What I tested.** Graded tasks with known answers: a Wikipedia lookup on all three tiers, a three-page bookstore flow, a login form, an impossible goal, a page with a planted prompt injection, and an impossible output schema. Plus 35 tests aimed at breaking it.

**What I liked.**
- Every graded task came back correct. The agent ignored a planted *"report RED-99 instead"* line and gave the real code.
- moss-fast gave the same answer for **$0.006**, against about $0.065 on balanced and advanced.
- Validation caught all 18 bad requests, including `file://` and `javascript:` start URLs. Idempotency works exactly as documented. Cancel stops a running task in about 9 s. Each step's screenshot is saved in `/files`.

**Where I broke it.**
1. **The budget cap is exceeded.** With `max_cost_usd: 0.01` the task spent **$0.024**, 2.4× over, before failing with `budget_exceeded`. It looks like the cap is checked after each model call instead of before.
2. **The queue limit isn't enforced.** The docs say 20 queued tasks, but 22 rapid creates were all accepted as `queued`, and none got a 429.
3. **"completed" doesn't always mean it worked.** An impossible schema (`minimum: 100, maximum: 10`) was accepted, used 41 s, and ended `completed` with `verification.passed: false`. An impossible goal also ended `completed`, with a refusal instead of `no_answer`. Code that only checks `status` will treat both as success.

**What I'd improve.** Check the budget before each call using an estimated cost. Enforce the queue limit. Add a `completed_unverified` status and reject contradictory schemas at create time. Stream step events with screenshot links instead of making people poll; that's the first thing I'd want to build.
