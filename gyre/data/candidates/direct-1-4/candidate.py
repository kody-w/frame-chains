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


def peek(tokens, pos):
    if pos < len(tokens):
        return tokens[pos][0]
    return ""


def int_value(token):
    value = int(token[1])
    if value < -1000 or value > 1000:
        raise ValueError("integer limit")
    return value


def parse_expression(tokens, pos, depth):
    values = []
    if peek(tokens, pos) == "" or peek(tokens, pos) == ")":
        return [values, pos]
    out = parse_term(tokens, pos, depth)
    values.extend(out[0])
    pos = out[1]
    if len(values) > 256:
        raise ValueError("too many values")
    while peek(tokens, pos) == ",":
        pos = pos + 1
        out = parse_term(tokens, pos, depth)
        values.extend(out[0])
        pos = out[1]
        if len(values) > 256:
            raise ValueError("too many values")
    return [values, pos]


def parse_term(tokens, pos, depth):
    kind = peek(tokens, pos)
    if kind != "int" and kind != "num":
        raise ValueError("expected term")
    token = tokens[pos]
    if kind == "num" and peek(tokens, pos + 1) == "*":
        count = int(token[1])
        if count < 0 or count > 20:
            raise ValueError("bad count")
        if depth + 1 > 12:
            raise ValueError("too deep")
        pos = pos + 2
        if peek(tokens, pos) != "(":
            raise ValueError("expected (")
        pos = pos + 1
        out = parse_expression(tokens, pos, depth + 1)
        inner = out[0]
        pos = out[1]
        if peek(tokens, pos) != ")":
            raise ValueError("expected )")
        pos = pos + 1
        if len(inner) > 256:
            raise ValueError("too many values")
        values = []
        step = 0
        while step < count:
            values.extend(inner)
            step = step + 1
            if len(values) > 256:
                raise ValueError("too many values")
        return [values, pos]
    first = int_value(token)
    pos = pos + 1
    if peek(tokens, pos) == "..":
        pos = pos + 1
        kind2 = peek(tokens, pos)
        if kind2 != "int" and kind2 != "num":
            raise ValueError("bad range")
        second = int_value(tokens[pos])
        pos = pos + 1
        values = []
        if first <= second:
            current = first
            while current <= second:
                values.append(current)
                current = current + 1
        else:
            current = first
            while current >= second:
                values.append(current)
                current = current - 1
        if len(values) > 256:
            raise ValueError("too many values")
        return [values, pos]
    return [[first], pos]


def solve(expression):
    if not isinstance(expression, str):
        raise ValueError("text required")
    if expression.strip() == "":
        return []
    tokens = tokenize(expression)
    out = parse_expression(tokens, 0, 0)
    values = out[0]
    pos = out[1]
    if pos != len(tokens):
        raise ValueError("trailing junk")
    if len(values) > 256:
        raise ValueError("too many values")
    return values
