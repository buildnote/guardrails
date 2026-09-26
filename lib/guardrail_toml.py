#!/usr/bin/env python3
import re

BARE = re.compile(r"[A-Za-z0-9_-]+")
INTEGER = re.compile(r"^[-+]?(?:0|[1-9](?:_?[0-9])*)$")
FLOAT = re.compile(r"^[-+]?(?:0|[1-9](?:_?[0-9])*)(?:\.[0-9](?:_?[0-9])*)?(?:[eE][-+]?[0-9]+)?$")
DATE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}([Tt ].*)?$")
TIME = re.compile(r"^[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+)?$")
ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f", "\"": "\"", "\\": "\\"}


class Unparsable(Exception):
    def __init__(self, construct, line):
        Exception.__init__(self, "%s at line %d" % (construct, line))
        self.reason = "%s at line %d" % (construct, line)


class Reader(object):
    def __init__(self, text):
        self.text = text
        self.at = 0
        self.line = 1

    def done(self):
        return self.at >= len(self.text)

    def peek(self):
        return "" if self.done() else self.text[self.at]

    def take(self, count=1):
        taken = self.text[self.at:self.at + count]
        self.at += len(taken)
        self.line += taken.count("\n")

        return taken

    def looking_at(self, text):
        return self.text.startswith(text, self.at)

    def reject(self, construct):
        raise Unparsable(construct, self.line)

    def spaces(self):
        while not self.done() and self.peek() in " \t":
            self.take()

    def comment(self):
        if self.peek() != "#":
            return
        while not self.done() and self.peek() != "\n":
            self.take()

    def blanks(self):
        while not self.done():
            self.spaces()
            self.comment()
            if self.peek() == "\n":
                self.take()
                continue
            if self.peek() == "\r" and self.text.startswith("\r\n", self.at):
                self.take(2)
                continue
            return

    def endline(self):
        self.spaces()
        self.comment()
        if self.done():
            return
        if self.peek() == "\n":
            self.take()
        elif self.text.startswith("\r\n", self.at):
            self.take(2)
        else:
            self.reject("unexpected content")


def basic_string(reader):
    reader.take()
    built = []

    while True:
        if reader.done() or reader.peek() == "\n":
            reader.reject("unterminated string")
        character = reader.take()
        if character == "\"":
            return "".join(built)
        if character != "\\":
            built.append(character)
            continue
        escape = reader.take()
        if escape in ESCAPES:
            built.append(ESCAPES[escape])
        elif escape in ("u", "U"):
            digits = reader.take(4 if escape == "u" else 8)
            try:
                built.append(chr(int(digits, 16)))
            except ValueError:
                reader.reject("bad escape")
        else:
            reader.reject("bad escape")


def multiline_string(reader, quote):
    reader.take(3)
    if reader.peek() == "\n":
        reader.take()
    built = []

    while True:
        if reader.done():
            reader.reject("unterminated string")
        if reader.looking_at(quote * 3):
            reader.take(3)
            return "".join(built)
        character = reader.take()
        if quote == "'" or character != "\\":
            built.append(character)
            continue
        if reader.peek() == "\n":
            reader.take()
            while not reader.done() and reader.peek() in " \t\n":
                reader.take()
            continue
        escape = reader.take()
        if escape in ESCAPES:
            built.append(ESCAPES[escape])
        elif escape in ("u", "U"):
            digits = reader.take(4 if escape == "u" else 8)
            try:
                built.append(chr(int(digits, 16)))
            except ValueError:
                reader.reject("bad escape")
        else:
            reader.reject("bad escape")


def literal_string(reader):
    reader.take()
    built = []

    while True:
        if reader.done() or reader.peek() == "\n":
            reader.reject("unterminated string")
        character = reader.take()
        if character == "'":
            return "".join(built)
        built.append(character)


def string(reader):
    if reader.looking_at("\"\"\""):
        return multiline_string(reader, "\"")
    if reader.looking_at("'''"):
        return multiline_string(reader, "'")
    if reader.peek() == "\"":
        return basic_string(reader)

    return literal_string(reader)


def bare(reader):
    found = BARE.match(reader.text, reader.at)
    if not found:
        reader.reject("expected a key")
    reader.take(found.end() - found.start())

    return found.group(0)


