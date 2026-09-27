import json,os,urllib.request,time
KEY=os.environ["OPENROUTER_API_KEY"]
def decide(state,questions,timeout=20):
    body={"model":"~typesafe/jev-latest","state":state,"questions":questions,"provider":{"zdr":True,"data_collection":"deny"}}
    req=urllib.request.Request("https://openrouter.ai/api/alpha/decisions",data=json.dumps(body).encode(),
        headers={"Authorization":f"Bearer {KEY}","Content-Type":"application/json"})
    for i in range(3):
        try: return json.load(urllib.request.urlopen(req,timeout=timeout)).get("answers",{})
        except Exception as e: err=str(e); time.sleep(1+i)
    return {"error":err}
