import time, requests, statistics, json
from common import AUTH, BASE, log
s = requests.Session(); ts = []
for i in range(12):
    t = time.perf_counter(); r = s.get(BASE + "/models", headers=AUTH, timeout=30); ts.append((time.perf_counter() - t) * 1000)
hdr = dict(r.headers)
print("GET /models over keep-alive ms:", [round(x) for x in ts]); print("min", round(min(ts[1:])), "median", round(statistics.median(ts[1:])))
print({k: v for k, v in hdr.items() if k.lower() in ("server", "via", "cf-ray", "x-served-by", "server-timing", "fly-request-id", "x-cache")})
log("network_rtt", {"ms": ts, "headers": hdr})
