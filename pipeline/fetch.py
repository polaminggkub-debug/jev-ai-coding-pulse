import json,time,urllib.request,urllib.parse,sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
SUBS=["LocalLLaMA","ClaudeAI","ClaudeCode","OpenAI","ChatGPTCoding","codex","singularity","cursor","DeepSeek","Qwen_AI"]
BASE="https://arctic-shift.photon-reddit.com/api"
ROOT=Path(__file__).resolve().parent.parent
DATA=ROOT/"data"
def get(path,**q):
    u=f"{BASE}/{path}?"+urllib.parse.urlencode(q)
    for i in range(4):
        try: return json.load(urllib.request.urlopen(urllib.request.Request(u,headers={"User-Agent":"jev-reddit-demo"}),timeout=60)).get("data",[])
        except Exception as e: print("retry",path,e,file=sys.stderr); time.sleep(3*(i+1))
    return []
def sub(s):
    now=int(time.time()); after_ts=now-5*86400; before=now-2*86400
    posts=[]
    for _ in range(4):
        page=get("posts/search",subreddit=s,after=after_ts,before=before,limit=100,sort="desc")
        if not page: break
        posts+=page; before=min(p["created_utc"] for p in page)
        if len(page)<100: break
    top=sorted(posts,key=lambda p:p.get("score") or 0,reverse=True)[:8]
    for p in top:
        p["comments"]=[{k:c.get(k) for k in("id","body","score")} for c in get("comments/search",link_id=p["id"],limit=100)]
    return s,{"scanned":len(posts),"top":[{k:p.get(k) for k in("id","title","selftext","score","num_comments","permalink","comments")} for p in top]}
def main():
    with ThreadPoolExecutor(4) as ex: out=dict(ex.map(sub,SUBS))
    for s,v in out.items(): print(f"{s:14} scanned={v['scanned']:3} top_scores={[p['score'] for p in v['top']]} comments={sum(len(p['comments']) for p in v['top'])}")
    DATA.mkdir(parents=True,exist_ok=True)
    (DATA/"raw.json").write_text(json.dumps(out,ensure_ascii=False,separators=(",",":"))+"\n",encoding="utf-8")

if __name__=="__main__":
    main()
