"""Contract-derived oracle, written before reading pilot solvers or evaluators.

This parser uses a token stream and an explicit stack of repeat-group states.
It does not import pilot code, fixture gold values, or the bounded interpreter.
"""


class ContractError(ValueError):
    pass


def _tokens(text):
    result = []
    cursor = 0
    while cursor < len(text):
        char = text[cursor]
        if char.isspace():
            cursor += 1
            continue
        start = cursor
        if char in "+-" or "0" <= char <= "9":
            if char in "+-":
                cursor += 1
            digits = cursor
            while cursor < len(text) and "0" <= text[cursor] <= "9":
                cursor += 1
            if cursor == digits:
                raise ContractError("sign without adjacent ASCII digits")
            result.append(("number", text[start:cursor]))
        elif text.startswith("..", cursor):
            result.append(("range", ".."))
            cursor += 2
        elif char in "*(),":
            result.append((char, char))
            cursor += 1
        else:
            raise ContractError("unknown token")
    result.append(("end", ""))
    return result


def _number(spelling, limit, unsigned=False):
    if unsigned and spelling[:1] in ("+", "-"):
        raise ContractError("signed repeat count")
    negative = spelling.startswith("-")
    magnitude = spelling.lstrip("+-").lstrip("0") or "0"
    ceiling = str(limit)
    if len(magnitude) > len(ceiling) or (
        len(magnitude) == len(ceiling) and magnitude > ceiling
    ):
        raise ContractError("number outside contract")
    value = int(magnitude)
    return -value if negative else value


def solve(expression):
    if not isinstance(expression, str):
        raise ContractError("input must be a string")
    tokens = _tokens(expression)
    # values, expecting a term, immediately after a comma, repeat multiplier
    groups = [[[], True, False, 1]]
    cursor = 0

    def append_term(values):
        group = groups[-1]
        if len(values) > 256 or len(group[0]) + len(values) > 256:
            raise ContractError("expanded expression exceeds contract")
        group[0].extend(values)
        group[1] = False
        group[2] = False

    while True:
        kind, spelling = tokens[cursor]
        group = groups[-1]
        if kind in (")", "end"):
            if group[2]:
                raise ContractError("trailing comma")
            if kind == "end":
                if len(groups) != 1:
                    raise ContractError("unclosed repeat group")
                return group[0]
            if len(groups) == 1:
                raise ContractError("unmatched closing parenthesis")
            values, _, _, multiplier = groups.pop()
            if len(values) * multiplier > 256:
                raise ContractError("repeat term exceeds contract")
            append_term(values * multiplier)
            cursor += 1
            continue
        if not group[1]:
            if kind != ",":
                raise ContractError("missing separator")
            group[1] = True
            group[2] = True
            cursor += 1
            continue
        if kind != "number":
            raise ContractError("expected integer or repeat")
        following = tokens[cursor + 1][0]
        if following == "*":
            multiplier = _number(spelling, 20, unsigned=True)
            if tokens[cursor + 2][0] != "(":
                raise ContractError("repeat requires a group")
            if len(groups) > 12:
                raise ContractError("more than twelve repeat groups")
            groups.append([[], True, False, multiplier])
            cursor += 3
            continue
        start = _number(spelling, 1000)
        if following == "range":
            end_kind, end_spelling = tokens[cursor + 2]
            if end_kind != "number":
                raise ContractError("range needs an endpoint")
            end = _number(end_spelling, 1000)
            length = abs(end - start) + 1
            if length > 256:
                raise ContractError("range term exceeds contract")
            step = 1 if end >= start else -1
            append_term([start + step * offset for offset in range(length)])
            cursor += 3
        else:
            append_term([start])
            cursor += 1
