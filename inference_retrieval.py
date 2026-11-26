"""Does X-Moss-Indexes actually ground answers? Fictional facts the model cannot know; with vs without index."""
import asyncio, json, time
import requests
from common import AUTH, BASE, PID, PKEY, RESULTS, log, md_table, pct

IDX = "zorblax-faq"
DOCS = [
    "Zorblax Kites was founded in 2019 in Coimbatore by Meera Tandon.",
    "The Zorblax Stormrider kite costs 4,750 rupees and is rated for winds up to 38 km/h.",
    "Zorblax offers a 45-day return window, but only if the kite string is unused.",
    "Customer support for Zorblax is open 9am to 6pm IST, Tuesday to Saturday. It is closed on Mondays.",
    "The Zorblax loyalty program is called SkyPoints; every 100 rupees spent earns 7 SkyPoints.",
    "Zorblax ships to India, Sri Lanka and Nepal only. Shipping to Nepal takes 9 business days.",
    "The Zorblax Featherlite kite weighs 112 grams and is made of ripstop nylon.",
    "Warranty on Zorblax frames is 18 months; fabric tears are not covered.",
    "Zorblax's warehouse is in Tiruppur and dispatches orders at 3pm daily.",
    "To reset a Zorblax account password, users must email reset@zorblax.example with the subject 'KITE-RESET'.",
]
QA = [  # question, substring that must appear in a correct answer
    ("Who founded Zorblax Kites?", "meera"),
    ("How much does the Stormrider cost?", "4,750"),
    ("How long is Zorblax's return window?", "45"),
    ("Which day is Zorblax support closed?", "monday"),
    ("How many SkyPoints do I earn per 100 rupees?", "7"),
    ("How long does shipping to Nepal take?", "9"),
    ("How much does the Featherlite weigh?", "112"),
    ("How long is the frame warranty?", "18"),
    ("Where is the Zorblax warehouse?", "tiruppur"),
    ("What subject line do I use to reset my password?", "kite-reset"),
    ("Does Zorblax ship to Bhutan?", "no"),  # negative: must say no, not hallucinate yes
]


async def build_index():
    from moss import MossClient, DocumentInfo  # pip install moss
    c = MossClient(PID, PKEY)
    try:
        await c.delete_index(IDX)
    except Exception:
        pass
    t0 = time.time()
    res = await c.create_index(IDX, [DocumentInfo(id=f"d{i}", text=t) for i, t in enumerate(DOCS)])
    job = getattr(res, "job_id", None)
    status = None
    for _ in range(90):  # up to ~3 min
        if not job:
            break
        status = await c.get_job_status(job)
        if getattr(status, "completed_at", None) or getattr(status, "error", None):  # JobStatus enum has no readable repr
            break
        await asyncio.sleep(2)
    st = {k: str(getattr(status, k)) for k in ("created_at", "completed_at", "progress", "error")} if status else {}
    log("retrieval_index_build", {"result": str(res), "status": st, "seconds": round(time.time() - t0, 1)})
    return round(time.time() - t0, 1), json.dumps(st)


def ask(model, q, indexes):
    h = {**AUTH, "X-Moss-Cache": "off"}
    if indexes:
        h["X-Moss-Indexes"] = IDX
    t0 = time.perf_counter()
    r = requests.post(BASE + "/chat/completions", headers=h, timeout=90, json={
        "model": model, "max_tokens": 80, "messages": [{"role": "user", "content": q + " Answer in one short sentence."}]})
    ms = (time.perf_counter() - t0) * 1000
    b = r.json() if r.headers.get("content-type", "").startswith("application/json") else {"raw": r.text}
    text = ((b.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
    return {"model": model, "q": q, "indexed": indexes, "status": r.status_code, "ms": round(ms), "text": text,
            "retrieve_ms": r.headers.get("X-Moss-Retrieve-Ms"), "usage": b.get("usage"), "error": b.get("error")}


def main():
    build_s, build_status = asyncio.run(build_index())
    time.sleep(3)
    recs, rows = [], []
    for model in ["moss/fastlane-1", "anthropic/claude-haiku-5.5"]:
        for indexed in (False, True):
            got = [ask(model, q, indexed) | {"expect": e} for q, e in QA]
            for g in got:
                g["correct"] = g["expect"] in g["text"].lower().replace("₹", "")
            recs += got
            rmss = [float(g["retrieve_ms"]) for g in got if g["retrieve_ms"]]
            rows.append([model, "yes" if indexed else "no", f"{sum(g['correct'] for g in got)}/{len(got)}",
                         pct([g["ms"] for g in got], 50), pct(rmss, 50) if rmss else "-",
                         pct([(g["usage"] or {}).get("prompt_tokens") for g in got], 50)])
            print(rows[-1], flush=True)
    log("retrieval_answers", recs)
    wrong = [[r["model"], r["q"], r["text"][:100]] for r in recs if r["indexed"] and not r["correct"]]
    md = [f"## Retrieval grounding (index of {len(DOCS)} fictional facts, built in {build_s}s, status `{build_status[:80]}`)",
          md_table(["model", "X-Moss-Indexes", "correct", "total p50 ms", "X-Moss-Retrieve-Ms p50", "prompt tokens p50"], rows),
          "", "### Wrong answers with the index attached", md_table(["model", "question", "answer"], wrong) if wrong else "none"]
    (RESULTS / "retrieval.md").write_text("\n".join(md), encoding="utf-8")


if __name__ == "__main__":
    main()
