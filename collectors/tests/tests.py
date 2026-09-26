#!/usr/bin/env python3
import json
import re
import xml.etree.ElementTree as ElementTree

from guardrail import Collector

FORMATS = ("junit", "nunit", "trx", "otr", "ctrf")

PASSED = "passed"

FAILED = "failed"

ERRORED = "error"

SKIPPED = "skipped"

FAILING = (FAILED, ERRORED)

MONTH_DAYS = (0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334)

INSTANT = re.compile(r"^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})(?:\.(\d+))?Z?$")

PERIOD = re.compile(r"^P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?)?$", re.IGNORECASE)

TRX_STATUSES = {
    "passed": PASSED,
    "failed": FAILED,
    "error": ERRORED,
    "timeout": ERRORED,
    "aborted": ERRORED,
}

OTR_STATUSES = {
    "SUCCESSFUL": PASSED,
    "FAILED": FAILED,
    "ERRORED": ERRORED,
    "SKIPPED": SKIPPED,
    "ABORTED": SKIPPED,
}

XML_FORMATS = {
    "testsuites": "junit",
    "testsuite": "junit",
    "test-run": "nunit",
    "test-results": "nunit",
    "TestRun": "trx",
    "events": "otr",
    "execution": "otr",
}


def globs(configured):
    return [pattern.strip() for pattern in configured.split(",") if pattern.strip()]


def summarised(case):
    return {
        "name": case.get("name"),
        "classname": case.get("classname"),
        "status": case.get("status"),
        "file": case.get("file"),
    }


def counted(cases, status):
    return len([case for case in cases if case.get("status") == status])


def root_of(text):
    if not isinstance(text, str):
        return None
    try:
        return ElementTree.fromstring(text.lstrip("\ufeff \t\r\n"))
    except Exception:
        return None


def tag(element):
    name = element.tag
    if not isinstance(name, str):
        return ""
    return name.rsplit("}", 1)[1] if "}" in name else name


def children_of(element, name):
    return [child for child in list(element) if tag(child) == name]


def descendants_of(element, name):
    return [found for found in element.iter() if tag(found) == name]


def blank(value):
    return value if value else None


def content(element):
    return (element.text or "").strip()


def whole(value):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def from_seconds(value):
    if value is None or not str(value).strip():
        return None
    try:
        return int(round(float(value) * 1000))
    except (TypeError, ValueError):
        return None


def from_clock(value):
    if not value:
        return None
    parts = str(value).split(":")
    if len(parts) != 3:
        return None
    try:
        return int(round((int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])) * 1000))
    except ValueError:
        return None


def leaps(year):
    return year // 4 - year // 100 + year // 400


def epoch_days(year, month, day):
    days = (year - 1970) * 365 + leaps(year - 1) - leaps(1969)
    days += MONTH_DAYS[month - 1] + day - 1
    if month > 2 and year % 4 == 0 and (year % 100 != 0 or year % 400 == 0):
        days += 1
    return days


def instant(value):
    if not value:
        return None
    found = INSTANT.match(str(value).strip())
    if found is None:
        return None
    year, month, day, hour, minute, second = [int(part) for part in found.group(1, 2, 3, 4, 5, 6)]
    if not 1 <= month <= 12:
        return None
    fraction = (found.group(7) or "")[:3].ljust(3, "0")
    return (epoch_days(year, month, day) * 86400 + hour * 3600 + minute * 60 + second) * 1000 + int(fraction)


def period(value):
    if not value:
        return None
    found = PERIOD.match(str(value).strip())
    if found is None:
        return None
    days, hours, minutes, seconds = found.group(1, 2, 3, 4)
    total = int(days or 0) * 86400 + int(hours or 0) * 3600 + int(minutes or 0) * 60 + float(seconds or 0)
    return int(round(total * 1000))


def normalised(name, classname, status, duration, path):
    return {
        "name": name or "",
        "classname": blank(classname),
        "status": status,
        "durationMs": duration,
        "file": blank(path),
    }


def elapsed(cases):
    stated = [case["durationMs"] for case in cases if case["durationMs"] is not None]
    return sum(stated) if stated else None


def suite_of(cases, duration):
    return {
        "tests": len(cases),
        "failures": len([case for case in cases if case["status"] == FAILED]),
        "errors": len([case for case in cases if case["status"] == ERRORED]),
        "skipped": len([case for case in cases if case["status"] == SKIPPED]),
        "durationMs": duration,
        "cases": cases,
    }


def junit(text):
    try:
        root = root_of(text)
        if root is None or tag(root) not in ("testsuites", "testsuite"):
            return None
        cases = [junit_case(case) for case in descendants_of(root, "testcase")]
        return suite_of(cases, junit_elapsed(root, cases))
    except Exception:
        return None


