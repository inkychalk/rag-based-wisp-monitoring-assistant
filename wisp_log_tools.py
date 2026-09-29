#!/usr/bin/env python3
"""wisp_log_tools.py - parse, validate and chunk synthetic MikroTik syslog.

Step 1 (data):  validate a generated log (and its answer key) before you trust it.
Step 2 (chunk): turn the log into chunks with metadata, ready for embedding.

Usage:
  python wisp_log_tools.py validate day1.log --key day1_key.json --date 2026-09-14
  python wisp_log_tools.py chunks   day1.log --date 2026-09-14 --out chunks.jsonl

Expected line format (matches the prompt's fallback format):
  Sep 14 02:10:05 CORE-RTR pppoe,ppp,info <pppoe-cust-B007>: disconnected
  "Mon DD HH:MM:SS", hostname, topics, message. There is no year in the log,
  so pass --date (or the current year is used).

If your real RouterOS lines look different, change LINE_RE and classify().
Standard library only. Python 3.8+.
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import Path

LINE_RE = re.compile(
    r"^(?P<mon>[A-Z][a-z]{2})\s+(?P<day>\d{1,2})\s+(?P<time>\d{2}:\d{2}:\d{2})\s+"
    r"(?P<host>\S+)\s+(?P<topics>[\w,\-]+)\s+(?P<msg>.*\S)\s*$"
)
PPPOE_IF_RE = re.compile(r"<pppoe-([^>]+)>")
MAC_RE = re.compile(r"\b([0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5})\b")
IP_RE = re.compile(r"\b(\d{1,3}(?:\.\d{1,3}){3})\b")
HMS_RE = re.compile(r"\b(\d{2}):(\d{2}):(\d{2})\b")
UNANSWERABLE_RE = re.compile(
    r"not in (the )?logs?|cannot be answered|not found in|not available in"
)
DOC_NETS = [
    ipaddress.ip_network(n)
    for n in ("192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24")
]
SYNTH_MAC_PREFIX = "02:00:0A:"
EPOCH = datetime(1970, 1, 1)


# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------
@dataclass
class Event:
    line_no: int
    raw: str
    ts: datetime
    host: str
    topics: str
    msg: str
    etype: str = "other"
    customer: str | None = None
    tower: str | None = None
    iface: str | None = None
    mac: str | None = None
    signal: int | None = None
    ip: str | None = None
    user: str | None = None


def classify(topics: str, msg: str) -> dict:
    """Turn topics + message into an event type and extracted fields."""
    tset = set(topics.lower().split(","))
    m = msg.lower()
    out = {"etype": "other", "customer": None, "iface": None,
           "mac": None, "signal": None, "ip": None, "user": None}
    mac = MAC_RE.search(msg)
    if mac:
        out["mac"] = mac.group(1).upper()
    sig = re.search(r"signal strength\s+(-?\d+)", m)
    if sig:
        out["signal"] = int(sig.group(1))

    if "pppoe" in tset:
        cust = PPPOE_IF_RE.search(msg)
        if cust:
            out["customer"] = cust.group(1)
        if "authentication failed" in m:
            out["etype"] = "pppoe_auth_failed"
        elif "disconnected" in m:
            out["etype"] = "pppoe_disconnected"
        elif "terminating" in m:
            out["etype"] = "pppoe_terminating"
        elif "connected" in m:
            out["etype"] = "pppoe_connected"
        elif "authenticated" in m:
            out["etype"] = "pppoe_authenticated"
        else:
            out["etype"] = "pppoe_other"
    elif "wireless" in tset:
        sig = re.search(r"signal strength\s+(-?\d+)", m)
        if sig:
            out["signal"] = int(sig.group(1))
        if "disconnected" in m:
            out["etype"] = "wireless_disconnected"
        elif "connected" in m:
            out["etype"] = "wireless_connected"
        else:
            out["etype"] = "wireless_other"
    elif "interface" in tset:
        link = re.match(r"(\S+)\s+link\s+(down|up)\b", msg, re.I)
        if link:
            out["iface"] = link.group(1)
            out["etype"] = "link_" + link.group(2).lower()
        else:
            out["etype"] = "interface_other"
    elif "rebooted without proper shutdown" in m:
        out["etype"] = "reboot"
    elif "login failure" in m:
        out["etype"] = "login_failure"
        ip = re.search(r"from\s+(\d{1,3}(?:\.\d{1,3}){3})", m)
        out["ip"] = ip.group(1) if ip else None
        um = re.search(r"login failure for user (\S+)", msg)
        out["user"] = um.group(1) if um else None
    elif "logged in" in m:
        out["etype"] = "login"
    elif "firewall" in tset:
        out["etype"] = "firewall"
        src = re.search(r"(\d{1,3}(?:\.\d{1,3}){3}):\d+->", m)
        out["ip"] = src.group(1) if src else None
    elif "dhcp" in tset:
        out["etype"] = "dhcp"
    elif "script" in tset and "signal strength" in m:
        out["etype"] = "signal_warning"
    elif "script" in tset and "cpu" in m:
        out["etype"] = "high_cpu"
    return out


def tower_of(host: str, customer: str | None) -> str | None:
    """Tower letter from a customer id (cust-B007) or a device name (TB-AP1)."""
    if customer:
        m = re.match(r"cust-([A-Za-z])\d+", customer)
        if m:
            return m.group(1).upper()
    m = re.match(r"T([A-Za-z])-", host)
    return m.group(1).upper() if m else None


def parse_log(lines: list[str], year: int, iface_map: dict | None = None):
    """iface_map maps a core-router interface to a tower, e.g. {"ether2": "B"}."""
    events: list[Event] = []
    bad: list[tuple[int, str]] = []
    for i, raw in enumerate(lines, 1):
        raw = raw.rstrip("\r\n")
        if not raw.strip():
            continue
        m = LINE_RE.match(raw)
        if not m:
            bad.append((i, raw))
            continue
        try:
            ts = datetime.strptime(
                f"{year} {m['mon']} {m['day']} {m['time']}", "%Y %b %d %H:%M:%S"
            )
        except ValueError:
            bad.append((i, raw))
            continue
        info = classify(m["topics"], m["msg"])
        tower = tower_of(m["host"], info["customer"])
        if tower is None and info["iface"] and iface_map:
            tower = iface_map.get(info["iface"])
        events.append(Event(
            line_no=i, raw=raw, ts=ts, host=m["host"], topics=m["topics"],
            msg=m["msg"], tower=tower, **info,
        ))
    return events, bad


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------
@dataclass
class Issue:
    level: str  # ERROR, WARNING or INFO
    line_no: int | None
    text: str

    def __str__(self) -> str:
        where = f"line {self.line_no}: " if self.line_no else ""
        return f"[{self.level}] {where}{self.text}"


def _to_dt(value, base: date) -> datetime | None:
    m = HMS_RE.search(str(value)) if value is not None else None
    if not m:
        return None
    return datetime.combine(base, time(int(m[1]), int(m[2]), int(m[3])))


def _tower_letter(value) -> str | None:
    m = re.search(r"([A-Za-z])\s*$", str(value or ""))
    return m.group(1).upper() if m else None


def validate(events, bad, raw_lines, key=None, expected_date=None):
    issues: list[Issue] = []

    def add(level, line_no, text):
        issues.append(Issue(level, line_no, text))

    for line_no, raw in bad[:10]:
        add("ERROR", line_no, f"line does not match the expected format: {raw[:70]!r}")
    if len(bad) > 10:
        add("ERROR", None, f"... and {len(bad) - 10} more unparsable lines")
    if not events:
        add("ERROR", None, "no valid log lines found")
        return issues, {}

    base = events[0].ts.date()

    # 1. Time order and single day
    for prev, cur in zip(events, events[1:]):
        if cur.ts < prev.ts:
            add("ERROR", cur.line_no,
                f"timestamp goes backwards ({prev.ts:%H:%M:%S} then {cur.ts:%H:%M:%S})")
    if len({e.ts.date() for e in events}) > 1:
        add("ERROR", None, "log spans more than one day")
    if expected_date and base != expected_date:
        add("ERROR", None, f"log date is {base}, expected {expected_date}")

    # 2. PPPoE session state
    state, last_down, delays, first_disc = {}, {}, [], set()
    for e in events:
        if not e.customer:
            continue
        if e.etype == "pppoe_connected":
            if state.get(e.customer) == "up":
                add("ERROR", e.line_no,
                    f"{e.customer} connected while already connected")
            if e.customer in last_down:
                delays.append((e.ts - last_down.pop(e.customer)).total_seconds())
            state[e.customer] = "up"
        elif e.etype == "pppoe_disconnected":
            prev = state.get(e.customer)
            if prev == "down":
                add("ERROR", e.line_no,
                    f"{e.customer} disconnected while already disconnected")
            elif prev is None:
                first_disc.add(e.customer)
            state[e.customer] = "down"
            last_down[e.customer] = e.ts
    if first_disc:
        add("INFO", None, f"{len(first_disc)} customers first appear as disconnected "
                          "(assumed connected at start of day)")

    # 3. Link state per device and interface
    links = {}
    for e in events:
        if e.etype in ("link_up", "link_down"):
            k, new = (e.host, e.iface), e.etype[5:]
            if links.get(k) == new:
                add("ERROR", e.line_no, f"{e.iface} on {e.host} reported {new} twice in a row")
            links[k] = new

    # 4. One access point per customer radio (MAC)
    mac_hosts = defaultdict(set)
    for e in events:
        if e.etype.startswith("wireless") and e.mac:
            mac_hosts[e.mac].add(e.host)
    for mac, hosts in mac_hosts.items():
        if len(hosts) > 1:
            add("WARNING", None, f"{mac} seen on several APs: {', '.join(sorted(hosts))}")

    # 5. Privacy: no public IPs, no real-looking MACs
    real_macs = set()
    for i, raw in enumerate(raw_lines, 1):
        for ipm in IP_RE.finditer(raw):
            try:
                ip = ipaddress.ip_address(ipm.group(1))
            except ValueError:
                continue
            ok = ip.is_private or ip.is_loopback or any(ip in n for n in DOC_NETS)
            if not ok:
                add("ERROR", i, f"public IP {ip} is not in a documentation range")
        for mm in MAC_RE.finditer(raw):
            mac = mm.group(1).upper()
            if not mac.startswith(SYNTH_MAC_PREFIX):
                real_macs.add(mac)
    if real_macs:
        add("WARNING", None, f"{len(real_macs)} MACs do not start with {SYNTH_MAC_PREFIX} "
                             f"(could be real): {', '.join(sorted(real_macs)[:5])}")

    disc_by_tower = Counter(
        e.tower for e in events if e.etype == "pppoe_disconnected" and e.tower
    )

    # 6. Answer key checks
    if key is not None:
        log_times = {e.ts for e in events}
        for inc in key.get("incidents", []):
            iid = inc.get("id", "?")
            letter = _tower_letter(inc.get("tower"))
            typ = str(inc.get("type", "")).lower()
            start, end = _to_dt(inc.get("start"), base), _to_dt(inc.get("end"), base)
            fe = _to_dt(inc.get("first_evidence_timestamp"), base)
            le = _to_dt(inc.get("last_evidence_timestamp"), base)
            for label, t in (("first_evidence_timestamp", fe), ("last_evidence_timestamp", le)):
                if t is None:
                    add("WARNING", None, f"incident {iid}: {label} missing or unreadable")
                elif t not in log_times:
                    add("ERROR", None, f"incident {iid}: no log line at {label} {t:%H:%M:%S}")
            aff = inc.get("affected_customers")
            if fe and le:
                disc = {e.customer for e in events
                        if e.etype == "pppoe_disconnected" and e.customer and fe <= e.ts <= le}
                if isinstance(aff, list):
                    missing = [c for c in aff if c not in disc]
                    if missing:
                        add("ERROR", None, f"incident {iid}: listed as affected but no "
                                           f"disconnect in evidence window: {', '.join(missing[:8])}")
                elif isinstance(aff, int) and letter:
                    n = len({c for c in disc if tower_of("", c) == letter})
                    if n != aff:
                        add("WARNING", None, f"incident {iid}: key says {aff} affected, "
                                             f"log shows {n} disconnected in window")
            if letter and start and end and ("backhaul" in typ or "power" in typ):
                prefix = f"T{letter}-"
                noisy = [e for e in events if e.host.startswith(prefix)
                         and start < e.ts < end and e.etype != "reboot"]
                if noisy:
                    add("WARNING", noisy[0].line_no,
                        f"incident {iid}: {noisy[0].host} logs during the outage "
                        f"({len(noisy)} lines), check the timing by hand")

        rc = key.get("routine_counts")
        if rc:
            for k, v in rc.items():
                letter = _tower_letter(k)
                try:
                    expected = int(v)
                except (TypeError, ValueError):
                    add("WARNING", None, f"routine_counts[{k}] is not a number: {v!r}")
                    continue
                actual = disc_by_tower.get(letter, 0)
                if actual != expected:
                    add("ERROR", None, f"routine_counts tower {letter}: key says {expected}, "
                                       f"log has {actual} PPPoE 'disconnected' lines")
        else:
            add("WARNING", None, "answer key has no routine_counts")

        qs = key.get("test_questions", [])
        if len(qs) != 8:
            add("WARNING", None, f"answer key has {len(qs)} test questions, expected 8")
        unans = [q for q in qs if UNANSWERABLE_RE.search(str(q.get("answer", "")).lower())]
        if len(unans) != 2:
            add("WARNING", None, f"{len(unans)} questions look unanswerable, expected 2")
        hms_in_log = {e.ts.strftime("%H:%M:%S") for e in events}
        for n, q in enumerate(qs, 1):
            if q in unans:
                continue
            for t in HMS_RE.finditer(str(q.get("answer", ""))):
                if t.group(0) not in hms_in_log:
                    add("WARNING", None, f"question {n}: answer cites {t.group(0)}, "
                                         "no log line at that time")

    stats = {
        "lines": len(raw_lines), "events": len(events),
        "hosts": sorted({e.host for e in events}),
        "customers": len({e.customer for e in events if e.customer}),
        "event_types": Counter(e.etype for e in events),
        "disconnects_by_tower": dict(sorted(disc_by_tower.items())),
        "reconnect_seconds": (
            (min(delays), statistics.median(delays), max(delays)) if delays else None
        ),
    }
    return issues, stats


def print_report(issues, stats) -> int:
    if stats:
        print(f"Parsed {stats['events']} events from {stats['lines']} lines; "
              f"{len(stats['hosts'])} hosts, {stats['customers']} customers")
        print("Event types:", ", ".join(f"{k}={v}" for k, v in sorted(stats["event_types"].items())))
        print("PPPoE disconnects by tower:", stats["disconnects_by_tower"])
        if stats["reconnect_seconds"]:
            lo, med, hi = stats["reconnect_seconds"]
            print(f"Reconnect delay (s): min {lo:.0f}, median {med:.0f}, max {hi:.0f}")
    print()
    order = {"ERROR": 0, "WARNING": 1, "INFO": 2}
    for issue in sorted(issues, key=lambda i: (order[i.level], i.line_no or 0)):
        print(issue)
    errors = sum(i.level == "ERROR" for i in issues)
    warnings = sum(i.level == "WARNING" for i in issues)
    print(f"\n{errors} errors, {warnings} warnings")
    return 1 if errors else 0


# --------------------------------------------------------------------------
# Chunking (step 2)
# --------------------------------------------------------------------------
PHRASES = {
    "pppoe_disconnected": "PPPoE disconnects", "pppoe_connected": "PPPoE reconnects",
    "pppoe_auth_failed": "PPPoE authentication failures",
    "wireless_disconnected": "wireless disconnects", "wireless_connected": "wireless reconnects",
    "signal_warning": "signal warnings", "link_down": "link down events",
    "link_up": "link up events", "reboot": "reboots", "login_failure": "login failures",
    "login": "admin logins", "firewall": "firewall hits", "high_cpu": "high CPU warnings",
    "dhcp": "DHCP assignments",
}


def _summary(piece):
    """One readable line built only from counts in the chunk. No interpretation."""
    counts = Counter(x.etype for x in piece)
    parts = []
    bits = [f"{counts[k]} {v}" for k, v in PHRASES.items() if counts.get(k)]
    if bits:
        parts.append(", ".join(bits))
    sigs = [x.signal for x in piece if x.signal is not None]
    if sigs:
        parts.append(f"weakest signal {min(sigs)} dBm")
    disc = [x for x in piece if x.etype == "pppoe_disconnected" and x.customer]
    custs = sorted({x.customer for x in disc})
    if len(custs) >= 5:
        span = int((disc[-1].ts - disc[0].ts).total_seconds())
        parts.append(f"mass disconnect: {len(custs)} customers dropped within {span} seconds "
                     "(possible tower or backhaul outage)")
    fails = Counter((x.ip, (re.search(r"via (\w+)", x.msg) or [None, "?"])[1])
                    for x in piece if x.etype == "login_failure" and x.ip)
    for (ip, svc), n in fails.items():
        if n >= 5:
            parts.append(f"repeated login failures from {ip} via {svc}: {n} attempts "
                         "(possible brute force)")
    ports = defaultdict(set)
    for x in piece:
        if x.etype == "firewall" and x.ip:
            pm = re.search(r"->[\d.]+:(\d+)", x.msg)
            if pm:
                ports[x.ip].add(pm.group(1))
    for ip, pset in ports.items():
        if len(pset) >= 3:
            parts.append(f"{ip} probed {len(pset)} different ports (possible port scan)")
    drops = Counter(x.host for x in piece if x.etype == "wireless_disconnected")
    for host, n in drops.items():
        if n >= 4:
            parts.append(f"repeated wireless drops on {host}: {n} "
                         "(possible interference or weak signal)")
    if custs:
        more = f" and {len(custs) - 20} more" if len(custs) > 20 else ""
        parts.append("customers disconnected: " + ", ".join(custs[:20]) + more)
    return ("Summary: " + "; ".join(parts) + "\n") if parts else ""


def chunk_events(events, source, window=15, max_lines=40):
    """Group events by tower and time window. Returns id/text/metadata dicts.

    Metadata values are plain strings and numbers so they can go straight
    into a vector store such as Chroma. Times are stored as epoch seconds
    (naive time treated as UTC) so you can filter with $gte and $lte.
    """
    groups = defaultdict(list)
    for e in events:
        bucket = (e.ts.hour * 60 + e.ts.minute) // window
        groups[(e.tower or "CORE", bucket)].append(e)

    chunks = []
    for (tower, bucket), evs in sorted(groups.items(), key=lambda kv: (kv[1][0].ts, kv[0][0])):
        for part, i in enumerate(range(0, len(evs), max_lines)):
            piece = evs[i:i + max_lines]
            first, last = piece[0], piece[-1]
            header = (f"Source: {source} | Tower: {tower} | "
                      f"{first.ts:%Y-%m-%d %H:%M:%S} to {last.ts:%H:%M:%S}")
            counts = Counter(x.etype for x in piece)
            customers = sorted({x.customer for x in piece if x.customer})
            chunks.append({
                "id": f"{source}:{tower}:{first.ts:%Y%m%d}:{bucket:03d}:{part}",
                "text": header + "\n" + _summary(piece) + "\n".join(x.raw for x in piece),
                "metadata": {
                    "source": source,
                    "type": "log",
                    "date": f"{first.ts:%Y-%m-%d}",
                    "tower": tower,
                    "hosts": ",".join(sorted({x.host for x in piece})),
                    "start_ts": int((first.ts - EPOCH).total_seconds()),
                    "end_ts": int((last.ts - EPOCH).total_seconds()),
                    "n_lines": len(piece),
                    "n_disconnects": counts.get("pppoe_disconnected", 0),
                    "event_types": ",".join(f"{k}:{v}" for k, v in sorted(counts.items())),
                    "n_customers": len(customers),
                    "customers": ",".join(customers[:50]),
                },
            })
    return chunks


# --------------------------------------------------------------------------
# Command line
# --------------------------------------------------------------------------
def _load(path: Path, date_arg: str | None, iface_map: dict | None = None):
    expected = date.fromisoformat(date_arg) if date_arg else None
    year = expected.year if expected else datetime.now().year
    raw_lines = path.read_text(encoding="utf-8").splitlines()
    events, bad = parse_log(raw_lines, year, iface_map)
    return events, bad, raw_lines, expected


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    v = sub.add_parser("validate", help="check a log (and optional answer key)")
    v.add_argument("log", type=Path)
    v.add_argument("--key", type=Path, help="ANSWER_KEY JSON file")
    v.add_argument("--date", help="expected date, YYYY-MM-DD")

    c = sub.add_parser("chunks", help="write chunks with metadata as JSONL")
    c.add_argument("log", type=Path)
    c.add_argument("--out", type=Path, default=Path("chunks.jsonl"))
    c.add_argument("--date", help="log date, YYYY-MM-DD (sets the year)")
    c.add_argument("--window", type=int, default=15, help="minutes per chunk window")
    c.add_argument("--max-lines", type=int, default=40)
    c.add_argument("--iface-map", default="",
                   help="core interfaces to towers, e.g. ether2=B,ether3=C")

    args = p.parse_args(argv)
    iface_map = dict(
        pair.split("=", 1) for pair in getattr(args, "iface_map", "").split(",") if "=" in pair
    )
    events, bad, raw_lines, expected = _load(args.log, args.date, iface_map)

    if args.cmd == "validate":
        key = json.loads(args.key.read_text(encoding="utf-8")) if args.key else None
        issues, stats = validate(events, bad, raw_lines, key, expected)
        return print_report(issues, stats)

    if bad:
        print(f"warning: skipped {len(bad)} unparsable lines", file=sys.stderr)
    chunks = chunk_events(events, args.log.name, args.window, args.max_lines)
    with args.out.open("w", encoding="utf-8") as f:
        for ch in chunks:
            f.write(json.dumps(ch, ensure_ascii=False) + "\n")
    print(f"wrote {len(chunks)} chunks from {len(events)} events to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())