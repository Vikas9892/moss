"""Edge cases and documented-error checks for the Inference API. Each row: expected vs actual."""
import concurrent.futures as cf
import requests
from common import AUTH, BASE, PID, RESULTS, call, err_code, md_table

FAST = "moss/fastlane-1"
MSG = [{"role": "user", "content": "hi"}]
CHAT = lambda **kw: {"model": FAST, "messages": MSG, "max_tokens": 5, **kw}

# (name, path, body, extra headers, use_auth, expected status, expected code or "")
CASES = [
    ("no auth header", "/chat/completions", CHAT(), {}, False, 401, ""),
    ("wrong key", "/chat/completions", CHAT(), {"Authorization": f"Bearer {PID}:wrongkey"}, True, 401, ""),
    ("bearer without colon", "/chat/completions", CHAT(), {"Authorization": f"Bearer {PID}"}, True, 401, ""),
    ("unknown model", "/chat/completions", CHAT(model="moss/nope-9"), {}, True, 400, "model_not_found"),
    ("empty messages", "/chat/completions", CHAT(messages=[]), {}, True, 400, ""),
    ("messages missing", "/chat/completions", {"model": FAST}, {}, True, 400, ""),
    ("unknown top-level field (chat)", "/chat/completions", CHAT(foo=1), {}, True, 400, ""),
    ("max_tokens negative", "/chat/completions", CHAT(max_tokens=-5), {}, True, 400, ""),
    ("max_tokens 10M (> 262k window)", "/chat/completions", CHAT(max_tokens=10_000_000), {}, True, 400, ""),
    ("temperature 5", "/chat/completions", CHAT(temperature=5), {}, True, 400, ""),
    ("n=3 (one choice only)", "/chat/completions", CHAT(n=3), {}, True, 400, ""),
    ("image part to fastlane (text only)", "/chat/completions",
     CHAT(messages=[{"role": "user", "content": [{"type": "image_url", "image_url": {"url": "https://upload.wikimedia.org/wikipedia/commons/4/47/PNG_transparency_demonstration_1.png"}}]}]),
     {}, True, 400, ""),
    ("openai: seed refused", "/chat/completions", CHAT(model="openai/gpt-6-luna", seed=1), {}, True, 400, "unsupported_parameter"),
    ("anthropic: temperature refused", "/chat/completions", CHAT(model="anthropic/claude-haiku-5.5", temperature=0.2), {}, True, 400, "unsupported_parameter"),
    ("anthropic: json_object refused", "/chat/completions", CHAT(model="anthropic/claude-haiku-5.5", response_format={"type": "json_object"}), {}, True, 400, "unsupported_parameter"),
    ("temperature=1 counts as unset (anthropic)", "/chat/completions", CHAT(model="anthropic/claude-haiku-5.5", temperature=1), {}, True, 200, ""),
    ("nonexistent index", "/chat/completions", CHAT(), {"X-Moss-Indexes": "definitely-not-an-index-xyz"}, True, 403, ""),
    ("33 indexes (max 32)", "/chat/completions", CHAT(), {"X-Moss-Indexes": ",".join(f"i{i}" for i in range(33))}, True, 400, ""),
    ("empty index names ',,,'", "/chat/completions", CHAT(), {"X-Moss-Indexes": ",,,"}, True, 400, ""),
    ("path-like index name", "/chat/completions", CHAT(), {"X-Moss-Indexes": "../../etc"}, True, 403, ""),
    ("X-Moss-Retrieve: banana", "/chat/completions", CHAT(), {"X-Moss-Retrieve": "banana"}, True, 400, ""),
    ("BYOK garbage provider key (openai)", "/chat/completions", CHAT(model="openai/gpt-6-luna"), {"X-Moss-Provider-Key": "sk-garbage"}, True, 401, ""),
    ("BYOK key on fastlane", "/chat/completions", CHAT(), {"X-Moss-Provider-Key": "sk-garbage"}, True, 400, ""),
    ("responses: previous_response_id", "/responses", {"model": FAST, "input": "hi", "previous_response_id": "resp_123"}, {}, True, 400, ""),
    ("responses: background=true", "/responses", {"model": FAST, "input": "hi", "background": True}, {}, True, 400, ""),
    ("responses: OpenAI built-in web_search tool", "/responses", {"model": FAST, "input": "hi", "tools": [{"type": "web_search"}]}, {}, True, 400, ""),
    ("responses: unknown field", "/responses", {"model": FAST, "input": "hi", "foo": 1}, {}, True, 400, ""),
    ("mcp tool with http (not https) url", "/responses",
     {"model": FAST, "input": "hi", "tools": [{"type": "mcp", "server_label": "x", "server_url": "http://example.com/mcp"}]}, {}, True, 400, ""),
    ("mcp tool pointing at localhost (SSRF probe)", "/responses",
     {"model": FAST, "input": "hi", "tools": [{"type": "mcp", "server_label": "x", "server_url": "https://127.0.0.1/mcp"}]}, {}, True, 400, ""),
]


