import json,collections,html,datetime
r=json.load(open("labeled.json"))
ZN={"us":"🇺🇸 US frontier","open":"🇨🇳 China + open models","tool":"🛠 Coding tools"}
agg=collections.defaultdict(lambda:collections.defaultdict(list))
for j in r: agg[(j["zone"],j["subject"])][j["label"]].append(j)
def e(s): return html.escape(s or "")
def quote(lst):
    lst=[j for j in lst if j["kind"]=="comment" and max((j["probs"] or {}).values() or [0])>0.6 and 20<len(j["text"])<400]
    if not lst: return ""
    j=max(lst,key=lambda j:j["score"]); t=" ".join(j["text"].split())
    return f'<a href="{e(j["link"])}" target=_blank>“{e(t[:160])}{"…" if len(t)>160 else ""}”</a> <span class=m>▲{j["score"]}</span>'
sections=""
for z in ["us","tool","open"]:
    rows=[];threads={}
    for (zz,n),d in agg.items():
        if zz!=z: continue
        p,c,m=len(d["praise"]),len(d["complaint"]),len(d["mixed"]);op=p+c+m
        for j in sum(d.values(),[]): threads[j["thread_url"]]=(j["thread_score"],j["thread"],j["sub"])
        if op<5: continue
        rows.append((p/op-c/op,n,p,c,m,op,quote(d["praise"]),quote(d["complaint"])))
    rows.sort(reverse=True)
    tr="".join(f'''<tr><td class=n>{e(n)}</td><td class=bar><div class=b><span class=p style="width:{100*p/op:.0f}%"></span><span class=x style="width:{100*m/op:.0f}%"></span><span class=c style="width:{100*c/op:.0f}%"></span></div>
      <span class=m>👍 {100*p/op:.0f}% · 👎 {100*c/op:.0f}% · {op} opinions</span></td><td class=q><div>{qp}</div><div class=neg>{qc}</div></td></tr>''' for s,n,p,c,m,op,qp,qc in rows)
    th="".join(f'<li><span class=m>▲{s} · r/{e(sub)}</span> <a href="{e(u)}" target=_blank>{e(t)}</a></li>' for u,(s,t,sub) in sorted(threads.items(),key=lambda x:-x[1][0])[:5])
    best=rows[0][1] if rows else "-"
    sections+=f'<section><h2>{ZN[z]} <span class=pick>best right now: {e(best)}</span></h2><table>{tr}</table><h3>Hot threads</h3><ul>{th}</ul></section>'
buzz=sorted(((len(sum(d.values(),[])),n) for (z,n),d in agg.items()),reverse=True)[:6]
bz=" · ".join(f"{e(n)} <b>{k}</b>" for k,n in buzz)
page=f'''<!doctype html><html><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>Jev Reddit Pulse</title><style>
:root{{--bg:#fafaf8;--fg:#1c1c1a;--mut:#6b6b66;--line:#e4e4df;--pos:#2f8f5b;--neg:#c2413b;--mix:#c9a13b;--card:#fff}}
@media (prefers-color-scheme:dark){{:root:not([data-theme=light]){{--bg:#161615;--fg:#ececea;--mut:#9a9a94;--line:#2c2c2a;--card:#1f1f1d}}}}
body{{background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif;margin:0;padding:24px 16px;max-width:1000px;margin:auto}}
h1{{margin:0}}.sub{{color:var(--mut);margin:4px 0 20px}}section{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;margin:16px 0;overflow-x:auto}}
h2{{margin:0 0 10px;font-size:18px}}.pick{{font-size:13px;font-weight:500;color:var(--pos);margin-left:8px}}h3{{font-size:14px;margin:14px 0 4px}}
table{{width:100%;border-collapse:collapse}}td{{border-top:1px solid var(--line);padding:8px 6px;vertical-align:top}}.n{{font-weight:600;white-space:nowrap}}.bar{{width:260px}}
.b{{display:flex;height:10px;border-radius:5px;overflow:hidden;background:var(--line)}}.p{{background:var(--pos)}}.c{{background:var(--neg)}}.x{{background:var(--mix)}}
.m{{color:var(--mut);font-size:12px}}.q{{font-size:13px}}.q a{{color:inherit;text-decoration:none}}.q a:hover{{text-decoration:underline}}.q .neg a{{color:var(--neg)}}.q>div:first-child a{{color:var(--pos)}}
ul{{margin:0;padding-left:18px}}li{{margin:3px 0;font-size:14px}}li a{{color:inherit}}.buzz{{font-size:14px}}
</style></head><body><h1>Jev Reddit Pulse</h1><div class=sub>Coding sentiment from 10 subreddits · top 8 threads each, {len(r):,} mentions judged by Jev · threads from 2–5 days ago (Reddit scores settle late) · demo {datetime.date.today()}</div>
<section><h2>🔥 Most talked about</h2><div class=buzz>{bz}</div></section>{sections}</body></html>'''
open("pulse.html","w").write(page);print("ok")
