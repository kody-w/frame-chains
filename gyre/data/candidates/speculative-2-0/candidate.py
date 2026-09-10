def solve(expression):
    if not isinstance(expression, str):
        raise ValueError("text required")
    tokens = scan(expression)
    state = [tokens, 0]
    values = read_expr(state, 0)
    if state[1] != len(tokens):
        raise ValueError("trailing junk")
    return values


def scan(text):
    tokens = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch.isspace():
            i = i + 1
            continue
        if ch == "," or ch == "*" or ch == "(" or ch == ")":
            tokens.append([ch, 0])
            i = i + 1
            continue
        if ch == ".":
            if i + 1 < n and text[i + 1] == ".":
                tokens.append(["..", 0])
                i = i + 2
                continue
            raise ValueError("bad dot")
        if ch == "+" or ch == "-":
            j = i + 1
            digits = grab_digits(text, j)
            if digits == j:
                raise ValueError("missing digits")
            magnitude = int(text[j:digits])
            if ch == "-":
                tokens.append(["signed", 0 - magnitude])
            else:
                tokens.append(["signed", magnitude])
            i = digits
            continue
        digits = grab_digits(text, i)
        if digits == i:
            raise ValueError("bad character")
        tokens.append(["bare", int(text[i:digits])])
        i = digits
    return tokens


def grab_digits(text, start):
    j = start
    while j < len(text):
        ch = text[j]
        if ch >= "0" and ch <= "9":
            j = j + 1
        else:
            return j
    return j


def peek(state, offset=0):
    tokens = state[0]
    idx = state[1] + offset
    if idx >= len(tokens):
        return "end"
    return tokens[idx][0]


def value_at(state, offset=0):
    return state[0][state[1] + offset][1]


def advance(state, amount=1):
    state[1] = state[1] + amount
    return state[1]


def cap(values):
    if len(values) > 256:
        raise ValueError("too many values")
    return values


def bounded(value):
    if value < -1000 or value > 1000:
        raise ValueError("integer limit")
    return value


def read_expr(state, depth):
    values = []
    head = peek(state)
    if head == "end" or head == ")":
        return values
    values.extend(read_term(state, depth))
    cap(values)
    while peek(state) == ",":
        advance(state)
        values.extend(read_term(state, depth))
        cap(values)
    return values


def read_term(state, depth):
    head = peek(state)
    if head == "bare" and peek(state, 1) == "*":
        return read_group(state, depth)
    if head != "bare" and head != "signed":
        raise ValueError("expected integer")
    left = bounded(value_at(state))
    advance(state)
    if peek(state) != "..":
        return [left]
    advance(state)
    tail = peek(state)
    if tail != "bare" and tail != "signed":
        raise ValueError("bad range")
    right = bounded(value_at(state))
    advance(state)
    return cap(span(left, right))


def span(left, right):
    out = []
    step = 1
    if left > right:
        step = -1
    v = left
    while True:
        out.append(v)
        if v == right:
            return out
        if len(out) > 4000:
            raise ValueError("too many values")
        v = v + step


def read_group(state, depth):
    count = value_at(state)
    if count > 20:
        raise ValueError("bad count")
    if peek(state, 2) != "(":
        raise ValueError("missing paren")
    if depth + 1 > 12:
        raise ValueError("too deep")
    advance(state, 3)
    body = cap(read_expr(state, depth + 1))
    if peek(state) != ")":
        raise ValueError("unclosed group")
    advance(state)
    out = []
    i = 0
    while i < count:
        out.extend(body)
        cap(out)
        i = i + 1
    return out
