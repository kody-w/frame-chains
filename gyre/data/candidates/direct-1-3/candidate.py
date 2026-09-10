def is_ascii_digits(text):
    if len(text) == 0:
        return False
    for character in text:
        if character < "0" or character > "9":
            return False
    return True


def tokenize(text):
    tokens = []
    index = 0
    size = len(text)
    while index < size:
        character = text[index]
        if character.isspace():
            index = index + 1
            continue
        if character == ",":
            tokens.append(("comma", "", False))
            index = index + 1
            continue
        if character == "*":
            tokens.append(("star", "", False))
            index = index + 1
            continue
        if character == "(":
            tokens.append(("lparen", "", False))
            index = index + 1
            continue
        if character == ")":
            tokens.append(("rparen", "", False))
            index = index + 1
            continue
        if character == ".":
            if index + 1 < size and text[index + 1] == ".":
                tokens.append(("dots", "", False))
                index = index + 2
                continue
            raise ValueError("bad dot")
        if character == "+" or character == "-":
            start = index
            index = index + 1
            digits = ""
            while index < size and text[index] >= "0" and text[index] <= "9":
                digits = digits + text[index]
                index = index + 1
            if len(digits) == 0:
                raise ValueError("missing digits")
            tokens.append(("num", text[start] + digits, True))
            continue
        if character >= "0" and character <= "9":
            digits = ""
            while index < size and text[index] >= "0" and text[index] <= "9":
                digits = digits + text[index]
                index = index + 1
            tokens.append(("num", digits, False))
            continue
        raise ValueError("bad character")
    return tokens


def token_kind(tokens, pos):
    if pos < 0 or pos >= len(tokens):
        return "end"
    return tokens[pos][0]


def number_value(token):
    text = token[1]
    body = text
    if token[2]:
        body = text[1:]
    if not is_ascii_digits(body):
        raise ValueError("bad integer")
    value = int(text)
    if value < -1000 or value > 1000:
        raise ValueError("integer limit")
    return value


def parse_term(tokens, pos, depth):
    if token_kind(tokens, pos) != "num":
        raise ValueError("expected term")
    token = tokens[pos]
    pos = pos + 1
    if token_kind(tokens, pos) == "dots":
        pos = pos + 1
        if token_kind(tokens, pos) != "num":
            raise ValueError("bad range")
        start = number_value(token)
        stop = number_value(tokens[pos])
        pos = pos + 1
        values = []
        if start <= stop:
            if stop - start + 1 > 256:
                raise ValueError("too many values")
            current = start
            while current <= stop:
                values.append(current)
                current = current + 1
        else:
            if start - stop + 1 > 256:
                raise ValueError("too many values")
            current = start
            while current >= stop:
                values.append(current)
                current = current - 1
        return values, pos
    if token_kind(tokens, pos) == "star":
        if token[2]:
            raise ValueError("signed count")
        if not is_ascii_digits(token[1]):
            raise ValueError("bad count")
        count = int(token[1])
        if count < 0 or count > 20:
            raise ValueError("count range")
        if depth + 1 > 12:
            raise ValueError("too deep")
        pos = pos + 1
        if token_kind(tokens, pos) != "lparen":
            raise ValueError("expected (")
        pos = pos + 1
        inner, pos = parse_expression(tokens, pos, depth + 1)
        if token_kind(tokens, pos) != "rparen":
            raise ValueError("expected )")
        pos = pos + 1
        if len(inner) * count > 256:
            raise ValueError("too many values")
        values = []
        repeat = 0
        while repeat < count:
            values.extend(inner)
            repeat = repeat + 1
        return values, pos
    return [number_value(token)], pos


def parse_expression(tokens, pos, depth):
    values = []
    kind = token_kind(tokens, pos)
    if kind == "end" or kind == "rparen":
        return values, pos
    part, pos = parse_term(tokens, pos, depth)
    values.extend(part)
    if len(values) > 256:
        raise ValueError("too many values")
    while token_kind(tokens, pos) == "comma":
        pos = pos + 1
        part, pos = parse_term(tokens, pos, depth)
        values.extend(part)
        if len(values) > 256:
            raise ValueError("too many values")
    return values, pos


def solve(expression):
    if not isinstance(expression, str):
        raise ValueError("text required")
    if expression.strip() == "":
        return []
    tokens = tokenize(expression)
    if len(tokens) == 0:
        return []
    values, pos = parse_expression(tokens, 0, 0)
    if pos != len(tokens):
        raise ValueError("trailing junk")
    if len(values) > 256:
        raise ValueError("too many values")
    return values
