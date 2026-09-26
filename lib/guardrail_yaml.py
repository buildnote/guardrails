#!/usr/bin/env python3
import re


INTEGER = re.compile(r"^[-+]?(?:0|[1-9][0-9]*)$")
FLOAT = re.compile(r"^[-+]?(?:(?:0|[1-9][0-9]*)\.[0-9]*|\.[0-9]+)(?:[eE][-+][0-9]+)?$")
CODED = re.compile(r"^([xuU])([0-9a-fA-F]+)$")
NAME = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.\-]*")
HEADER = re.compile(r"^([|>])([+-]?)[ \t]*(#.*)?$")
START = re.compile(r"^---([ \t].*)?$")
END = re.compile(r"^\.\.\.([ \t].*)?$")

NULLS = ("", "~", "null", "Null", "NULL")
TRUTHS = ("true", "True", "TRUE", "yes", "Yes", "YES", "on", "On", "ON")
FALSEHOODS = ("false", "False", "FALSE", "no", "No", "NO", "off", "Off", "OFF")
ESCAPES = {
    "n": "\n",
    "t": "\t",
    "r": "\r",
    "b": "\b",
    "f": "\f",
    "0": "\0",
    "\"": "\"",
    "'": "'",
    "\\": "\\",
    "/": "/",
    " ": " ",
}


class Unparsable(Exception):
    def __init__(self, construct, line):
        Exception.__init__(self, "%s at line %d" % (construct, line))
        self.reason = "%s at line %d" % (construct, line)


class Reader(object):
    def __init__(self, lines, offset):
        self.lines = list(lines)
        self.offset = offset
        self.at = 0

    def number(self):
        return self.offset + min(self.at, len(self.lines) - 1) + 1

    def skip(self):
        while self.at < len(self.lines):
            stripped = self.lines[self.at].strip()
            if stripped and not stripped.startswith("#"):
                return True
            self.at += 1
        return False

    def more(self):
        return self.at < len(self.lines)

    def raw(self):
        return self.lines[self.at]

    def content(self):
        return self.lines[self.at].strip()

    def take(self):
        self.at += 1

    def indent(self):
        return measured(self.raw(), self.number())


def measured(line, number):
    width = len(line) - len(line.lstrip(" "))
    head = line[width:width + 1]
    if head == "\t":
        raise Unparsable("tab indentation", number)
    if head.isspace():
        raise Unparsable("non-space indentation", number)
    return width


def is_item(content):
    return content == "-" or content.startswith("- ")


def named(text):
    return NAME.match(text) is not None


def reject(content, number):
    head = content[:1]
    if head == "&" and named(content[1:]):
        raise Unparsable("anchor", number)
    if head == "*" and named(content[1:]):
        raise Unparsable("alias", number)
    if head == "!":
        raise Unparsable("tag", number)
    if content == "?" or content.startswith("? "):
        raise Unparsable("complex key", number)


def quoted(text, at, number):
    quote = text[at]
    at += 1
    value = ""
    while at < len(text):
        char = text[at]
        if char == quote:
            if quote == "'" and text[at + 1:at + 2] == "'":
                value += "'"
                at += 2
                continue
            return value, at + 1
        if quote == "\"" and char == "\\":
            escape = text[at + 1:at + 2]
            if escape in ESCAPES:
                value += ESCAPES[escape]
                at += 2
                continue
            width = {"x": 2, "u": 4, "U": 8}.get(escape)
            if width is None:
                raise Unparsable("unsupported escape", number)
            coded = CODED.match(escape + text[at + 2:at + 2 + width])
            if coded is None or len(coded.group(2)) != width:
                raise Unparsable("unsupported escape", number)
            value += chr(int(coded.group(2), 16))
            at += 2 + width
            continue
        value += char
        at += 1
    raise Unparsable("unterminated quote", number)


def uncommented(text):
    at = 0
    while at < len(text):
        if text[at] == "#" and (at == 0 or text[at - 1] in " \t"):
            return text[:at].strip()
        at += 1
    return text.strip()


def tail(text, number):
    rest = text.strip()
    if rest and not rest.startswith("#"):
        raise Unparsable("unexpected content", number)


def plain(text):
    if text in NULLS:
        return None
    if text in TRUTHS:
        return True
    if text in FALSEHOODS:
        return False
    if INTEGER.match(text):
        return int(text)
    if FLOAT.match(text):
        return float(text)
    return text


def scalar(text, number):
    if text[:1] in ("\"", "'"):
        value, at = quoted(text, 0, number)
        tail(text[at:], number)
        return value
    return plain(uncommented(text))


