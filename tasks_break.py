"""Try to break the Tasks API: validation, idempotency, cancel, files, limits enforcement, queue cap."""
import json, time, uuid
import requests
from common import AUTH, BASE, RESULTS, call, create_task, err_code, log, md_table, wait_task

OK_BODY = lambda **kw: {"goal": "Open example.com and return the main heading.", "environment": {"type": "browser", "start_url": "https://example.com"},
                        "model": "moss-fast", "limits": {"max_runtime_seconds": 120, "max_cost_usd": 0.05}, **kw}
rows = []
created = []  # every task we start, to cancel on exit


def row(name, expected, actual, ok, note=""):
    rows.append([name, expected, actual, "ok" if ok else "**MISMATCH**", note]); print(rows[-1], flush=True)


def post(name, body, headers=None, raw=None):
    s, b, h, ms = call("POST", "/tasks", "tb_" + name, headers=headers, raw=raw, json=None if raw else body)
    if s == 202 and isinstance(b, dict) and b.get("id"):
        created.append(b["id"])
    return s, b, h


def validation():
    bad = {
        "missing goal": {k: v for k, v in OK_BODY().items() if k != "goal"},
        "empty goal": OK_BODY(goal=""),
        "goal 20,001 chars": OK_BODY(goal="x" * 20_001),
        "environment.type=desktop": OK_BODY(environment={"type": "desktop"}),
        "start_url ftp://": OK_BODY(environment={"type": "browser", "start_url": "ftp://example.com"}),
        "start_url javascript:": OK_BODY(environment={"type": "browser", "start_url": "javascript:alert(1)"}),
        "start_url file:///etc/passwd": OK_BODY(environment={"type": "browser", "start_url": "file:///etc/passwd"}),
        "max_runtime 59": OK_BODY(limits={"max_runtime_seconds": 59, "max_cost_usd": 0.05}),
        "max_runtime 7201": OK_BODY(limits={"max_runtime_seconds": 7201, "max_cost_usd": 0.05}),
        "max_cost 0": OK_BODY(limits={"max_runtime_seconds": 120, "max_cost_usd": 0}),
        "max_cost 50.01": OK_BODY(limits={"max_runtime_seconds": 120, "max_cost_usd": 50.01}),
        "max_cost as string": OK_BODY(limits={"max_runtime_seconds": 120, "max_cost_usd": "0.05"}),
        "effort=extreme": OK_BODY(effort="extreme"),
        "unknown model": OK_BODY(model="moss-ultra"),
        "unknown top-level field": OK_BODY(foo=1),
        "output_schema type array": OK_BODY(output_schema={"type": "array"}),
        "output_schema not valid JSON Schema": OK_BODY(output_schema={"type": "object", "properties": {"a": {"type": "banana"}}}),
        "metadata 5 KB": OK_BODY(metadata={"x": "y" * 5000}),
    }
    for name, body in bad.items():
        s, b, _ = post(name.replace(" ", "_")[:30], body)
        row(f"validation: {name}", "400", f"{s} {err_code(b)}", s == 400, (b.get("error") or {}).get("message", "")[:80] if isinstance(b, dict) and isinstance(b.get("error"), dict) else "")
    s, b, _ = post("body_300KB", None, headers={"Content-Type": "application/json"},
                   raw=json.dumps(OK_BODY(metadata={"x": "y" * 300_000})).encode())
    row("validation: body 300 KiB", "413", f"{s} {err_code(b)}", s == 413)
    s, b, _, _ = call("POST", "/tasks", "tb_noauth", auth=False, json=OK_BODY())
    row("no auth", "401", f"{s} {err_code(b)}", s == 401)
    s, b, _, _ = call("GET", "/tasks/task_" + "0" * 32, "tb_get_missing")
    row("GET nonexistent task", "404", f"{s} {err_code(b)}", s == 404)
    s, b, _, _ = call("GET", "/tasks/not-a-task-id", "tb_get_malformed")
    row("GET malformed id", "400/404", f"{s} {err_code(b)}", s in (400, 404))


def idempotency():
    key = str(uuid.uuid4())
    s1, b1, h1 = post("idem_1", OK_BODY(), {"Idempotency-Key": key})
    s2, b2, h2 = post("idem_2", OK_BODY(), {"Idempotency-Key": key})
    same = b1.get("id") == b2.get("id")
    row("idempotency: same key+body", "same id, Idempotent-Replayed: true",
        f"{s1}/{s2} same_id={same} replayed={h2.get('Idempotent-Replayed')}", same and str(h2.get("Idempotent-Replayed")).lower() == "true")
    s3, b3, _ = post("idem_3", OK_BODY(goal="Different goal."), {"Idempotency-Key": key})
    row("idempotency: same key, new body", "422 idempotency_key_reused", f"{s3} {err_code(b3)}", s3 == 422)
    s4, b4, _ = post("idem_badkey", OK_BODY(), {"Idempotency-Key": "k" * 256})
    row("idempotency: 256-char key", "400", f"{s4} {err_code(b4)}", s4 == 400)
    return b1.get("id")


