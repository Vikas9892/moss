"""Shared helpers: config, logged HTTP calls, task polling, spend guard."""
import json, os, pathlib, statistics, time
import requests

ROOT = pathlib.Path(__file__).parent
LOGS = ROOT / "logs"; LOGS.mkdir(exist_ok=True)
RESULTS = ROOT / "results"; RESULTS.mkdir(exist_ok=True)

env = ROOT / ".env"
if env.exists():
    for line in env.read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"'))

PID = os.environ["MOSS_PROJECT_ID"]
PKEY = os.environ["MOSS_PROJECT_KEY"]
BASE = os.environ.get("MOSS_BASE", "https://inference.moss.dev/v1")
AUTH = {"Authorization": f"Bearer {PID}:{PKEY}"}
SPEND_CAP = float(os.environ.get("SPEND_CAP_USD", "6"))  # stop task tests before credits run dry


def redact(h):
    return {k: "<redacted>" if k.lower() in ("authorization", "x-moss-provider-key") else v for k, v in h.items()}


def log(name, data):
    name = "".join(c if c.isalnum() or c in "-_." else "_" for c in name)[:60]  # Windows-safe
    p = LOGS / f"{time.strftime('%Y%m%d-%H%M%S')}_{name}.json"
    p.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    return p


def call(method, path, name, headers=None, auth=True, raw=None, **kw):
    """One logged HTTP call. Returns (status, body, headers, ms)."""
    h = {**(AUTH if auth else {}), **(headers or {})}
    t = time.perf_counter()
    try:
        r = requests.request(method, BASE + path, headers=h, data=raw, timeout=120, **kw)
    except requests.RequestException as e:
        log(name, {"request": {"method": method, "path": path}, "exception": repr(e)})
        return None, {"exception": repr(e)}, {}, (time.perf_counter() - t) * 1000
    ms = (time.perf_counter() - t) * 1000
    try:
        body = r.json()
    except ValueError:
        body = r.text[:5000]
    log(name, {"request": {"method": method, "path": path, "headers": redact(h),
                           "body": kw.get("json") if raw is None else f"<{len(raw)} raw bytes>"},
               "status": r.status_code, "ms": round(ms), "resp_headers": dict(r.headers), "body": body})
    return r.status_code, body, r.headers, ms


def err_code(body):
    if isinstance(body, dict) and isinstance(body.get("error"), dict):
        return body["error"].get("code") or body["error"].get("type")
    return ""


def pct(xs, p):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    k = (len(xs) - 1) * p / 100
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return round(xs[lo] + (xs[hi] - xs[lo]) * (k - lo))


def md_table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    out += ["| " + " | ".join(str(c).replace("|", "\\|").replace("\n", " ") for c in r) + " |" for r in rows]
    return "\n".join(out)


# ---------- tasks ----------
SPEND_FILE = RESULTS / "spend.json"


def spent():
    return json.loads(SPEND_FILE.read_text())["total"] if SPEND_FILE.exists() else 0.0


def add_spend(task):
    cost = ((task.get("usage") or {}).get("cost") or {}).get("total_usd") or 0
    SPEND_FILE.write_text(json.dumps({"total": spent() + cost}))


def guard():
    if spent() >= SPEND_CAP:
        raise SystemExit(f"Spend cap ${SPEND_CAP} reached (spent ${spent():.2f}); raise SPEND_CAP_USD to continue.")


def create_task(name, body, headers=None):
    guard()
    return call("POST", "/tasks", f"task_create_{name}", headers=headers, json=body)


def wait_task(task_id, name, timeout=900, every=3):
    """Poll until terminal; returns (task, timeline of status changes with seconds since start)."""
    t0, last, timeline = time.time(), None, []
    while time.time() - t0 < timeout:
        s, task, _, _ = _quiet_get(task_id)
        if s != 200:
            time.sleep(every); continue
        if task["status"] != last:
            last = task["status"]; timeline.append((last, round(time.time() - t0, 1)))
        if last in ("completed", "failed", "cancelled"):
            log(f"task_final_{name}", task)
            add_spend(task)
            return task, timeline
        time.sleep(every)
    return {"status": "client_timeout", "id": task_id}, timeline


def _quiet_get(task_id):
    # polls are not individually logged after the first few seconds to keep logs readable; final state is logged
    r = requests.get(f"{BASE}/tasks/{task_id}", headers=AUTH, timeout=60)
    try:
        return r.status_code, r.json(), r.headers, 0
    except ValueError:
        return r.status_code, {}, r.headers, 0
