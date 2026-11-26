"""Run every test in order, then stitch results/*.md into results/REPORT.md."""
import subprocess, sys, time
from common import RESULTS, spent

STEPS = sys.argv[1:] or ["inference_compat", "inference_edge", "inference_latency", "inference_retrieval", "tasks_break", "tasks_real"]
for s in STEPS:
    print(f"\n===== {s} =====", flush=True)
    rc = subprocess.call([sys.executable, f"{s}.py"])
    print(f"===== {s} exit {rc} =====", flush=True)

parts = [f"# Moss Inference test results ({time.strftime('%Y-%m-%d')})", f"Task spend tracked: ${spent():.2f}", ""]
for f in ["compat", "edge", "latency", "retrieval", "tasks_real", "tasks_break"]:
    p = RESULTS / f"{f}.md"
    if p.exists():
        parts += [p.read_text(encoding="utf-8"), ""]
(RESULTS / "REPORT.md").write_text("\n".join(parts), encoding="utf-8")
print("wrote results/REPORT.md")
