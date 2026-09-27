"""Small dependency-free JavaScript lexer and source guards."""

import re
from typing import List, Optional, Tuple


Token = Tuple[str, int, str]
JS_CONTROLS = {"catch", "for", "if", "switch", "while", "with", "function"}
JS_NETWORK_APIS = {
    "EventSource", "WebSocket", "XMLHttpRequest", "fetch", "sendBeacon",
    "Worker", "SharedWorker",
}
EXPRESSION_PREFIXES = {
    "(", "[", "{", ",", ";", ":", "=", "=>", "!", "?", "&&", "||",
    "+", "-", "*", "%", "&", "|", "^", "~", "return", "throw", "case",
    "delete", "void", "typeof", "instanceof", "in", "of", "yield", "await",
}
REGEX_KEYWORDS = {"case", "delete", "in", "instanceof", "of", "return", "throw", "typeof", "void", "yield"}


def _quoted(source: str, index: int, line: int) -> Tuple[str, int, int]:
    quote = source[index]
    start = index + 1
    index += 1
    while index < len(source):
        if source[index] == "\\":
            if index + 1 < len(source) and source[index + 1] == "\n":
                line += 1
            index += 2
            continue
        if source[index] == quote:
            return source[start:index], index + 1, line
        line += source[index] == "\n"
        index += 1
    return source[start:index], index, line


def _regex_end(source: str, index: int, line: int) -> Tuple[int, int]:
    index += 1
    in_class = False
    while index < len(source):
        char = source[index]
        if char == "\\":
            index += 2
        elif char == "[":
            in_class = True
            index += 1
        elif char == "]":
            in_class = False
            index += 1
        elif char == "/" and not in_class:
            index += 1
            while index < len(source) and source[index].isalpha():
                index += 1
            break
        else:
            line += char == "\n"
            index += 1
    return index, line


def _trivia(source: str, index: int, line: int) -> Tuple[int, int]:
    while index < len(source):
        if source[index].isspace():
            line += source[index] == "\n"
            index += 1
        elif source.startswith("//", index):
            end = source.find("\n", index + 2)
            index = len(source) if end < 0 else end
        elif source.startswith("/*", index):
            end = source.find("*/", index + 2)
            end = len(source) if end < 0 else end + 2
            line += source[index:end].count("\n")
            index = end
        else:
            break
    return index, line


def _template(source: str, index: int, line: int) -> Tuple[List[Token], int, int]:
    nested_tokens = []
    chunks = []
    index += 1
    segment = index
    start_line = line
    while index < len(source):
        if source[index] == "\\":
            if source[index:index + 2] == "\\\n":
                line += 1
            index += 2
        elif source[index] == "`":
            chunks.append(source[segment:index])
            literal = "".join(chunks)
            tokens = [(literal, start_line, "template")] if literal else []
            return tokens + nested_tokens, index + 1, line
        elif source.startswith("${", index):
            chunks.append(source[segment:index])
            chunks.append("__PULSE_DYNAMIC__")
            nested, index, line = _tokens(source, index + 2, line, True)
            nested_tokens.extend(nested)
            segment = index
        else:
            line += source[index] == "\n"
            index += 1
    chunks.append(source[segment:index])
    literal = "".join(chunks)
    tokens = [(literal, start_line, "template")] if literal else []
    return tokens + nested_tokens, index, line


def _word_or_number(source: str, index: int, line: int) -> Optional[Tuple[Token, int]]:
    char = source[index]
    if char.isalpha() or char in "_$" or ord(char) > 127:
        end = index + 1
        while end < len(source) and (
            source[end].isalnum() or source[end] in "_$" or ord(source[end]) > 127
        ):
            end += 1
        return (source[index:end], line, "word"), end
    if char.isdigit():
        end = index + 1
        while end < len(source) and (source[end].isalnum() or source[end] in "._"):
            end += 1
        return (source[index:end], line, "number"), end
    return None


def _symbol(source: str, index: int, line: int) -> Tuple[Token, int]:
    value = next((item for item in ("=>", "?.", "...", "**", "&&", "||", "??")
                  if source.startswith(item, index)), source[index])
    return (value, line, "symbol"), index + len(value)


def _tokens(
    source: str, index: int = 0, line: int = 1, template_expr: bool = False,
) -> Tuple[List[Token], int, int]:
    tokens = []
    brace_depth = 0
    while index < len(source):
        index, line = _trivia(source, index, line)
        if index >= len(source):
            break
        char = source[index]
        if template_expr and char == "}" and brace_depth == 0:
            return tokens, index + 1, line
        if char in "'\"":
            start_line = line
            value, index, line = _quoted(source, index, line)
            tokens.append((value, start_line, "string"))
        elif char == "`":
            nested, index, line = _template(source, index, line)
            tokens.extend(nested)
        elif char == "/" and (not tokens or tokens[-1][0] in REGEX_KEYWORDS or (
            tokens[-1][0] in EXPRESSION_PREFIXES and tokens[-1][2] == "symbol"
        )):
            index, line = _regex_end(source, index, line)
        else:
            found = _word_or_number(source, index, line)
            if found:
                token, index = found
                tokens.append(token)
                continue
            token, index = _symbol(source, index, line)
            tokens.append(token)
            brace_depth += (template_expr and token[0] == "{") - (template_expr and token[0] == "}")
    return tokens, index, line


def _pairs(tokens: List[Token]) -> dict:
    opening = {"(": ")", "[": "]", "{": "}"}
    closing = {value: key for key, value in opening.items()}
    stack = []
    pairs = {}
    for index, token in enumerate(tokens):
        value = token[0]
        if token[2] != "symbol":
            continue
        if value in opening:
            stack.append((value, index))
        elif value in closing and stack and stack[-1][0] == closing[value]:
            _, start = stack.pop()
            pairs[start] = index
            pairs[index] = start
    return pairs


