def solve(expression):
    if not isinstance(expression, str):
        raise ValueError("text required")
    tokens = tokenize(expression)
    stack = []
    cur = []
    pos = 0
    mode = "term"
    fresh = True
    while True:
        k = kind_at(tokens, pos)
        if mode == "term":
            if fresh and (k == "end" or k == ")"):
                mode = "sep"
                continue
            if k == "unum" and kind_at(tokens, pos + 1) == "*":
                count = tokens[pos][1]
                if count > 20:
                    raise ValueError("bad count")
                if kind_at(tokens, pos + 2) != "(":
                    raise ValueError("missing paren")
                if len(stack) + 1 > 12:
                    raise ValueError("too deep")
                stack.append((cur, count))
                cur = []
                pos = pos + 3
                fresh = True
                mode = "term"
                continue
            pos, part = read_atom(tokens, pos)
            cur.extend(part)
            check_size(cur)
            fresh = False
            mode = "sep"
            continue
        if k == ",":
            pos = pos + 1
            fresh = False
            mode = "term"
            continue
        if k == ")":
            if len(stack) == 0:
                raise ValueError("unmatched paren")
            outer, count = stack.pop()
            check_size(cur)
            body = cur
            cur = outer
            i = 0
            while i < count:
                cur.extend(body)
                check_size(cur)
                i = i + 1
            check_size(cur)
            pos = pos + 1
            fresh = False
            mode = "sep"
            continue
        if k == "end":
            if len(stack) != 0:
                raise ValueError("unclosed group")
            return cur
        raise ValueError("unexpected token")


def read_atom(tokens, pos):
    k = kind_at(tokens, pos)
    if k != "num" and k != "unum":
        raise ValueError("expected integer")
    first = check_int(tokens[pos][1])
    pos = pos + 1
    if kind_at(tokens, pos) != "..":
        return pos, [first]
    pos = pos + 1
    k2 = kind_at(tokens, pos)
    if k2 != "num" and k2 != "unum":
        raise ValueError("bad range")
    second = check_int(tokens[pos][1])
    pos = pos + 1
    out = []
    step = 1
    if first > second:
        step = -1
    v = first
    while True:
        out.append(v)
        check_size(out)
        if v == second:
            break
        v = v + step
    return pos, out


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
            tokens.append((ch, 0))
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
            value = int(text[start:j])
            if ch == "-":
                value = -value
            tokens.append(("num", value))
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


def check_size(values):
    if len(values) > 256:
        raise ValueError("too many values")
    return len(values)


def check_int(value):
    if value < -1000 or value > 1000:
        raise ValueError("integer limit")
    return value
