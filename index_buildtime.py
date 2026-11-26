import asyncio, time
from moss import MossClient, DocumentInfo
from common import PID, PKEY
async def main():
    c = MossClient(PID, PKEY)
    t0 = time.time()
    res = await c.create_index("zorblax-buildtime", [DocumentInfo(id=f"d{i}", text=f"fact number {i}") for i in range(10)])
    print("create returned after", round(time.time()-t0,1), "s:", {k: getattr(res, k) for k in dir(res) if not k.startswith("_")})
    while True:
        s = await c.get_job_status(res.job_id)
        d = {k: getattr(s, k) for k in dir(s) if not k.startswith("_") and not callable(getattr(s, k))}
        print(round(time.time()-t0,1), d); 
        if str(d.get("status","")).lower() not in ("pending","running","queued","building","in_progress","processing") or time.time()-t0>300: break
        await asyncio.sleep(3)
    await c.delete_index("zorblax-buildtime")
asyncio.run(main())
