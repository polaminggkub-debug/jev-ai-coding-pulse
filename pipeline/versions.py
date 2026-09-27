"""Extract explicit, family-matched model versions from a mention."""

import re


_NUMBER = r"\d+(?:\.\d+)*"
_RULES = {
    "claude opus": (r"\b(?:claude\s+)?opus\s*[- ]?(" + _NUMBER + r")\b", "Opus"),
    "opus": (r"\b(?:claude\s+)?opus\s*[- ]?(" + _NUMBER + r")\b", "Opus"),
    "claude sonnet": (r"\b(?:claude\s+)?sonnet\s*[- ]?(" + _NUMBER + r")\b", "Sonnet"),
    "sonnet": (r"\b(?:claude\s+)?sonnet\s*[- ]?(" + _NUMBER + r")\b", "Sonnet"),
    "claude haiku": (r"\b(?:claude\s+)?haiku\s*[- ]?(" + _NUMBER + r")\b", "Haiku"),
    "haiku": (r"\b(?:claude\s+)?haiku\s*[- ]?(" + _NUMBER + r")\b", "Haiku"),
    "claude fable": (r"\b(?:claude\s+)?fable\s*[- ]?(" + _NUMBER + r")\b", "Fable"),
    "fable": (r"\b(?:claude\s+)?fable\s*[- ]?(" + _NUMBER + r")\b", "Fable"),
    "claude code": (r"\bclaude[ -]?code(?:\s+version)?\s*[-:]?\s*v?(" + _NUMBER + r")\b", "Claude Code"),
    "codex": (r"\bcodex(?:\s+version)?\s*[-:]?\s*v?(" + _NUMBER + r")\b", "Codex"),
    "cursor": (r"\bcursor(?:\s+version)?\s*[-:]?\s*v?(" + _NUMBER + r")\b", "Cursor"),
    "opencode": (r"\bopen[ -]?code(?:\s+version)?\s*[-:]?\s*v?(" + _NUMBER + r")\b", "OpenCode"),
    "copilot": (r"\bcopilot(?:\s+version)?\s*[-:]?\s*v?(" + _NUMBER + r")\b", "Copilot"),
    "jev": (r"\bjev(?:\s+version)?\s*[-:]?\s*v?(" + _NUMBER + r")\b", "Jev"),
    "gpt / chatgpt": (r"\b(?:chat\s*gpt|gpt)\s*[- ]?(" + _NUMBER + r")\b", "GPT"),
    "gpt": (r"\b(?:chat\s*gpt|gpt)\s*[- ]?(" + _NUMBER + r")\b", "GPT"),
    "gemini": (r"\bgemini\s*[- ]?(" + _NUMBER + r")\b", "Gemini"),
    "grok": (r"\bgrok\s*[- ]?(" + _NUMBER + r")\b", "Grok"),
    "deepseek": (r"\bdeep\s*-?\s*seek\s*[- ]?([vr]?" + _NUMBER + r")\b", "DeepSeek"),
    "qwen": (r"\bqwen\s*[- ]?(" + _NUMBER + r")\b", "Qwen"),
    "kimi": (r"\bkimi\s*[- ]?(k?" + _NUMBER + r")\b", "Kimi"),
    "xiaomi mimo": (r"\b(?:xiaomi\s+)?mimo\s*[- ]?(v?" + _NUMBER + r")\b", "MiMo"),
    "mimo": (r"\b(?:xiaomi\s+)?mimo\s*[- ]?(v?" + _NUMBER + r")\b", "MiMo"),
    "glm": (r"\bglm\s*[- ]?(" + _NUMBER + r")\b", "GLM"),
    "minimax": (r"\bminimax\s*[- ]?(m?" + _NUMBER + r")\b", "MiniMax"),
    "llama": (r"\bllama\s*[- ]?(" + _NUMBER + r")\b", "Llama"),
    "mistral": (r"\b(?:mistral(?:\s+(?:large|medium|small))?|devstral)\s*[- ]?(" + _NUMBER + r")\b", "Mistral"),
    "gemma": (r"\bgemma\s*[- ]?(" + _NUMBER + r")\b", "Gemma"),
    "gpt-oss": (r"\bgpt\s*[- ]?oss\s*[- ]?(\d+(?:\.\d+)*b?)\b", "gpt-oss"),
}

_GPT_NICKNAMES = {
    "astra": "Astra",
    "sol": "Sol",
    "luna": "Luna",
    "terra": "Terra",
}
_NICKNAME_RE = re.compile(r"\b(?:astra|sol|luna|terra)\b", re.IGNORECASE)
_NON_VERSION_SUFFIX = re.compile(
    r"^\s*(?:[%$]|/\s*\d|,\s*\d|"
    r"(?:dollars?|bucks?|usd|eur|percent|tokens?|requests?|prompts?|messages?|"
    r"users?|subs(?:criptions?)?|credits?|calls?|days?|weeks?|hours?|months?|"
    r"years?|times?|cases?|tasks?|commits?)\b)",
    re.IGNORECASE,
)


def _extract_from(subject, text):
    family = (subject or "").strip().casefold()
    if not family or not text:
        return None

    if family in {"gpt", "gpt / chatgpt"}:
        full_nickname = re.search(
            r"\b(?:chat\s*gpt|gpt)\s*[- ]?6\s+(astra|sol|luna|terra)\b",
            text,
            re.IGNORECASE,
        )
        if full_nickname:
            name = _GPT_NICKNAMES[full_nickname.group(1).casefold()]
            return f"GPT-6 {name}"

    rule = _RULES.get(family)
    if rule:
        pattern, prefix = rule
        for match in re.finditer(pattern, text, re.IGNORECASE):
            version = match.group(1)
            suffix = text[match.end():]
            if _NON_VERSION_SUFFIX.match(suffix):
                continue
            # Repeated numeric halves after a slash describe a ratio (Fable 61/61),
            # rather than a release identifier.
            if re.match(r"\s*/\s*" + re.escape(version) + r"\b", suffix, re.IGNORECASE):
                continue
            if prefix == "DeepSeek" and version[:1].casefold() in {"v", "r"}:
                version = version[0].upper() + version[1:]
            elif prefix == "MiMo" and version.casefold().startswith("v"):
                version = "V" + version[1:]
            elif prefix == "Kimi" and version.casefold().startswith("k"):
                version = "K" + version[1:]
            elif prefix == "MiniMax" and version.casefold().startswith("m"):
                version = "M" + version[1:]
            return f"{prefix} {version}" if prefix != "GPT" else f"GPT-{version}"

    if family in {"gpt", "gpt / chatgpt"}:
        nickname = _NICKNAME_RE.search(text)
        if nickname:
            name = _GPT_NICKNAMES[nickname.group(0).casefold()]
            return f"GPT-6 {name}"
    return None


def extract_version(subject, text, thread_title=""):
    """Return an explicit version from text, then title, else ``None``.

    Matching is scoped to the supplied subject family so an unrelated model's
    version in the same sentence cannot label this mention.
    """
    return _extract_from(subject, text) or _extract_from(subject, thread_title)
