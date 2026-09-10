def solve(expression):
    if not isinstance(expression, str):
        raise ValueError("text required")
    tokens = tokenize(expression)
    if len(tokens) == 0:
        return []
    pair = parse_expression(tokens, 0, 0)
    values = pair[0]
    index = pair[1]
    if index != len(tokens):
        raise ValueError("junk")
    return values


def is_ascii_digit(character):
    return character >= "0" and character <= "9"


def tokenize(text):
    tokens = []
    i = 0
    n = len(text)
    while i < n:
        character = text[i]
        if character.isspace():
            i = i + 1
            continue
        if character == ".":
            if i + 1 < n and text[i + 1] == ".":
                tokens.append(["range", "..", 0])
                i = i + 2
                continue
            raise ValueError("bad dots")
        if character == "*" or character == "(" or character == ")" or character == ",":
            tokens.append([character, character, 0])
            i = i + 1
            continue
        if character == "+" or character == "-" or is_ascii_digit(character):
            start = i
            signed = 0
            if character == "+" or character == "-":
                signed = 1
                i = i + 1
            digits = 0
            while i < n and is_ascii_digit(text[i]):
                digits = digits + 1
                i = i + 1
            if digits == 0:
                raise ValueError("missing digits")
            tokens.append(["num", text[start:i], signed])
            continue
        raise ValueError("bad character")
    return tokens


def token_kind(tokens, index):
    if index < 0 or index >= len(tokens):
        return ""
    return tokens[index][0]


def integer_value(token):
    number = int(token[1])
    if number < -1000 or number > 1000:
        raise ValueError("integer limit")
    return number


def parse_expression(tokens, index, depth):
    values = []
    kind = token_kind(tokens, index)
    if kind == "" or kind == ")":
        return [values, index]
    while True:
        pair = parse_term(tokens, index, depth)
        values.extend(pair[0])
        index = pair[1]
        if len(values) > 256:
            raise ValueError("too many values")
        if token_kind(tokens, index) != ",":
            break
        index = index + 1
    return [values, index]


def parse_term(tokens, index, depth):
    if token_kind(tokens, index) != "num":
        raise ValueError("expected term")
    token = tokens[index]
    if token_kind(tokens, index + 1) == "*":
        return parse_repeat(tokens, index, depth)
    first = integer_value(token)
    if token_kind(tokens, index + 1) == "range":
        if token_kind(tokens, index + 2) != "num":
            raise ValueError("bad range")
        second = integer_value(tokens[index + 2])
        values = build_range(first, second)
        return [values, index + 3]
    return [[first], index + 1]


def build_range(first, second):
    if first <= second:
        step = 1
    else:
        step = -1
    values = []
    current = first
    while True:
        values.append(current)
        if len(values) > 256:
            raise ValueError("too many values")
        if current == second:
            break
        current = current + step
    return values


def parse_repeat(tokens, index, depth):
    token = tokens[index]
    if token[2] == 1:
        raise ValueError("signed count")
    count = int(token[1])
    if count < 0 or count > 20:
        raise ValueError("bad count")
    if token_kind(tokens, index + 2) != "(":
        raise ValueError("expected group")
    if depth + 1 > 12:
        raise ValueError("too deep")
    pair = parse_expression(tokens, index + 3, depth + 1)
    inner = pair[0]
    index = pair[1]
    if token_kind(tokens, index) != ")":
        raise ValueError("unclosed group")
    index = index + 1
    if len(inner) * count > 256:
        raise ValueError("too many values")
    values = []
    i = 0
    while i < count:
        values.extend(inner)
        i = i + 1
    return [values, index]
