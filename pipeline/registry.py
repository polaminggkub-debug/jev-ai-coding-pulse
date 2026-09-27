import re
# (name, zone, regex). Zones: us, open (China + open weights), tool
R=[
("Claude Code","tool",r"\bclaude[ -]?code\b|\bcc\b"),
("Codex","tool",r"\bcodex\b"),
("Cursor","tool",r"\bcursor\b"),
("OpenCode","tool",r"\bopen[ -]?code\b"),
("Copilot","tool",r"\bcopilot\b"),
("Jev","tool",r"\bjev\b"),
("Claude Opus","us",r"\bopus\b"),
("Claude Sonnet","us",r"\bsonnet\b"),
("Claude Haiku","us",r"\bhaiku\b"),
("Claude Fable","us",r"\bfable\b"),
("GPT / ChatGPT","us",r"\bgpt[- ]?5(?:\.\d)?\b|\bchat ?gpt\b|\bgpt\b|\b(?:astra|sol|luna|terra)\b"),
("Gemini","us",r"\bgemini\b"),
("Grok","us",r"\bgrok\b"),
("DeepSeek","open",r"\bdeep ?seek\b"),
("Qwen","open",r"\bqwen\w*"),
("Kimi","open",r"\bkimi\b"),
("Xiaomi MiMo","open",r"\bmimo\b"),
("GLM","open",r"\bglm[- ]?\d|\bzhipu\b|\bz\.ai\b"),
("MiniMax","open",r"\bminimax\b"),
("Llama","open",r"\bllama\b(?!\.cpp)"),
("Mistral","open",r"\bmistral\b|\bdevstral\b"),
("Gemma","open",r"\bgemma\b"),
("gpt-oss","open",r"\bgpt[- ]?oss\b"),
]
C=[(n,z,re.compile(p,re.I)) for n,z,p in R]
def mentions(text):
    return [(n,z) for n,z,rx in C if rx.search(text or "")]