def junit_case(case):
    if children_of(case, "failure"):
        status = FAILED
    elif children_of(case, "error"):
        status = ERRORED
    elif children_of(case, "skipped"):
        status = SKIPPED
    else:
        status = PASSED

    return normalised(
        case.get("name"),
        case.get("classname"),
        status,
        from_seconds(case.get("time")),
        case.get("file"),
    )


def junit_elapsed(root, cases):
    stated = from_seconds(root.get("time"))
    if stated is not None:
        return stated

    suites = children_of(root, "testsuite") if tag(root) == "testsuites" else [root]
    times = [from_seconds(suite.get("time")) for suite in suites]
    declared = [time for time in times if time is not None]

    return sum(declared) if declared else elapsed(cases)


def nunit(text):
    try:
        root = root_of(text)
        if root is None:
            return None
        if tag(root) == "test-run":
            cases = [nunit3_case(case) for case in descendants_of(root, "test-case")]
            stated = from_seconds(root.get("duration"))
            if stated is None:
                stated = from_seconds(root.get("time"))
            return suite_of(cases, stated if stated is not None else elapsed(cases))
        if tag(root) == "test-results":
            cases = [nunit2_case(case) for case in descendants_of(root, "test-case")]
            return suite_of(cases, elapsed(cases))
        return None
    except Exception:
        return None


def nunit3_case(case):
    result = (case.get("result") or "").lower()

    if result == "failed":
        status = FAILED
    elif result == "passed":
        status = PASSED
    else:
        status = SKIPPED

    duration = from_seconds(case.get("duration"))
    if duration is None:
        duration = from_seconds(case.get("time"))

    return normalised(case.get("name"), case.get("classname"), status, duration, None)


def nunit2_case(case):
    result = (case.get("result") or "").lower()
    success = (case.get("success") or "").lower()

    if result == "failure" or success == "false":
        status = FAILED
    elif result == "success" or success == "true":
        status = PASSED
    else:
        status = SKIPPED

    name, classname = nunit2_names(case.get("name") or "")

    return normalised(name, classname, status, from_seconds(case.get("time")), None)


def nunit2_names(full):
    depth = 0
    separator = -1
    for index in range(len(full) - 1, -1, -1):
        character = full[index]
        if character == ")":
            depth += 1
        elif character == "(":
            depth -= 1
        elif character == "." and depth == 0:
            separator = index
            break

    if separator <= 0:
        return full, None

    return full[separator + 1:], full[:separator]


def trx(text):
    try:
        root = root_of(text)
        if root is None or tag(root) != "TestRun":
            return None

        definitions = {}
        for unit in descendants_of(root, "UnitTest"):
            methods = descendants_of(unit, "TestMethod")
            classname = methods[0].get("className") if methods else None
            definitions[unit.get("id")] = (unit.get("name"), classname)

        cases = []
        for result in descendants_of(root, "UnitTestResult"):
            name, classname = definitions.get(result.get("testId"), (None, None))
            cases.append(
                normalised(
                    name or result.get("testName"),
                    classname,
                    TRX_STATUSES.get((result.get("outcome") or "").lower(), SKIPPED),
                    from_clock(result.get("duration")),
                    None,
                )
            )

        return suite_of(cases, elapsed(cases))
    except Exception:
        return None


def ctrf(text):
    try:
        if not isinstance(text, str):
            return None
        document = json.loads(text)
        if not isinstance(document, dict):
            return None
        results = document.get("results")
        if not isinstance(results, dict):
            return None
        entries = results.get("tests")
        if not isinstance(entries, list):
            return None

        cases = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            status = (entry.get("status") or "").lower()
            cases.append(
                normalised(
                    entry.get("name"),
                    entry.get("suite"),
                    PASSED if status == "passed" else FAILED if status == "failed" else SKIPPED,
                    whole(entry.get("duration")),
                    entry.get("filePath"),
                )
            )

        return suite_of(cases, elapsed(cases))
    except Exception:
        return None


def otr(text):
    try:
        root = root_of(text)
        if root is None:
            return None
        if tag(root) == "events":
            return otr_events(root)
        if tag(root) == "execution":
            return otr_hierarchy(root)
        return None
    except Exception:
        return None


def otr_info(element):
    info = {"type": None, "className": None, "status": None}

    for child in list(element):
        kind = tag(child)
        if kind == "metadata":
            for item in list(child):
                if tag(item) == "type" and content(item):
                    info["type"] = content(item)
        elif kind == "sources":
            for item in list(child):
                if tag(item) in ("methodSource", "classSource") and item.get("className"):
                    info["className"] = item.get("className")
        elif kind == "result":
            info["status"] = blank(child.get("status"))

    return info


