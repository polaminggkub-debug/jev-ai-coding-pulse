import json,time,urllib.request,urllib.parse,sys
from concurrent.futures import ThreadPoolExecutor
SUBS=["LocalLLaMA","ClaudeAI","ClaudeCode","OpenAI","ChatGPTCoding","codex","singularity","cursor","DeepSeek","Qwen_AI"]
BASE="https://arctic-shift.photon-reddit.com/api"
NOW=int(time.time()); AFTER=NOW-5*86400; BEFORE=NOW-2*86400
def get(path,**q):
    u=f"{BASE}/{path}?"+urllib.parse.urlencode(q)
    for i in range(4):
        try: return json.load(urllib.request.urlopen(urllib.request.Request(u,headers={"User-Agent":"jev-reddit-demo"}),timeout=60)).get("data",[])
        except Exception as e: print("retry",path,e,file=sys.stderr); time.sleep(3*(i+1))
    return []
def sub(s):
    posts=[];before=BEFORE
    for _ in range(4):
        page=get("posts/search",subreddit=s,after=AFTER,before=before,limit=100,sort="desc")
        if not page: break
        posts+=page; before=min(p["created_utc"] for p in page)
        if len(page)<100: break
    top=sorted(posts,key=lambda p:p.get("score") or 0,reverse=True)[:8]
    for p in top:
        p["comments"]=[{k:c.get(k) for k in("id","body","score")} for c in get("comments/search",link_id=p["id"],limit=100)]
    return s,{"scanned":len(posts),"top":[{k:p.get(k) for k in("id","title","selftext","score","num_comments","permalink","comments")} for p in top]}
with ThreadPoolExecutor(4) as ex: out=dict(ex.map(sub,SUBS))
for s,v in out.items(): print(f"{s:14} scanned={v['scanned']:3} top_scores={[p['score'] for p in v['top']]} comments={sum(len(p['comments']) for p in v['top'])}")
json.dump(out,open("raw.json","w"))
