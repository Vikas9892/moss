"""Streaming latency benchmark: time-to-first-token and total time per model, plus reply-cache effect."""
import json, os, sys, time
import requests
from common import AUTH, BASE, RESULTS, log, md_table, pct

MODELS = sys.argv[1:] or ["moss/fastlane-1", "openai/gpt-6-luna", "anthropic/claude-haiku-5.5",
                          "google/gemini-3.5-flash-lite", "deepseek/deepseek-v4.1-flash"]
N = int(os.environ.get("N", "20"))
SESSION = requests.Session()  # keep-alive, like a real client; fresh TLS per call added ~400 ms in our first run
TOPICS = ["hash map", "TCP handshake", "B-tree", "garbage collection", "CAP theorem", "mutex", "DNS",
          "Bloom filter", "gradient descent", "TLS", "load balancer", "consistent hashing", "LRU cache",
          "event loop", "vector database", "JWT", "rate limiter", "Kafka", "Raft", "CDN"]


def one(model, prompt, cache="off"):
    body = {"model": model, "messages": [{"role": "user", "content": prompt}], "stream": True,
            "max_tokens": 60, "stream_options": {"include_usage": True}}
    h = {**AUTH, "X-Moss-Cache": cache}
    t0 = time.perf_counter(); ttft = None; text = ""; usage = None; err = None; status = None; hdr = {}
    try:
        with SESSION.post(BASE + "/chat/completions", headers=h, json=body, stream=True, timeout=90) as r:
            status, hdr = r.status_code, dict(r.headers)
            if r.status_code != 200:
                err = r.text[:500]
            else:
                for line in r.iter_lines():
                    if not line.startswith(b"data: "):
                        continue
                    if line[6:] == b"[DONE]":
                        break
                    j = json.loads(line[6:])
                    if j.get("error"):
                        err = j["error"]
                    for c in j.get("choices") or []:
                        d = (c.get("delta") or {}).get("content")
                        if d:
                            ttft = ttft or (time.perf_counter() - t0) * 1000
                            text += d
                    usage = j.get("usage") or usage
    except requests.RequestException as e:
        err = repr(e)
    total = (time.perf_counter() - t0) * 1000
    rec = {"model": model, "prompt": prompt, "cache": cache, "status": status, "ttft_ms": ttft and round(ttft),
           "total_ms": round(total), "text": text, "usage": usage, "error": err,
           "x_moss_request_id": hdr.get("X-Moss-Request-Id") or hdr.get("x-moss-request-id")}
    return rec


def main():
    rows, all_recs = [], []
    for m in MODELS:
        one(m, "Say hi.")  # warm-up, excluded
        recs = []
        for i in range(N):
            recs.append(one(m, f"In one sentence, what is a {TOPICS[i % len(TOPICS)]}? (run {i})"))
            time.sleep(0.6)  # stay under fastlane burst limit
        all_recs += recs
        ok = [r for r in recs if r["status"] == 200 and not r["error"]]
        rows.append([m, f"{len(ok)}/{N}", pct([r["ttft_ms"] for r in ok], 50), pct([r["ttft_ms"] for r in ok], 95),
                     pct([r["total_ms"] for r in ok], 50), pct([r["total_ms"] for r in ok], 95)])
        print(rows[-1], flush=True)

    # reply cache: identical prompt twice with cache on
    cache_rows = []
    for m in MODELS[:2]:
        p = f"Name three prime numbers. nonce={int(time.time())}"
        a, b = one(m, p, "on"), one(m, p, "on")
        all_recs += [a, b]
        cache_rows.append([m, a["ttft_ms"], b["ttft_ms"], a["total_ms"], b["total_ms"], a["text"] == b["text"]])

    log("latency_all", all_recs)
    md = ["## Streaming latency (chat/completions, max_tokens=60, X-Moss-Cache: off, sequential, client in India)",
          md_table(["model", "ok", "TTFT p50 ms", "TTFT p95 ms", "total p50 ms", "total p95 ms"], rows),
          "", "## Reply cache (same prompt twice, X-Moss-Cache: on)",
          md_table(["model", "TTFT 1st", "TTFT 2nd", "total 1st", "total 2nd", "identical text"], cache_rows)]
    (RESULTS / "latency.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
