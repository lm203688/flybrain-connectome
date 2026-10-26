import json, time, urllib.request
URL="http://127.0.0.1:8788/v1/chat/completions"
results=[]
for i in range(5):
    body=json.dumps({"model":"deepseek-v4-flash","messages":[{"role":"user","content":f"Q{i}: 2*{i+1}=? 只答数字"}],"max_tokens":20,"reasoning_effort":"none"}).encode()
    req=urllib.request.Request(URL, data=body, headers={"Content-Type":"application/json"})
    t0=time.time()
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            d=json.loads(r.read())
        c=d["choices"][0]["message"]["content"]
        results.append((time.time()-t0, c, d.get("usage",{}).get("total_tokens",0)))
    except Exception as e:
        results.append((time.time()-t0, f"ERR:{type(e).__name__}", 0))
print(f"{'ms':>6}  {'tokens':>6}  answer")
for ms,ans,tk in results:
    print(f"{ms*1000:>6.0f}  {tk:>6}  {ans[:40]!r}")
print(f"\navg latency: {sum(r[0] for r in results)/len(results)*1000:.0f}ms")
print(f"success: {sum(1 for r in results if not str(r[1]).startswith('ERR'))}/{len(results)}")