def main():
    rows = []
    for name, path, body, hdr, use_auth, exp_s, exp_c in CASES:
        h = {**(AUTH if use_auth else {}), **hdr}
        s, b, _, ms = call("POST", path, "edge_" + name.replace(" ", "_")[:40], headers=h, auth=False, json=body)
        code = err_code(b)
        msg = (b.get("error") or {}).get("message", "")[:90] if isinstance(b, dict) and isinstance(b.get("error"), dict) else ""
        ok = s == exp_s and (not exp_c or exp_c == code)
        rows.append([name, f"{exp_s} {exp_c}".strip(), f"{s} {code}".strip(), "ok" if ok else "**MISMATCH**", msg])
        print(rows[-1], flush=True)

    # oversized body (>4MB) -> 413
    s, b, _, _ = call("POST", "/chat/completions", "edge_413", headers={"Content-Type": "application/json"},
                      raw=('{"model":"%s","messages":[{"role":"user","content":"%s"}]}' % (FAST, "a" * 4_300_000)).encode())
    rows.append(["body 4.3 MB", "413", f"{s} {err_code(b)}", "ok" if s == 413 else "**MISMATCH**", ""])

    # context window: ~300k tokens to fastlane (262,144 limit); ~1.3 MB, under body cap
    s, b, _, ms = call("POST", "/chat/completions", "edge_ctx", json=CHAT(messages=[{"role": "user", "content": "word " * 300_000}]))
    rows.append(["~300k-token prompt to fastlane", "400 context_length_exceeded", f"{s} {err_code(b)}",
                 "ok" if err_code(b) == "context_length_exceeded" else "**MISMATCH**", f"{ms:.0f} ms to reject"])

    # burst: 25 parallel fastlane requests (documented burst 10) -> expect some 429 + Retry-After
    def hit(_):
        r = requests.post(BASE + "/chat/completions", headers=AUTH, json=CHAT(), timeout=60)
        return r.status_code, r.headers.get("Retry-After")
    with cf.ThreadPoolExecutor(25) as ex:
        res = list(ex.map(hit, range(25)))
    n429 = sum(1 for s, _ in res if s == 429)
    ra = {r for s, r in res if s == 429}
    rows.append(["25 parallel requests (burst 10)", "some 429 w/ Retry-After",
                 f"{n429}x429, {sum(1 for s, _ in res if s == 200)}x200, Retry-After={ra or '-'}",
                 "ok" if n429 and all(ra) else "**MISMATCH**", str(sorted(s for s, _ in res))])

    (RESULTS / "edge.md").write_text("## Inference API edge cases\n" + md_table(["case", "expected", "actual", "", "error message"], rows), encoding="utf-8")


if __name__ == "__main__":
    main()
