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
            tokens.append(("comma", ""))
            index = index + 1
            continue
        if character == "*":
            tokens.append(("star", ""))
            index = index + 1
            continue
        if character == "(":
            tokens.append(("lp", ""))
            index = index + 1
            continue
        if character == ")":
            tokens.append(("rp", ""))
            index = index + 1
            continue
        if character == ".":
            if index + 1 < size and text[index + 1] == ".":
                tokens.append(("dots", ""))
                index = index + 2
                continue
            raise ValueError("bad dot")
        if character == "+" or character == "-" or (character >= "0" and character <= "9"):
            start = index
            if character == "+" or character == "-":
                index = index + 1
            digit_start = index
            while index < size and text[index] >= "0" and text[index] <= "9":
                index = index + 1
            if index == digit_start:
                raise ValueError("missing digits")
            tokens.append(("int", text[start:index]))
            continue
        raise ValueError("invalid character")
    return tokens


def integer_value(raw):
    number = int(raw)
    if number < -1000 or number > 1000:
        raise ValueError("integer limit")
    return number


def parse_expression(tokens, pos, depth):
    values = []
    if pos >= len(tokens) or tokens[pos][0] == "rp":
        return values, pos
    while True:
        piece, pos = parse_term(tokens, pos, depth)
        values.extend(piece)
        if len(values) > 256:
            raise ValueError("too many values")
        if pos < len(tokens) and tokens[pos][0] == "comma":
            pos = pos + 1
            if pos >= len(tokens) or tokens[pos][0] == "rp":
                raise ValueError("trailing comma")
            continue
        break
    return values, pos


def parse_term(tokens, pos, depth):
    if pos >= len(tokens) or tokens[pos][0] != "int":
        raise ValueError("expected integer")
    raw = tokens[pos][1]
    pos = pos + 1
    if pos < len(tokens) and tokens[pos][0] == "star":
        if not is_ascii_digits(raw):
            raise ValueError("signed count")
        count = int(raw)
        if count < 0 or count > 20:
            raise ValueError("count range")
        if depth + 1 > 12:
            raise ValueError("too deep")
        pos = pos + 1
        if pos >= len(tokens) or tokens[pos][0] != "lp":
            raise ValueError("expected (")
        pos = pos + 1
        inner, pos = parse_expression(tokens, pos, depth + 1)
        if pos >= len(tokens) or tokens[pos][0] != "rp":
            raise ValueError("expected )")
        pos = pos + 1
        if len(inner) > 256:
            raise ValueError("too many values")
        total = count * len(inner)
        if total > 256:
            raise ValueError("too many values")
        out = []
        step = 0
        while step < count:
            out.extend(inner)
            step = step + 1
        return out, pos
    first = integer_value(raw)
    if pos < len(tokens) and tokens[pos][0] == "dots":
        pos = pos + 1
        if pos >= len(tokens) or tokens[pos][0] != "int":
            raise ValueError("expected integer")
        second = integer_value(tokens[pos][1])
        pos = pos + 1
        out = []
        if first <= second:
            current = first
            while current <= second:
                out.append(current)
                current = current + 1
        else:
            current = first
            while current >= second:
                out.append(current)
                current = current - 1
        if len(out) > 256:
            raise ValueError("too many values")
        return out, pos
    return [first], pos


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
        raise ValueError("unexpected token")
    if len(values) > 256:
        raise ValueError("too many values")
    return values
