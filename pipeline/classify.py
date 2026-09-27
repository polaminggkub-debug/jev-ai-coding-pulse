import json,time
from concurrent.futures import ThreadPoolExecutor
from registry import mentions
from jev import decide
Q={"type":"choice","instructions":"`text` is a Reddit post or comment. How does it talk about `subject` as a tool for writing code or doing agentic coding work?",
 "criteria":{"praise":"Positive about `subject`: works well, impressed, recommends it, prefers it",
  "complaint":"Negative about `subject`: broken, worse, nerfed, limits, too expensive, disappointed, prefers something else",
  "mixed":"Both clear positives and clear negatives about `subject`",
  "no_opinion":"Mentions `subject` without judging it, asks a question, or is not about `subject` at all"}}
raw=json.load(open("raw.json"));jobs=[]
for s,v in raw.items():
    for p in v["top"]:
        url="https://www.reddit.com"+p["permalink"]
        items=[("post",p["title"]+"\n"+(p["selftext"] or ""),p["score"],url)]+[("comment",c["body"],c["score"],url+c["id"]+"/") for c in p["comments"]]
        for kind,text,score,link in items:
            for n,z in mentions(text): jobs.append(dict(sub=s,kind=kind,text=text[:1500],score=score or 0,link=link,thread=p["title"],thread_score=p["score"],thread_url=url,subject=n,zone=z))
def run(j):
    a=decide({"subject":j["subject"],"text":j["text"]},{"s":Q}).get("s",{})
    j["label"]=a.get("choice");j["probs"]=a.get("probabilities");return j
t=time.time()
with ThreadPoolExecutor(12) as ex: res=list(ex.map(run,jobs))
json.dump(res,open("labeled.json","w"))
print(len(res),"calls in",round(time.time()-t),"s; failed:",sum(1 for r in res if not r["label"]))