def _arrow_end(tokens: List[Token], pairs: dict, start: int) -> int:
    index = last = start
    while index < len(tokens):
        value, _, kind = tokens[index]
        if kind == "symbol" and value in {",", ";", ")", "]", "}"}:
            break
        if kind == "symbol" and value in {"(", "[", "{"} and index in pairs:
            last = pairs[index]
            index = last + 1
        else:
            last = index
            index += 1
    return last


def _add_function(functions: dict, tokens: List[Token], pairs: dict,
                  name: str, start: int, opening: int, end: Optional[int] = None) -> None:
    close = pairs.get(opening) if end is None else end
    if close is not None and close < len(tokens):
        first, last = tokens[start][1], tokens[close][1]
        functions[(start, close)] = (name, first, last - first + 1)


def js_functions(source: str) -> List[Tuple[str, int, int]]:
    """Return line spans for declarations, methods, and arrow functions."""
    tokens, _, _ = _tokens(source)
    pairs = _pairs(tokens)
    functions = {}
    for index, token in enumerate(tokens):
        if token[0] == "function" and token[2] == "word":
            opening = next((pos for pos in range(index + 1, len(tokens))
                            if tokens[pos][2] == "symbol" and tokens[pos][0] in {"(", "{", ";"}), None)
            if opening is not None and tokens[opening][0] == "(":
                close = pairs.get(opening)
                if close is not None and close + 1 < len(tokens) and tokens[close + 1][0] == "{":
                    _add_function(functions, tokens, pairs, "function", index, close + 1)
        if token[0] != "=>" or token[2] != "symbol":
            continue
        body = index + 1
        start = index - 1
        if start >= 0 and tokens[start][0] == ")":
            start = pairs.get(start, start)
        if start > 0 and tokens[start - 1][0] == "async":
            start -= 1
        start = max(start, 0)
        if body < len(tokens) and tokens[body][0] == "{":
            _add_function(functions, tokens, pairs, "arrow", start, body)
        elif body < len(tokens):
            end = _arrow_end(tokens, pairs, body)
            first, last = tokens[start][1], tokens[end][1]
            functions[(start, end)] = ("arrow", first, last - first + 1)
    _method_functions(tokens, pairs, functions)
    return list(functions.values())


def js_markup_literals(source: str) -> List[str]:
    """Return HTML-shaped JavaScript strings and template literals."""
    tokens, _, _ = _tokens(source)
    return [token[0] for token in tokens if token[2] in {"string", "template"}
            and "<" in token[0] and ">" in token[0]]


def _method_functions(tokens: List[Token], pairs: dict, functions: dict) -> None:
    for opening, closing in pairs.items():
        if opening > closing or tokens[opening][0] != "(":
            continue
        name_index = opening - 1
        if closing + 1 >= len(tokens) or tokens[closing + 1][0] != "{":
            continue
        if name_index < 0 or tokens[name_index][0] in JS_CONTROLS:
            continue
        name = tokens[name_index][0]
        if tokens[name_index][2] not in {"word", "string"} and name != "]":
            continue
        before = tokens[name_index - 1][0] if name_index else ""
        if before in {".", "?.", "function"}:
            continue
        start = name_index - 1 if before in {"async", "get", "set", "static", "*"} else name_index
        if start > 0 and tokens[start - 1][0] in {"async", "static"}:
            start -= 1
        _add_function(functions, tokens, pairs, "method " + name, start, closing + 1)


def _external_urls(value: str) -> List[str]:
    candidates = re.findall(r"(?i)(?:[a-z][a-z0-9+.-]*://|//)[^\s\"'<>]+", value)
    found = []
    for candidate in candidates:
        clean = candidate.rstrip(".,;:!?)]}")
        if clean.lower().startswith(("http://", "https://", "ftp://", "ws://", "wss://", "//")):
            found.append(clean)
    return found


def js_external_loads(source: str, label: str) -> List[str]:
    """Flag common page network APIs and dynamically assigned resource URLs."""
    tokens, _, _ = _tokens(source)
    values = [token[0] for token in tokens]
    failures = []
    for index, token in enumerate(tokens):
        value = token[0]
        if token[2] == "word" and value in JS_NETWORK_APIS:
            next_value = values[index + 1] if index + 1 < len(values) else ""
            if value in {"fetch", "sendBeacon"} and next_value != "(":
                continue
            failures.append(f"{label}: browser network API {value}")
        if token[2] == "word" and value == "import":
            failures.extend(_module_loads(tokens, index, label))
    for index, value in enumerate(values[:-2]):
        if value == "." and values[index + 1] == "src" and values[index + 2] == "=":
            failures.append(f"{label}: dynamic resource src assignment")
        if value == "setAttribute" and values[index + 2] == "src":
            failures.append(f"{label}: dynamic resource src assignment")
        if value == "location" and (
            values[index + 1] in {"=", "."} or values[index + 1] in {"assign", "replace"}
        ):
            failures.append(f"{label}: programmatic external navigation")
        if value == "[" and values[index + 1] == "src" and values[index + 2] == "]":
            failures.append(f"{label}: dynamic resource src assignment")
    for match in re.findall(r"(?is)url\(\s*([^)]*)\)", source):
        failures.extend(f"{label}: external CSS resource {url}" for url in _external_urls(match))
    return failures


def _module_loads(tokens: List[Token], index: int, label: str) -> List[str]:
    failures = []
    for token in tokens[index + 1:index + 10]:
        if token[2] == "symbol" and token[0] in {";", ")"}:
            break
        failures.extend(f"{label}: external module load {url}" for url in _external_urls(token[0]))
    return failures
