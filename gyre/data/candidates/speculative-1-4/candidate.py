def solve(expression):
    if not isinstance(expression, str):
        raise ValueError("text required")
    tokens = tokenize(expression)
    pos, values = parse_expr(tokens, 0, 0)
    if pos != len(tokens):
        raise ValueError("trailing junk")
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
            start = j
            while j < n and is_ascii_digit(text[j]):
                j = j + 1
            if j == start:
                raise ValueError("missing digits")
            tokens.append(("num", int(ch + text[start:j])))
            i = j
            continue
        if is_ascii_digit(ch):
            j = i
            while j < n and is_ascii_digit(text[j]):
                j = j + 1
            tokens.append(("unum", int(text[i:j])))
            i = j
            continue
        raise ValueError("bad character")
    return tokens


def is_ascii_digit(ch):
    return ch >= "0" and ch <= "9"


def kind_at(tokens, pos):
    if pos >= len(tokens):
        return "end"
    return tokens[pos][0]


def parse_expr(tokens, pos, depth):
    values = []
    k = kind_at(tokens, pos)
    if k == "end" or k == ")":
        return pos, values
    pos, part = parse_term(tokens, pos, depth)
    values.extend(part)
    check_size(values)
    while kind_at(tokens, pos) == ",":
        pos = pos + 1
        pos, part = parse_term(tokens, pos, depth)
        values.extend(part)
        check_size(values)
    return pos, values


def check_size(values):
    if len(values) > 256:
        raise ValueError("too many values")


def check_int(value):
    if value < -1000 or value > 1000:
        raise ValueError("integer limit")
    return value


def parse_term(tokens, pos, depth):
    k = kind_at(tokens, pos)
    if k == "unum" and kind_at(tokens, pos + 1) == "*":
        count = tokens[pos][1]
        if count > 20:
            raise ValueError("bad count")
        if kind_at(tokens, pos + 2) != "(":
            raise ValueError("missing paren")
        if depth + 1 > 12:
            raise ValueError("too deep")
        pos, body = parse_expr(tokens, pos + 3, depth + 1)
        if kind_at(tokens, pos) != ")":
            raise ValueError("unclosed group")
        pos = pos + 1
        check_size(body)
        out = []
        i = 0
        while i < count:
            out.extend(body)
            check_size(out)
            i = i + 1
        return pos, out
    if k != "num" and k != "unum":
        raise ValueError("expected integer")
    first = check_int(tokens[pos][1])
    pos = pos + 1
    if kind_at(tokens, pos) == "..":
        pos = pos + 1
        k2 = kind_at(tokens, pos)
        if k2 != "num" and k2 != "unum":
            raise ValueError("bad range")
        second = check_int(tokens[pos][1])
        pos = pos + 1
        out = []
        if first <= second:
            v = first
            while v <= second:
                out.append(v)
                v = v + 1
        else:
            v = first
            while v >= second:
                out.append(v)
                v = v - 1
        check_size(out)
        return pos, out
    return pos, [first]
