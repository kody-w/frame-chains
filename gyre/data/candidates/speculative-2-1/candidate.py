def solve(expression):
    if not isinstance(expression, str):
        raise ValueError("text required")
    tokens = tokenize(expression)
    return run_machine(tokens)


def is_ascii_digit(ch):
    return ch >= "0" and ch <= "9"


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


def kind_at(tokens, pos):
    if pos >= len(tokens):
        return "end"
    return tokens[pos][0]


def check_size(values):
    if len(values) > 256:
        raise ValueError("too many values")
    return values


def check_int(value):
    if value < -1000 or value > 1000:
        raise ValueError("integer limit")
    return value


def span(first, second):
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
    return out


def repeat_body(body, count):
    out = []
    i = 0
    while i < count:
        out.extend(body)
        check_size(out)
        i = i + 1
    return out


def run_machine(tokens):
    stack_vals = []
    stack_counts = []
    cur = []
    fresh = True
    mode = "term"
    pos = 0
    while True:
        k = kind_at(tokens, pos)
        if mode == "term":
            if fresh and (k == "end" or k == ")"):
                mode = "close"
                continue
            if k == "unum" and kind_at(tokens, pos + 1) == "*":
                count = tokens[pos][1]
                if count > 20:
                    raise ValueError("bad count")
                if kind_at(tokens, pos + 2) != "(":
                    raise ValueError("missing paren")
                if len(stack_vals) + 1 > 12:
                    raise ValueError("too deep")
                stack_vals.append(cur)
                stack_counts.append(count)
                cur = []
                fresh = True
                pos = pos + 3
                continue
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
                cur.extend(span(first, second))
            else:
                cur.append(first)
            check_size(cur)
            fresh = False
            mode = "sep"
            continue
        if mode == "sep":
            if k == ",":
                pos = pos + 1
                fresh = False
                mode = "term"
                continue
            mode = "close"
            continue
        if len(stack_vals) == 0:
            if k == "end":
                return cur
            raise ValueError("trailing junk")
        if k != ")":
            raise ValueError("unclosed group")
        pos = pos + 1
        check_size(cur)
        count = stack_counts.pop()
        body = cur
        cur = stack_vals.pop()
        cur.extend(repeat_body(body, count))
        check_size(cur)
        fresh = False
        mode = "sep"