def matching(text, number):
    closing = "]" if text[0] == "[" else "}"
    at = 1
    while at < len(text):
        char = text[at]
        if char in ("\"", "'"):
            ignored, at = quoted(text, at, number)
            continue
        if char in ("[", "{"):
            raise Unparsable("nested flow collection", number)
        if char in ("]", "}"):
            if char != closing:
                raise Unparsable("unterminated flow collection", number)
            return at
        at += 1
    raise Unparsable("multi-line flow collection", number)


def entries(inner, number):
    items = []
    current = ""
    at = 0
    while at < len(inner):
        char = inner[at]
        if char in ("\"", "'"):
            ignored, to = quoted(inner, at, number)
            current += inner[at:to]
            at = to
            continue
        if char == ",":
            items.append(current.strip())
            current = ""
            at += 1
            continue
        current += char
        at += 1
    items.append(current.strip())
    if items and items[-1] == "":
        items.pop()
    for item in items:
        if item == "":
            raise Unparsable("empty flow entry", number)
    return items


def flow(text, number):
    end = matching(text, number)
    tail(text[end + 1:], number)
    inner = text[1:end].strip()
    items = entries(inner, number) if inner else []
    if text[0] == "[":
        values = []
        for item in items:
            reject(item, number)
            values.append(scalar(item, number))
        return values
    result = {}
    for item in items:
        reject(item, number)
        entry = keyed(item, number)
        if entry is None:
            raise Unparsable("flow mapping entry", number)
        name, rest = entry
        if name == "<<":
            raise Unparsable("merge key", number)
        result[name] = scalar(rest.strip(), number) if rest.strip() else None
    return result


def keyed(content, number):
    if content[:1] in ("\"", "'"):
        name, at = quoted(content, 0, number)
        rest = content[at:]
        if not rest.startswith(":"):
            return None
        return name, rest[1:]
    at = 0
    while at < len(content):
        char = content[at]
        if char == "#" and (at == 0 or content[at - 1] in " \t"):
            return None
        if char == ":" and (at + 1 == len(content) or content[at + 1] in " \t"):
            name = content[:at].strip()
            if not name:
                return None
            return name, content[at + 1:]
        at += 1
    return None


def blank(line):
    return line.strip() == ""


def folded(lines):
    text = ""
    breaks = 0
    started = False
    literal = False
    for line in lines:
        if blank(line):
            breaks += 1
            continue
        indented = line[:1] == " "
        if started:
            if breaks:
                text += "\n" * breaks
            elif literal or indented:
                text += "\n"
            else:
                text += " "
        text += line
        breaks = 0
        started = True
        literal = indented
    return text


def block_scalar(reader, indent, style, chomping):
    body = []
    width = None
    while reader.more():
        line = reader.raw()
        if blank(line):
            body.append(line[width:] if width is not None else "")
            reader.take()
            continue
        here = len(line) - len(line.lstrip(" "))
        if width is None or here < width:
            here = measured(line, reader.number())
        if width is None:
            if here <= indent:
                break
            width = here
        elif here < width:
            break
        body.append(line[width:])
        reader.take()

    trailing = 0
    while body and blank(body[-1]):
        body.pop()
        trailing += 1

    breaks = trailing if not reader.more() else trailing + 1
    text = "\n".join(body) if style == "|" else folded(body)
    if chomping == "-" or not breaks:
        return text
    if chomping == "+":
        return text + "\n" * breaks
    return text + "\n" if text else ""


def plain_block(reader, indent):
    parts = []
    breaks = 0
    started = False
    while reader.more():
        line = reader.raw()
        stripped = line.strip()
        if stripped == "":
            breaks += 1
            reader.take()
            continue
        if stripped.startswith("#"):
            reader.take()
            continue
        here = reader.indent()
        if here < indent:
            break
        if started and (is_item(stripped) or keyed(stripped, reader.number()) is not None):
            raise Unparsable("unexpected content", reader.number())
        reject(stripped, reader.number())
        piece = uncommented(stripped)
        if started:
            parts.append("\n" * breaks if breaks else " ")
        parts.append(piece)
        breaks = 0
        started = True
        reader.take()
    return plain("".join(parts))


def inline(reader, text, indent, number):
    text = text.strip()
    if text[:1] in ("|", ">"):
        header = HEADER.match(text)
        if header is None:
            raise Unparsable("block scalar header", number)
        return block_scalar(reader, indent, header.group(1), header.group(2))
    if text == "" or text.startswith("#"):
        if not reader.skip():
            return None
        here = reader.indent()
        if here > indent:
            return block(reader, indent + 1)
        if here == indent and is_item(reader.content()):
            return sequence(reader, indent)
        return None
    reject(text, number)
    if text[:1] in ("[", "{"):
        return flow(text, number)
    return scalar(text, number)