def key(reader):
    parts = []

    while True:
        reader.spaces()
        parts.append(string(reader) if reader.peek() in "\"'" else bare(reader))
        reader.spaces()
        if reader.peek() != ".":
            return parts
        reader.take()


def scalar(reader):
    started = reader.at
    depth = 0

    while not reader.done():
        character = reader.peek()
        if character in "[{":
            depth += 1
        elif character in "]}":
            if depth == 0:
                break
            depth -= 1
        elif depth == 0 and (character in "\n,#" or (character == "\r" and reader.looking_at("\r\n"))):
            break
        reader.take()

    text = reader.text[started:reader.at].strip()
    if not text:
        reader.reject("expected a value")

    return typed(text, reader)


def typed(text, reader):
    if text in ("true", "false"):
        return text == "true"
    if INTEGER.match(text):
        return int(text.replace("_", ""))
    if FLOAT.match(text):
        return float(text.replace("_", ""))
    if text in ("inf", "+inf", "-inf", "nan", "+nan", "-nan"):
        return text
    if DATE.match(text) or TIME.match(text):
        return text

    return reader.reject("unknown value")


def array(reader):
    reader.take()
    found = []

    while True:
        reader.blanks()
        if reader.done():
            reader.reject("unterminated array")
        if reader.peek() == "]":
            reader.take()
            return found
        found.append(value(reader))
        reader.blanks()
        if reader.done():
            reader.reject("unterminated array")
        if reader.peek() == ",":
            reader.take()
        elif reader.peek() != "]":
            reader.reject("expected a comma")


def inline_table(reader):
    reader.take()
    found = {}

    while True:
        reader.spaces()
        if reader.done():
            reader.reject("unterminated table")
        if reader.peek() == "}":
            reader.take()
            return found
        parts = key(reader)
        if reader.peek() != "=":
            reader.reject("expected an equals")
        reader.take()
        reader.spaces()
        place(found, parts, value(reader), reader)
        reader.spaces()
        if reader.done():
            reader.reject("unterminated table")
        if reader.peek() == ",":
            reader.take()
        elif reader.peek() != "}":
            reader.reject("expected a comma")


def value(reader):
    reader.spaces()
    character = reader.peek()

    if character in "\"'":
        return string(reader)
    if character == "[":
        return array(reader)
    if character == "{":
        return inline_table(reader)

    return scalar(reader)


def place(document, parts, given, reader):
    holder = document
    for part in parts[:-1]:
        holder = holder.setdefault(part, {})
        if not isinstance(holder, dict):
            reader.reject("redefined key")
    if parts[-1] in holder:
        reader.reject("redefined key")
    holder[parts[-1]] = given


def table(document, parts, reader):
    holder = document
    for part in parts:
        nested = holder.setdefault(part, {})
        if isinstance(nested, list):
            nested = nested[-1]
        if not isinstance(nested, dict):
            reader.reject("redefined key")
        holder = nested

    return holder


def table_array(document, parts, reader):
    holder = document
    for part in parts[:-1]:
        nested = holder.setdefault(part, {})
        if isinstance(nested, list):
            nested = nested[-1]
        if not isinstance(nested, dict):
            reader.reject("redefined key")
        holder = nested

    entries = holder.setdefault(parts[-1], [])
    if not isinstance(entries, list):
        reader.reject("redefined key")
    entries.append({})

    return entries[-1]


def document_of(text):
    reader = Reader(text.replace("\r\n", "\n"))
    document = {}
    current = document

    while True:
        reader.blanks()
        if reader.done():
            return document

        if reader.looking_at("[["):
            reader.take(2)
            parts = key(reader)
            if not reader.looking_at("]]"):
                reader.reject("unterminated header")
            reader.take(2)
            current = table_array(document, parts, reader)
            reader.endline()
            continue

        if reader.peek() == "[":
            reader.take()
            parts = key(reader)
            if reader.peek() != "]":
                reader.reject("unterminated header")
            reader.take()
            current = table(document, parts, reader)
            reader.endline()
            continue

        parts = key(reader)
        if reader.peek() != "=":
            reader.reject("expected an equals")
        reader.take()
        place(current, parts, value(reader), reader)
        reader.endline()


def parse(text):
    try:
        return document_of(text)
    except Exception:
        return None


def unsupported(text):
    try:
        document_of(text)
        return None
    except Unparsable as rejected:
        return rejected.reason
    except Exception:
        return "unreadable"
