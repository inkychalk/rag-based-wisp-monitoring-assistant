#!/usr/bin/env python3
"""wisp_query.py - turn a question into search filters (tower, date, time of day).

Why: the two log days look almost identical, so meaning-based search cannot tell
"14 September" from "15 September". Dates, towers and times must be read
from the question by fixed rules, then used as metadata filters.

    from wisp_query import extract_filters
    filters, notes = extract_filters("What happened to Tower B at 02:10 on 15 September?")
    # filters: {'tower': 'B', 'date': '2026-09-15', 'time_from': '01:55', 'time_to': '02:25'}

Run this file to execute the self-test:  python wisp_query.py
"""
from __future__ import annotations

import re
from datetime import date

MONTHS = {m: i for i, m in enumerate(
    "jan feb mar apr may jun jul aug sep oct nov dec".split(), 1)}
MON = r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?"
ORD = r"(?:st|nd|rd|th)?"
DAY_PARTS = [  # first match wins
    (r"\bovernight\b|\bat night\b|\bnight\b", ("00:00", "06:00")),
    (r"\bmorning\b", ("06:00", "12:00")),
    (r"\bafternoon\b", ("12:00", "18:00")),
    (r"\bevening\b", ("18:00", "23:59")),
]
WINDOW_MIN = 15  # for a single clock time, look this far either side


def _hm(minutes: int) -> str:
    minutes = max(0, min(minutes, 23 * 60 + 59))
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _year_for(month: int, day: int, known: list[date]) -> int:
    same = [d.year for d in known if (d.month, d.day) == (month, day)]
    if same:
        return max(same)
    return max((d.year for d in known), default=date.today().year)


def _find_dates(ql: str, known: list[date]) -> list[date]:
    pairs = set()  # (month, day)
    for y, mo, d in re.findall(r"\b(\d{4})-(\d{2})-(\d{2})\b", ql):
        try:
            pairs.add((int(y), int(mo), int(d)))
        except ValueError:
            pass
    md = set()
    # "14 and 15 September", "14-15 Sep"
    for d1, d2, mon in re.findall(
            rf"\b(\d{{1,2}}){ORD}\s*(?:and|&|,|-|to)\s*(\d{{1,2}}){ORD}\s+(?:of\s+)?{MON}", ql):
        md.update({(MONTHS[mon], int(d1)), (MONTHS[mon], int(d2))})
    # "14 September", "14th of Sep"
    for d, mon in re.findall(rf"\b(\d{{1,2}}){ORD}\s+(?:of\s+)?{MON}", ql):
        md.add((MONTHS[mon], int(d)))
    # "September 14", "Sep 14th"
    for mon, d in re.findall(rf"\b{MON}\s+(\d{{1,2}}){ORD}\b", ql):
        md.add((MONTHS[mon], int(d)))
    out = set()
    for y, mo, d in pairs:
        out.add(date(y, mo, d))
    for mo, d in md:
        try:
            out.add(date(_year_for(mo, d, known), mo, d))
        except ValueError:
            pass
    return sorted(out)


def _find_times(ql: str) -> list[int]:
    """Clock times in the question as minutes since midnight."""
    found = []
    for h, m, ap in re.findall(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", ql):
        h = int(h) % 12 + (12 if ap == "pm" else 0)
        found.append(h * 60 + int(m or 0))
    rest = re.sub(r"\b\d{1,2}(?::\d{2})?\s*(?:am|pm)\b", " ", ql)
    for h, m in re.findall(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", rest):
        found.append(int(h) * 60 + int(m))
    return sorted(set(found))


def extract_filters(question: str, known_dates=()):
    """Return (filters, notes). filters may hold: tower, date or dates,
    time_from, time_to. notes explain anything left out or ambiguous."""
    ql = question.lower()
    known = []
    for d in known_dates:
        try:
            known.append(date.fromisoformat(str(d)))
        except ValueError:
            pass
    filters, notes = {}, []

    towers = {m.upper() for m in re.findall(r"\btower[\s\-_]*([a-z])\b", ql)}
    towers |= {m.upper() for m in re.findall(r"\bt([a-z])-(?:bh|ap\d)\b", ql)}
    towers |= {m.upper() for m in re.findall(r"\bcust-([a-z])\d+\b", ql)}
    if len(towers) == 1:
        filters["tower"] = towers.pop()
    elif len(towers) > 1:
        notes.append(f"several towers mentioned ({', '.join(sorted(towers))}); no tower filter")

    dates = _find_dates(ql, known)
    if len(dates) == 1:
        filters["date"] = dates[0].isoformat()
    elif len(dates) > 1:
        filters["dates"] = [d.isoformat() for d in dates]
        notes.append("several dates mentioned; search each date separately")
    else:
        notes.append("no date in the question")

    times = _find_times(ql)
    if len(times) >= 2:
        filters["time_from"], filters["time_to"] = _hm(times[0]), _hm(times[-1])
    elif len(times) == 1:
        filters["time_from"] = _hm(times[0] - WINDOW_MIN)
        filters["time_to"] = _hm(times[0] + WINDOW_MIN)
    else:
        for pattern, (a, b) in DAY_PARTS:
            if re.search(pattern, ql):
                filters["time_from"], filters["time_to"] = a, b
                break
    return filters, notes


# --------------------------------------------------------------------------
if __name__ == "__main__":
    known = ["2026-09-14", "2026-09-15", "2026-08-19"]
    cases = [
        ("What caused the Tower B outage on 14 September?",
         {"tower": "B", "date": "2026-09-14"}),
        ("What happened to Tower B customers overnight on 14 September?",
         {"tower": "B", "date": "2026-09-14", "time_from": "00:00", "time_to": "06:00"}),
        ("What happened to Tower B at 02:10 on 15 September?",
         {"tower": "B", "date": "2026-09-15", "time_from": "01:55", "time_to": "02:25"}),
        ("How do I respond to SSH brute force on the core router?", {}),
        ("Which IP address attacked the router over SSH on Sep 14th?",
         {"date": "2026-09-14"}),
        ("Tower A drops in the afternoon",
         {"tower": "A", "time_from": "12:00", "time_to": "18:00"}),
        ("what happened between 02:00 and 03:00 on 2026-09-14 on TB-BH",
         {"tower": "B", "date": "2026-09-14", "time_from": "02:00", "time_to": "03:00"}),
        ("Was there an outage at 2:10 AM on 15 September?",
         {"date": "2026-09-15", "time_from": "01:55", "time_to": "02:25"}),
        ("Compare tower A on 14 and 15 September",
         {"tower": "A", "dates": ["2026-09-14", "2026-09-15"]}),
        ("Which tower had the most drops, A or B?", {}),
        ("What caused the Tower C outage?", {"tower": "C"}),
        ("Any problems with cust-B007 in the evening on 19 August?",
         {"tower": "B", "date": "2026-08-19", "time_from": "18:00", "time_to": "23:59"}),
    ]
    bad = 0
    for q, want in cases:
        got, notes = extract_filters(q, known)
        ok = got == want
        bad += not ok
        print(("ok   " if ok else "FAIL ") + q)
        if not ok:
            print("     want", want, "\n     got ", got)
    print(f"\n{len(cases) - bad}/{len(cases)} passed")
    raise SystemExit(1 if bad else 0)