def mapping(reader, indent):
    result = {}
    while reader.skip():
        at = reader.at
        here = reader.indent()
        if here < indent:
            break
        if here > indent:
            raise Unparsable("unexpected indentation", reader.number())
        content = reader.content()
        number = reader.number()
        reject(content, number)
        split = keyed(content, number)
        if split is None:
            raise Unparsable("unexpected content", number)
        name, rest = split
        if name == "<<":
            raise Unparsable("merge key", number)
        reader.take()
        result[name] = inline(reader, rest, indent, number)
        if reader.at <= at:
            raise Unparsable("unexpected content", number)
    return result


def sequence(reader, indent):
    items = []
    while reader.skip():
        at = reader.at
        here = reader.indent()
        if here < indent:
            break
        if here > indent:
            raise Unparsable("unexpected indentation", reader.number())
        content = reader.content()
        if not is_item(content):
            break
        line = reader.raw()
        reader.lines[at] = line[:here] + " " + line[here + 1:]
        items.append(block(reader, here + 1))
        if reader.at <= at:
            raise Unparsable("unexpected content", reader.number())
    return items


def block(reader, minimum):
    if not reader.skip():
        return None
    indent = reader.indent()
    if indent < minimum:
        return None
    content = reader.content()
    number = reader.number()
    reject(content, number)
    if is_item(content):
        return sequence(reader, indent)
    if content[:1] in ("|", ">"):
        header = HEADER.match(content)
        if header is None:
            raise Unparsable("block scalar header", number)
        reader.take()
        return block_scalar(reader, indent, header.group(1), header.group(2))
    if content[:1] in ("[", "{"):
        reader.take()
        return flow(content, number)
    if keyed(content, number) is not None:
        return mapping(reader, indent)
    if content[:1] in ("\"", "'"):
        reader.take()
        return scalar(content, number)
    return plain_block(reader, indent)


def sectioned(text):
    if text[:1] == "\ufeff":
        text = text[1:]
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    chunks = []
    current = []
    offset = 0
    marker = 0
    for index, line in enumerate(lines):
        if START.match(line):
            chunks.append((offset, current + [""], marker))
            current = []
            offset = index + 1
            marker = index + 1
            if line.strip() != "---":
                offset = index
                current = [line]
            continue
        current.append(line)
    chunks.append((offset, current, marker))
    return chunks


def significant(lines):
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return True
    return False


def directives(lines):
    found = False
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not line.startswith("%"):
            return False
        found = True
    return found


def terminated(lines, offset):
    for index, line in enumerate(lines):
        if END.match(line):
            for later, after in enumerate(lines[index + 1:]):
                stripped = after.strip()
                if stripped and not stripped.startswith("#"):
                    raise Unparsable("content after document end", offset + index + later + 2)
            return lines[:index] + [""]
    return lines


def document(lines, offset, marker):
    if lines and START.match(lines[0]):
        raise Unparsable("content after document marker", marker)
    reader = Reader(terminated(lines, offset), offset)
    if not reader.skip():
        return None
    parsed = block(reader, 0)
    if reader.skip():
        raise Unparsable("unexpected indentation", reader.number())
    return parsed


def sections(text):
    found = sectioned(text)
    kept = []
    for index, chunk in enumerate(found):
        offset, lines, marker = chunk
        if not significant(lines) and (index == 0 or index == len(found) - 1):
            continue
        if directives(lines) and index < len(found) - 1:
            continue
        kept.append(chunk)
    return kept


def parsed(text):
    found = sections(text)
    if len(found) > 1:
        return None, "multiple documents at line %d" % found[1][2]
    if not found:
        return None, None
    offset, lines, marker = found[0]
    return document(lines, offset, marker), None


def parse(text):
    try:
        result, reason = parsed(text)
        return None if reason else result
    except Unparsable:
        return None
    except Exception:
        return None


def documents(text):
    try:
        found = sections(text)
    except Exception:
        return []
    results = []
    for offset, lines, marker in found:
        try:
            results.append(document(lines, offset, marker))
        except Unparsable:
            results.append(None)
        except Exception:
            results.append(None)
    return results


def unsupported(text):
    try:
        ignored, reason = parsed(text)
        return reason
    except Unparsable as error:
        return error.reason
    except Exception:
        return "unparsable document"
