def solve(expression):
    if not isinstance(expression, str):
        raise ValueError("text required")
    text = expression
    pos = skip_space(text, 0)
    if pos >= len(text):
        return []
    pos, values = parse_expr(text, pos, 0)
    pos = skip_space(text, pos)
    if pos != len(text):
        raise ValueError("trailing junk")
    return values


def skip_space(text, pos):
    n = len(text)
    while pos < n and text[pos].isspace():
        pos = pos + 1
    return pos


def is_ascii_digit(ch):
    return ch >= "0" and ch <= "9"


def peek(text, pos):
    if pos >= len(text):
        return ""
    return text[pos]


def check_size(values):
    if len(values) > 256:
        raise ValueError("too many values")
    return values


def check_int(value):
    if value < -1000 or value > 1000:
        raise ValueError("integer limit")
    return value


def scan_number(text, pos):
    n = len(text)
    sign = 0
    ch = peek(text, pos)
    if ch == "+" or ch == "-":
        sign = 1
        pos = pos + 1
    start = pos
    while pos < n and is_ascii_digit(text[pos]):
        pos = pos + 1
    if pos == start:
        raise ValueError("expected integer")
    digits = text[start:pos]
    value = int(digits)
    if peek(text, start - 1) == "-":
        value = -value
    return pos, value, sign


def parse_expr(text, pos, depth):
    values = []
    pos, part = parse_term(text, pos, depth)
    values.extend(part)
    check_size(values)
    pos = skip_space(text, pos)
    while peek(text, pos) == ",":
        pos = skip_space(text, pos + 1)
        pos, part = parse_term(text, pos, depth)
        values.extend(part)
        check_size(values)
        pos = skip_space(text, pos)
    return pos, values


def parse_group_body(text, pos, depth):
    pos = skip_space(text, pos)
    if peek(text, pos) == ")":
        return pos, []
    return parse_expr(text, pos, depth)


def parse_term(text, pos, depth):
    pos = skip_space(text, pos)
    ch = peek(text, pos)
    if ch == "":
        raise ValueError("unexpected end")
    if ch == "," or ch == ")" or ch == "(" or ch == "*":
        raise ValueError("expected term")
    pos, first, signed = scan_number(text, pos)
    after = skip_space(text, pos)
    if peek(text, after) == "*":
        if signed:
            raise ValueError("signed count")
        if first > 20:
            raise ValueError("bad count")
        after = skip_space(text, after + 1)
        if peek(text, after) != "(":
            raise ValueError("missing paren")
        if depth + 1 > 12:
            raise ValueError("too deep")
        after, body = parse_group_body(text, after + 1, depth + 1)
        after = skip_space(text, after)
        if peek(text, after) != ")":
            raise ValueError("unclosed group")
        after = after + 1
        check_size(body)
        out = []
        i = 0
        while i < first:
            out.extend(body)
            check_size(out)
            i = i + 1
        return after, out
    check_int(first)
    if peek(text, after) == ".":
        if peek(text, after + 1) != ".":
            raise ValueError("bad dot")
        rpos = skip_space(text, after + 2)
        ch2 = peek(text, rpos)
        if not (is_ascii_digit(ch2) or ch2 == "+" or ch2 == "-"):
            raise ValueError("bad range")
        rpos, second, ignored = scan_number(text, rpos)
        check_int(second)
        out = []
        v = first
        if first <= second:
            while v <= second:
                out.append(v)
                v = v + 1
        else:
            while v >= second:
                out.append(v)
                v = v - 1
        check_size(out)
        return rpos, out
    return pos, [first]
