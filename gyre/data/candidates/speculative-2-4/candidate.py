def solve(expression):
    if not isinstance(expression, str):
        raise ValueError("text required")
    toks = lex(expression)
    state = [0]
    values = parse_expr(toks, state, 0)
    if state[0] != len(toks):
        raise ValueError("trailing junk")
    return values


def lex(text):
    toks = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch.isspace():
            i = i + 1
            continue
        if ch == "," or ch == "*" or ch == "(" or ch == ")":
            toks.append((ch, 0))
            i = i + 1
            continue
        if ch == ".":
            if i + 1 < n and text[i + 1] == ".":
                toks.append(("..", 0))
                i = i + 2
                continue
            raise ValueError("bad dot")
        if ch == "+" or ch == "-":
            j = i + 1
            s = j
            while j < n and digit(text[j]):
                j = j + 1
            if j == s:
                raise ValueError("missing digits")
            val = int(text[s:j])
            if ch == "-":
                val = -val
            toks.append(("signed", val))
            i = j
            continue
        if digit(ch):
            j = i
            while j < n and digit(text[j]):
                j = j + 1
            toks.append(("plain", int(text[i:j])))
            i = j
            continue
        raise ValueError("bad character")
    return toks


def digit(ch):
    return ch >= "0" and ch <= "9"


def peek(toks, state, offset=0):
    p = state[0] + offset
    if p >= len(toks):
        return "end"
    return toks[p][0]


def take(toks, state):
    p = state[0]
    state[0] = p + 1
    return toks[p][1]


def numeric(kind):
    return kind == "signed" or kind == "plain"


def cap(values):
    if len(values) > 256:
        raise ValueError("too many values")
    return values


def bounded(value):
    if value < -1000 or value > 1000:
        raise ValueError("integer limit")
    return value


def parse_expr(toks, state, depth):
    values = []
    head = peek(toks, state)
    if head == "end" or head == ")":
        return values
    values.extend(parse_term(toks, state, depth))
    cap(values)
    while peek(toks, state) == ",":
        state[0] = state[0] + 1
        values.extend(parse_term(toks, state, depth))
        cap(values)
    return values


def parse_term(toks, state, depth):
    head = peek(toks, state)
    if head == "plain" and peek(toks, state, 1) == "*":
        count = take(toks, state)
        state[0] = state[0] + 1
        if count > 20:
            raise ValueError("bad count")
        if peek(toks, state) != "(":
            raise ValueError("missing paren")
        if depth + 1 > 12:
            raise ValueError("too deep")
        state[0] = state[0] + 1
        body = parse_expr(toks, state, depth + 1)
        if peek(toks, state) != ")":
            raise ValueError("unclosed group")
        state[0] = state[0] + 1
        cap(body)
        out = []
        i = 0
        while i < count:
            out.extend(body)
            cap(out)
            i = i + 1
        return out
    if not numeric(head):
        raise ValueError("expected integer")
    first = bounded(take(toks, state))
    if peek(toks, state) != "..":
        return [first]
    state[0] = state[0] + 1
    if not numeric(peek(toks, state)):
        raise ValueError("bad range")
    second = bounded(take(toks, state))
    out = []
    step = 1
    if first > second:
        step = -1
    v = first
    while True:
        out.append(v)
        if v == second:
            break
        v = v + step
        if len(out) > 4000:
            raise ValueError("too many values")
    return cap(out)
