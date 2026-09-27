"""One OpenRouter request per decision, keeping the per-run call cap literal."""
import json
import os
import urllib.request


def decide(state, questions, timeout=20):
    body = {"model": "~typesafe/jev-latest", "state": state, "questions": questions,
            "provider": {"zdr": True, "data_collection": "deny"}}
    request = urllib.request.Request(
        "https://openrouter.ai/api/alpha/decisions", data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
                 "Content-Type": "application/json"})
    # Failed requests are retried on the next scheduled run, never hidden here.
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response).get('answers', {})
