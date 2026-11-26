import json, glob
from inference_latency import one, SESSION, AUTH
import inference_latency as L
recs = json.load(open(sorted(glob.glob("logs/*latency_all.json"))[-1]))
print("failures:", [ (r["model"], r["status"], str(r["error"])[:200]) for r in recs if r["status"]!=200 or r["error"]])
for hdr in ({}, {"X-Moss-System-Prompt": "off"}):
    L.AUTH.update(hdr)
    xs = [one("moss/fastlane-1", f"In one sentence, what is a {t}? (sp {i})")["ttft_ms"] for i, t in enumerate(L.TOPICS[:10])]
    print(hdr or "default", sorted(xs))
