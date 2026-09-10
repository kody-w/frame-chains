def solve(expression):
    if not isinstance(expression, str):
        raise ValueError("text required")
    text = expression.strip()
    if text == "":
        return []
    result = []
    parts = text.split(",")
    if len(parts) > 256:
        raise ValueError("too many values")
    for part in parts:
        token = part.strip()
        if token == "":
            raise ValueError("empty token")
        start = 0
        if token[0] == "+" or token[0] == "-":
            start = 1
        if start == len(token):
            raise ValueError("missing digits")
        for character in token[start:]:
            if character < "0" or character > "9":
                raise ValueError("invalid integer")
        number = int(token)
        if number < -1000 or number > 1000:
            raise ValueError("integer limit")
        result.append(number)
    return result