def otr_merge(info, other):
    return dict((key, other[key] or info[key]) for key in info)


def otr_status(status):
    return OTR_STATUSES.get(status, SKIPPED)


def otr_is_case(kind, nested):
    if kind == "TEST":
        return True
    if kind == "CONTAINER":
        return False
    return not nested


def otr_events(root):
    entries = {}
    order = []

    for event in list(root):
        kind = tag(event)
        identifier = event.get("id")
        if kind not in ("started", "reported", "finished") or not identifier:
            continue

        if kind == "started":
            if identifier not in entries:
                order.append(identifier)
            entries[identifier] = {
                "name": event.get("name") or "",
                "parent": blank(event.get("parentId")),
                "start": instant(event.get("time")),
                "finish": None,
                "info": otr_info(event),
            }
            continue

        entry = entries.get(identifier)
        if entry is None:
            continue
        if kind == "finished":
            entry["finish"] = instant(event.get("time"))
        entry["info"] = otr_merge(entry["info"], otr_info(event))

    parents = set(entry["parent"] for entry in entries.values())
    cases = []
    for identifier in order:
        entry = entries[identifier]
        if not otr_is_case(entry["info"]["type"], identifier in parents):
            continue
        duration = None
        if entry["start"] is not None and entry["finish"] is not None:
            duration = entry["finish"] - entry["start"]
        cases.append(
            normalised(
                entry["name"],
                otr_class(entries, identifier),
                otr_status(entry["info"]["status"]),
                duration,
                None,
            )
        )

    return suite_of(cases, elapsed(cases))


def otr_class(entries, identifier):
    walked = set()
    while identifier and identifier in entries and identifier not in walked:
        walked.add(identifier)
        classname = entries[identifier]["info"]["className"]
        if classname:
            return classname
        identifier = entries[identifier]["parent"]

    return None


def otr_hierarchy(root):
    cases = []
    roots = children_of(root, "root")
    for element in roots:
        otr_visit(element, None, cases)

    durations = [period(element.get("duration")) for element in roots]
    stated = [duration for duration in durations if duration is not None]

    return suite_of(cases, sum(stated) if stated else elapsed(cases))


def otr_visit(element, inherited, cases):
    info = otr_info(element)
    classname = info["className"] or inherited
    nested = children_of(element, "child")

    if otr_is_case(info["type"], nested):
        cases.append(
            normalised(
                element.get("name"),
                classname,
                otr_status(info["status"]),
                period(element.get("duration")),
                None,
            )
        )
        return

    for child in nested:
        otr_visit(child, classname, cases)


def tests(text):
    for parser in (junit, nunit, trx, otr, ctrf):
        parsed = parser(text)
        if parsed is not None:
            return parsed

    return None


def detect(text):
    try:
        root = root_of(text)
        if root is not None:
            return XML_FORMATS.get(tag(root))
        if ctrf(text) is not None:
            return "ctrf"
        return None
    except Exception:
        return None


with Collector() as collector:
    patterns = globs(collector.input("reports", "TEST-*.xml,*-test-report.xml,junit*.xml,test-results*.xml,*.trx,*-ctrf.json,open-test-report.xml"))
    limit = int(collector.input("maxFailures", "50") or "50")

    read = []
    cases = []
    durations = []

    for path, modified, text in collector.reports(*patterns):
        format = detect(text)

        if format not in FORMATS:
            continue

        parsed = tests(text)

        if parsed is None:
            collector.log("%s looked like %s and could not be read" % (path, format))
            continue

        read.append({"path": collector.path(path), "modified": modified, "format": format})
        cases += parsed["cases"]
        durations.append(parsed["durationMs"])

    if not read:
        collector.empty("no test report matched %s" % ", ".join(patterns))

    stated = [duration for duration in durations if duration is not None]
    failed = [case for case in cases if case.get("status") in FAILING]
    skipped = [case for case in cases if case.get("status") == SKIPPED]

    collector.sourced("report", read)
    collector.facts["totals"] = {
        "tests": len(cases),
        "passed": counted(cases, PASSED),
        "failed": counted(cases, FAILED),
        "errors": counted(cases, ERRORED),
        "skipped": len(skipped),
        "durationMs": sum(stated) if stated else None,
    }
    collector.facts["suites"] = len(read)
    collector.facts["failures"] = [summarised(case) for case in failed[:limit]]
    collector.facts["skipped"] = [summarised(case) for case in skipped[:limit]]
    collector.facts["dropped"] = max(0, len(failed) - limit) + max(0, len(skipped) - limit)
