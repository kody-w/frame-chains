def tokenize(text):
    tokens = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c.isspace():
            i = i + 1
            continue
        if c == "," or c == "*" or c == "(" or c == ")":
            tokens.append([c, c])
            i = i + 1
            continue
        if c == ".":
            if i + 1 < n and text[i + 1] == ".":
                tokens.append(["..", ".."])
                i = i + 2
                continue
            raise ValueError("bad dot")
        if c == "+" or c == "-":
            j = i + 1
            digits = ""
            while j < n and text[j] >= "0" and text[j] <= "9":
                digits = digits + text[j]
                j = j + 1
            if digits == "":
                raise ValueError("missing digits")
            tokens.append(["signed", c + digits])
            i = j
            continue
        if c >= "0" and c <= "9":
            j = i
            digits = ""
            while j < n and text[j] >= "0" and text[j] <= "9":
                digits = digits + text[j]
                j = j + 1
            tokens.append(["plain", digits])
            i = j
            continue
        raise ValueError("bad character")
    tokens.append(["end", ""])
    return tokens


def kind_at(tokens, pos):
    return tokens[pos][0]


def text_at(tokens, pos):
    return tokens[pos][1]


def is_number(tokens, pos):
    k = kind_at(tokens, pos)
    return k == "plain" or k == "signed"


def number_value(tokens, pos):
    value = int(text_at(tokens, pos))
    if value < -1000 or value > 1000:
        raise ValueError("integer limit")
    return value


def check_size(values):
    if len(values) > 256:
        raise ValueError("too many values")
    return values


def parse_expression(tokens, pos, depth):
    values = []
    if kind_at(tokens, pos) == ")" or kind_at(tokens, pos) == "end":
        return [values, pos]
    outcome = parse_term(tokens, pos, depth)
    values.extend(outcome[0])
    pos = outcome[1]
    check_size(values)
    while kind_at(tokens, pos) == ",":
        pos = pos + 1
        if kind_at(tokens, pos) == ")" or kind_at(tokens, pos) == "end":
            raise ValueError("trailing comma")
        outcome = parse_term(tokens, pos, depth)
        values.extend(outcome[0])
        pos = outcome[1]
        check_size(values)
    return [values, pos]


def parse_term(tokens, pos, depth):
    if kind_at(tokens, pos) == "plain" and kind_at(tokens, pos + 1) == "*":
        count = int(text_at(tokens, pos))
        if count > 20:
            raise ValueError("count limit")
        if depth + 1 > 12:
            raise ValueError("nesting limit")
        pos = pos + 2
        if kind_at(tokens, pos) != "(":
            raise ValueError("missing paren")
        pos = pos + 1
        outcome = parse_expression(tokens, pos, depth + 1)
        body = outcome[0]
        pos = outcome[1]
        if kind_at(tokens, pos) != ")":
            raise ValueError("missing close")
        pos = pos + 1
        check_size(body)
        if len(body) * count > 256:
            raise ValueError("too many values")
        values = []
        k = 0
        while k < count:
            values.extend(body)
            k = k + 1
        return [values, pos]
    if not is_number(tokens, pos):
        raise ValueError("expected term")
    first = number_value(tokens, pos)
    pos = pos + 1
    if kind_at(tokens, pos) == "..":
        pos = pos + 1
        if not is_number(tokens, pos):
            raise ValueError("bad range")
        second = number_value(tokens, pos)
        pos = pos + 1
        values = []
        if first <= second:
            step = 1
        else:
            step = -1
        current = first
        while True:
            values.append(current)
            if current == second:
                break
            current = current + step
            if len(values) > 256:
                raise ValueError("too many values")
        check_size(values)
        return [values, pos]
    return [[first], pos]


def solve(expression):
    if not isinstance(expression, str):
        raise ValueError("text required")
    if expression.strip() == "":
        return []
    tokens = tokenize(expression)
    outcome = parse_expression(tokens, 0, 0)
    values = outcome[0]
    pos = outcome[1]
    if kind_at(tokens, pos) != "end":
        raise ValueError("junk")
    return check_size(values)
