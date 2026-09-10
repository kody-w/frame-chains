def solve(expression):
    if not isinstance(expression, str):
        raise ValueError("text required")
    tokens = tokenize(expression)
    pos, values = parse_expression(tokens, 0, 0)
    if pos != len(tokens):
        raise ValueError("junk")
    return values


def tokenize(text):
    tokens = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch.isspace():
            i = i + 1
            continue
        if ch == ",":
            tokens.append((",", 0))
            i = i + 1
            continue
        if ch == "*":
            tokens.append(("*", 0))
            i = i + 1
            continue
        if ch == "(":
            tokens.append(("(", 0))
            i = i + 1
            continue
        if ch == ")":
            tokens.append((")", 0))
            i = i + 1
            continue
        if ch == ".":
            if i + 1 < n and text[i + 1] == ".":
                tokens.append(("..", 0))
                i = i + 2
                continue
            raise ValueError("bad dot")
        if ch == "+" or ch == "-":
            j = i + 1
            digits = ""
            while j < n and is_ascii_digit(text[j]):
                digits = digits + text[j]
                j = j + 1
            if digits == "":
                raise ValueError("missing digits")
            tokens.append(("signed", int(ch + digits)))
            i = j
            continue
        if is_ascii_digit(ch):
            j = i
            digits = ""
            while j < n and is_ascii_digit(text[j]):
                digits = digits + text[j]
                j = j + 1
            if len(digits) > 6:
                raise ValueError("too long")
            tokens.append(("plain", int(digits)))
            i = j
            continue
        raise ValueError("bad character")
    return tokens


def is_ascii_digit(ch):
    return ch >= "0" and ch <= "9"


def peek(tokens, pos):
    if pos < len(tokens):
        return tokens[pos][0]
    return "end"


def check_integer(value):
    if value < -1000 or value > 1000:
        raise ValueError("integer limit")
    return value


def parse_expression(tokens, pos, depth):
    values = []
    kind = peek(tokens, pos)
    if kind == "end" or kind == ")":
        return pos, values
    pos, part = parse_term(tokens, pos, depth)
    values.extend(part)
    if len(values) > 256:
        raise ValueError("too many values")
    while peek(tokens, pos) == ",":
        pos, part = parse_term(tokens, pos + 1, depth)
        values.extend(part)
        if len(values) > 256:
            raise ValueError("too many values")
    return pos, values


def parse_term(tokens, pos, depth):
    kind = peek(tokens, pos)
    if kind == "plain" and peek(tokens, pos + 1) == "*":
        count = tokens[pos][1]
        if count > 20:
            raise ValueError("count range")
        if peek(tokens, pos + 2) != "(":
            raise ValueError("missing paren")
        if depth + 1 > 12:
            raise ValueError("too deep")
        pos, inner = parse_expression(tokens, pos + 3, depth + 1)
        if peek(tokens, pos) != ")":
            raise ValueError("unclosed group")
        pos = pos + 1
        if len(inner) * count > 256:
            raise ValueError("too many values")
        out = []
        i = 0
        while i < count:
            out.extend(inner)
            i = i + 1
        return pos, out
    if kind != "plain" and kind != "signed":
        raise ValueError("expected integer")
    first = check_integer(tokens[pos][1])
    pos = pos + 1
    if peek(tokens, pos) != "..":
        return pos, [first]
    kind2 = peek(tokens, pos + 1)
    if kind2 != "plain" and kind2 != "signed":
        raise ValueError("bad range")
    second = check_integer(tokens[pos + 1][1])
    pos = pos + 2
    out = []
    if first <= second:
        step = 1
    else:
        step = -1
    value = first
    while True:
        out.append(value)
        if len(out) > 256:
            raise ValueError("too many values")
        if value == second:
            break
        value = value + step
    return pos, out
