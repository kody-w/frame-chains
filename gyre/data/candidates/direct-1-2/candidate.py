def solve(expression):
    if not isinstance(expression, str):
        raise ValueError("text required")
    tokens = tokenize(expression)
    result = parse_expression(tokens, 0, 0)
    values = result[0]
    pos = result[1]
    if pos != len(tokens):
        raise ValueError("junk")
    if len(values) > 256:
        raise ValueError("too many values")
    return values


def is_ascii_digit(character):
    return character >= "0" and character <= "9"


def tokenize(text):
    tokens = []
    index = 0
    length = len(text)
    while index < length:
        character = text[index]
        if character.isspace():
            index = index + 1
            continue
        if character == ",":
            tokens.append(("comma", ""))
            index = index + 1
            continue
        if character == "*":
            tokens.append(("star", ""))
            index = index + 1
            continue
        if character == "(":
            tokens.append(("lpar", ""))
            index = index + 1
            continue
        if character == ")":
            tokens.append(("rpar", ""))
            index = index + 1
            continue
        if character == ".":
            if index + 1 < length and text[index + 1] == ".":
                tokens.append(("dots", ""))
                index = index + 2
                continue
            raise ValueError("bad dots")
        if character == "+" or character == "-" or is_ascii_digit(character):
            start = index
            if character == "+" or character == "-":
                index = index + 1
            digits = 0
            while index < length and is_ascii_digit(text[index]):
                index = index + 1
                digits = digits + 1
            if digits == 0:
                raise ValueError("missing digits")
            tokens.append(("int", text[start:index]))
            continue
        raise ValueError("bad character")
    return tokens


def token_kind(tokens, pos):
    if pos < 0 or pos >= len(tokens):
        return "end"
    return tokens[pos][0]


def to_number(literal):
    value = int(literal)
    if value < -1000 or value > 1000:
        raise ValueError("integer limit")
    return value


def parse_expression(tokens, pos, depth):
    values = []
    kind = token_kind(tokens, pos)
    if kind == "end" or kind == "rpar":
        return (values, pos)
    result = parse_term(tokens, pos, depth)
    values.extend(result[0])
    pos = result[1]
    if len(values) > 256:
        raise ValueError("too many values")
    while token_kind(tokens, pos) == "comma":
        result = parse_term(tokens, pos + 1, depth)
        values.extend(result[0])
        pos = result[1]
        if len(values) > 256:
            raise ValueError("too many values")
    return (values, pos)


def parse_term(tokens, pos, depth):
    if token_kind(tokens, pos) != "int":
        raise ValueError("expected integer")
    literal = tokens[pos][1]
    following = token_kind(tokens, pos + 1)
    if following == "dots":
        if token_kind(tokens, pos + 2) != "int":
            raise ValueError("bad range")
        start = to_number(literal)
        stop = to_number(tokens[pos + 2][1])
        values = []
        if start <= stop:
            current = start
            while current <= stop:
                values.append(current)
                current = current + 1
        else:
            current = start
            while current >= stop:
                values.append(current)
                current = current - 1
        if len(values) > 256:
            raise ValueError("too many values")
        return (values, pos + 3)
    if following == "star":
        if literal[0] == "+" or literal[0] == "-":
            raise ValueError("signed count")
        count = int(literal)
        if count < 0 or count > 20:
            raise ValueError("bad count")
        if token_kind(tokens, pos + 2) != "lpar":
            raise ValueError("expected (")
        if depth + 1 > 12:
            raise ValueError("too deep")
        inner = parse_expression(tokens, pos + 3, depth + 1)
        body = inner[0]
        next_pos = inner[1]
        if token_kind(tokens, next_pos) != "rpar":
            raise ValueError("expected )")
        if len(body) > 256:
            raise ValueError("too many values")
        values = []
        repeats = 0
        while repeats < count:
            values.extend(body)
            if len(values) > 256:
                raise ValueError("too many values")
            repeats = repeats + 1
        return (values, next_pos + 1)
    return ([to_number(literal)], pos + 1)
