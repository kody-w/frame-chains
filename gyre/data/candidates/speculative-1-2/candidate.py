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


def check_int(word):
    start = 0
    if word[0] == "+" or word[0] == "-":
        start = 1
    if start == len(word):
        raise ValueError("missing digits")
    k = start
    while k < len(word):
        c = word[k]
        if c < "0" or c > "9":
            raise ValueError("bad digit")
        k = k + 1
    value = int(word)
    if value < -1000 or value > 1000:
        raise ValueError("integer limit")
    return value


def parse_expression(tokens, pos, depth):
    if depth > 12:
        raise ValueError("too deep")
    out = []
    if pos >= len(tokens) or tokens[pos][0] == ")":
        return [out, pos]
    while True:
        piece = parse_term(tokens, pos, depth)
        values = piece[0]
        pos = piece[1]
        out.extend(values)
        if len(out) > 256:
            raise ValueError("too many values")
        if pos < len(tokens) and tokens[pos][0] == ",":
            pos = pos + 1
            if pos >= len(tokens) or tokens[pos][0] == "," or tokens[pos][0] == ")":
                raise ValueError("empty element")
            continue
        break
    return [out, pos]


def parse_term(tokens, pos, depth):
    if pos >= len(tokens):
        raise ValueError("unexpected end")
    kind = tokens[pos][0]
    word = tokens[pos][1]
    if kind == "num" and pos + 1 < len(tokens) and tokens[pos + 1][0] == "*":
        count = int(word)
        if count < 0 or count > 20:
            raise ValueError("bad count")
        pos = pos + 2
        if pos >= len(tokens) or tokens[pos][0] != "(":
            raise ValueError("missing paren")
        pos = pos + 1
        inner = parse_expression(tokens, pos, depth + 1)
        body = inner[0]
        pos = inner[1]
        if pos >= len(tokens) or tokens[pos][0] != ")":
            raise ValueError("missing close")
        pos = pos + 1
        total = len(body) * count
        if total > 256:
            raise ValueError("too many values")
        out = []
        r = 0
        while r < count:
            out.extend(body)
            r = r + 1
        return [out, pos]
    if kind != "num" and kind != "int":
        raise ValueError("bad token")
    first = check_int(word)
    pos = pos + 1
    if pos < len(tokens) and tokens[pos][0] == "..":
        pos = pos + 1
        if pos >= len(tokens) or (tokens[pos][0] != "num" and tokens[pos][0] != "int"):
            raise ValueError("bad range")
        second = check_int(tokens[pos][1])
        pos = pos + 1
        out = []
        if second >= first:
            v = first
            while v <= second:
                out.append(v)
                v = v + 1
        else:
            v = first
            while v >= second:
                out.append(v)
                v = v - 1
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
    if len(tokens) == 0:
        return []
    if tokens[0][0] == ",":
        raise ValueError("empty element")
    parsed = parse_expression(tokens, 0, 0)
    result = parsed[0]
    pos = parsed[1]
    if pos != len(tokens):
        raise ValueError("junk")
    if len(result) > 256:
        raise ValueError("too many values")
    return result