def files_and_cancel(task_id):
    s, b, _, _ = call("GET", f"/tasks/{task_id}/files", "tb_files_early")
    row("files before finish", "409 task_not_finished", f"{s} {err_code(b)}", s == 409)
    s, b, _, _ = call("POST", f"/tasks/{task_id}/cancel", "tb_cancel_early")
    row("cancel right after create", "cancelled (or cancel_requested)", f"{s} status={b.get('status')} cancel_requested={b.get('cancel_requested')}",
        s == 200 and (b.get("status") == "cancelled" or b.get("cancel_requested")))
    t, tl = wait_task(task_id, "cancel_early", timeout=180)
    row("  final state after early cancel", "cancelled", f"{t['status']} cost=${((t.get('usage') or {}).get('cost') or {}).get('total_usd')}", t["status"] == "cancelled", str(tl))
    s, b, _, _ = call("POST", f"/tasks/{task_id}/cancel", "tb_cancel_twice")
    row("cancel an already-cancelled task", "200, unchanged", f"{s} status={b.get('status')}", s == 200 and b.get("status") == "cancelled")
    s, b, _, _ = call("GET", f"/tasks/{task_id}/files", "tb_files_after")
    row("files after finish", "200 list", f"{s} {json.dumps(b)[:80]}", s == 200)
    s, b, _, _ = call("GET", f"/tasks/{task_id}/files/../../etc/passwd", "tb_files_traversal")
    row("files path traversal ../../etc/passwd", "404/400", f"{s} {err_code(b)}", s in (400, 404))


def cancel_running():
    s, b, _ = post("cancel_running", OK_BODY(goal="Browse books.toscrape.com and list every book title on the first 5 pages.",
                                              limits={"max_runtime_seconds": 600, "max_cost_usd": 0.25}))
    if s != 202:
        return row("cancel while running", "cancelled", f"create {s}", False)
    tid, t0 = b["id"], time.time()
    while time.time() - t0 < 120:
        st = requests.get(f"{BASE}/tasks/{tid}", headers=AUTH, timeout=30).json().get("status")
        if st == "running":
            break
        time.sleep(1)
    time.sleep(10)
    tc = time.time()
    call("POST", f"/tasks/{tid}/cancel", "tb_cancel_running")
    t, tl = wait_task(tid, "cancel_running", timeout=300)
    row("cancel while running", "cancelled soon after", f"{t['status']} after {time.time() - tc:.0f}s, cost=${((t.get('usage') or {}).get('cost') or {}).get('total_usd')}",
        t["status"] == "cancelled" and time.time() - tc < 60, str(tl))


def limits_enforced():
    for name, lim, expect in [("budget $0.01", {"max_runtime_seconds": 600, "max_cost_usd": 0.01}, "budget_exceeded"),
                              ("runtime 60s", {"max_runtime_seconds": 60, "max_cost_usd": 0.25}, "time_limit")]:
        s, b, _ = post("lim_" + name[:8], OK_BODY(model="moss-balanced", limits=lim,
                                                   goal="On books.toscrape.com visit every category and count the books in each. Return all counts."))
        if s != 202:
            row(f"limit: {name}", expect, f"create {s} {err_code(b)}", False); continue
        t, tl = wait_task(b["id"], "lim_" + name[:8], timeout=400)
        u = t.get("usage") or {}; c = u.get("cost") or {}
        dur = None
        if t.get("started_at") and t.get("finished_at"):
            dur = round(t["finished_at"] - t["started_at"]) if isinstance(t["started_at"], (int, float)) else f"{t['started_at']}→{t['finished_at']}"
        over = c.get("model_usd", 0) > lim["max_cost_usd"] * 1.05
        row(f"limit: {name}", f"failed {expect}, model_usd ≤ cap",
            f"{t['status']} {(t.get('error') or {}).get('code')} model_usd={c.get('model_usd')} total={c.get('total_usd')} runtime={dur}",
            (t.get("error") or {}).get("code") == expect and not over, str(tl))


def queue_cap():
    ids, codes = [], []
    for i in range(22):
        s, b, _ = post(f"q{i}", OK_BODY(limits={"max_runtime_seconds": 60, "max_cost_usd": 0.01}))
        codes.append(f"{s}{':' + err_code(b) if s != 202 else ''}")
        if s == 202:
            ids.append(b["id"])
    for tid in ids:
        requests.post(f"{BASE}/tasks/{tid}/cancel", headers=AUTH, timeout=30)
    n429 = sum(c.startswith("429") for c in codes)
    row("22 rapid creates (queue cap 20)", "429 too_many_queued_tasks after 20 queued", f"{codes.count('202')} accepted, {n429} rejected",
        n429 > 0, ", ".join(codes))


def main():
    try:
        validation()
        tid = idempotency()
        if tid:
            files_and_cancel(tid)
        cancel_running()
        limits_enforced()
        queue_cap()
    finally:
        for tid in created:  # never leave anything running on our credits
            requests.post(f"{BASE}/tasks/{tid}/cancel", headers=AUTH, timeout=30)
        (RESULTS / "tasks_break.md").write_text("## Tasks API: breaking it\n" + md_table(["test", "expected", "actual", "", "note"], rows), encoding="utf-8")


if __name__ == "__main__":
    main()
