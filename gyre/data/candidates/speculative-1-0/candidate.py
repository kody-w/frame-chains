def tokenize(text):
    tokens = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch.isspace():
            i = i + 1
            continue
        if ch == "," or ch == "*" or ch == "(" or ch == ")":
            tokens.append([ch, ch])
            i = i + 1
            continue
        if ch == ".":
            if i + 1 < n and text[i + 1] == ".":
                tokens.append(["..", ".."])
                i = i + 2
                continue
            raise ValueError("bad dot")
        if ch == "+" or ch == "-":
            j = i + 1
            digits = ""
            while j < n and text[j] >= "0" and text[j] <= "9":
                digits = digits + text[j]
                j = j + 1
            if digits == "":
                raise ValueError("missing digits")
            tokens.append(["int", ch + digits])
            i = j
            continue
        if ch >= "0" and ch <= "9":
            j = i
            digits = ""
            while j < n and text[j] >= "0" and text[j] <= "9":
                digits = digits + text[j]
                j = j + 1
            tokens.append(["num", digits])
            i = j
            continue
        raise ValueError("bad character")
    return tokens


def to_int(token):
    kind = token[0]
    if kind != "int" and kind != "num":
        raise ValueError("integer expected")
    value = int(token[1])
    if value < -1000 or value > 1000:
        raise ValueError("integer limit")
    return value


def peek(tokens, pos):
    if pos < len(tokens):
        return tokens[pos][0]
    return ""


def parse_expression(tokens, pos, depth):
    values = []
    if peek(tokens, pos) == "" or peek(tokens, pos) == ")":
        return [values, pos]
    step = parse_term(tokens, pos, depth)
    values.extend(step[0])
    pos = step[1]
    if len(values) > 256:
        raise ValueError("too many values")
    while peek(tokens, pos) == ",":
        pos = pos + 1
        step = parse_term(tokens, pos, depth)
        values.extend(step[0])
        pos = step[1]
        if len(values) > 256:
            raise ValueError("too many values")
    return [values, pos]


def parse_term(tokens, pos, depth):
    kind = peek(tokens, pos)
    if kind == "":
        raise ValueError("unexpected end")
    if kind == "num" and peek(tokens, pos + 1) == "*":
        count = int(tokens[pos][1])
        if count > 20:
            raise ValueError("count range")
        if depth + 1 > 12:
            raise ValueError("too deep")
        pos = pos + 2
        if peek(tokens, pos) != "(":
            raise ValueError("paren expected")
        pos = pos + 1
        inner = parse_expression(tokens, pos, depth + 1)
        pos = inner[1]
        if peek(tokens, pos) != ")":
            raise ValueError("close expected")
        pos = pos + 1
        body = inner[0]
        if len(body) * count > 256:
            raise ValueError("too many values")
        out = []
        k = 0
        while k < count:
            out.extend(body)
            k = k + 1
        return [out, pos]
    if kind != "int" and kind != "num":
        raise ValueError("term expected")
    first = to_int(tokens[pos])
    pos = pos + 1
    if peek(tokens, pos) == "..":
        pos = pos + 1
        if peek(tokens, pos) == "":
            raise ValueError("range end missing")
        second = to_int(tokens[pos])
        pos = pos + 1
        out = []
        value = first
        if first <= second:
            while value <= second:
                out.append(value)
                value = value + 1
        else:
            while value >= second:
                out.append(value)
                value = value - 1
        if len(out) > 256:
            raise ValueError("too many values")
        return [out, pos]
    return [[first], pos]


def solve(expression):
    if not isinstance(expression, str):
        raise ValueError("text required")
    if expression.strip() == "":
        return []
    tokens = tokenize(expression)
    result = parse_expression(tokens, 0, 0)
    if result[1] != len(tokens):
        raise ValueError("trailing junk")
    values = result[0]
    if len(values) > 256:
        raise ValueError("too many values")
    return values
