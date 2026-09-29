#!/usr/bin/env python3
"""wisp_assistant.py 

Question -> filters (tower, date, time) -> notes + playbooks + log chunks
         -> exact counts from SQL -> checks -> prompt -> LLM -> cited answer.

Needs wisp_rag.py, wisp_log_tools.py, wisp_query.py in the same folder, an index
built with `wisp_rag.py ingest`, and events.db (ingest writes it when you pass --log).

Try it WITHOUT an API key first (prints exactly what the LLM would receive):
  python wisp_assistant.py ask "What happened to Tower B at 02:10 on 15 September?" --dry-run

With an LLM. Providers: kimi (Moonshot), gemini, openrouter, openai, anthropic, ollama (local).
Keys go in the terminal session or in a .env file that is in .gitignore:
  PowerShell:  $env:MOONSHOT_API_KEY="<key>"     $env:GEMINI_API_KEY="<key>"
               $env:OPENROUTER_API_KEY="<key>"   (one key, many models: ids look like vendor/model)
               $env:LLM_PROVIDER="kimi"          $env:LLM_MODEL="<a model id>"
  python wisp_assistant.py models --provider openrouter --filter kimi   (list ids, narrow by text)
  LOCAL (no key, nothing leaves your PC):  install Ollama, then  ollama pull <model>
               $env:LLM_PROVIDER="ollama"        $env:OLLAMA_MODEL="<name from: ollama list>"
  python wisp_assistant.py ask "How many customers dropped on Tower B on 14 September?"
  python wisp_assistant.py check-keys                   (keys and models for every provider)
  python wisp_assistant.py compare "Which user has the most login failures?" \
         --with kimi --with gemini            (models come from KIMI_MODEL, GEMINI_MODEL in .env)
         --with all                           (every provider that has a key and a model)
         --with kimi:<model id>               (or name the model here)
  python wisp_assistant.py compare-tests --tests assistant_tests.json \
         --with kimi:<model id> --with gemini:<model id>        (writes compare_report.md)
  python wisp_assistant.py compare-tests --with ollama --min-pass 0.8   (scorecard, error exit below 80%)
  python wisp_assistant.py chat
  python wisp_assistant.py ui          (needs: pip install gradio; add --host 0.0.0.0 inside Docker)
Paths can also come from WISP_DB and WISP_EVENTS_DB (used by the Docker setup).
The web UI has no login unless you set WISP_UI_USER and WISP_UI_PASSWORD. Set them before you expose it.

Optional settings: LLM_MAX_TOKENS (answer limit; thinking models spend part of it on reasoning),
LLM_REASONING_EFFORT (only if your model supports it), KIMI_BASE_URL (China: https://api.moonshot.cn/v1),
OPENROUTER_DATA_COLLECTION=deny (only route to providers that do not collect prompts).

PRIVACY: everything in the EVIDENCE section is sent to the LLM provider.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from wisp_query import extract_filters
from wisp_rag import Embedder, build_where, get_client, run_query, COLLECTION

SYSTEM_PROMPT = """You are a monitoring assistant for a small wireless ISP (WISP) network. \
You answer questions about network incidents using ONLY the FACTS, CHECKS and EVIDENCE in the message.

Rules:
1. Base every statement on the EVIDENCE, FACTS or CHECKS. After each claim taken from the EVIDENCE, \
cite its label in square brackets, for example [E1] or [E2, E3]. Copy the label exactly. \
FACTS and CHECKS need no citation and never take a bracket of any kind, not even [FACTS] or [CHECKS]: \
state what they say as plain sentences. This still applies when your whole answer comes only from FACTS \
and CHECKS with no EVIDENCE at all — in that case write it as plain sentences with no brackets anywhere. \
When you follow a playbook or incident note through several steps or sections, cite its label again in \
each section, not only once at the end: an uncited section is treated as unsupported.
2. FACTS are exact counts computed from the parsed logs. Use them for numbers and never recount from the evidence. \
"Distinct customers" counts customers, while "disconnect lines" counts log lines, and one customer can have several \
lines. Use the count that matches the wording of the question.
3. If the evidence does not contain what was asked (the tower, date, customer, device or cause), \
begin the answer with "Not found in the records." and state what was searched. Do not guess and do not use \
outside knowledge about this network.
4. Give a root cause only when an incident note states one. If a note says root_cause_status: not_confirmed, \
present its hypotheses as unconfirmed.
5. If CHECKS say something was not found, treat that as true. If CHECKS say no playbook exists for the problem, \
say that in your first sentence, then describe only what past incident notes did.
6. If none of the playbooks in the evidence is for this kind of problem, say there is no playbook for it and \
describe only what past incident notes did. For how-to questions, copy the commands from the evidence exactly as \
written and name the note or playbook they come from. Never write a command that is not in the evidence.
7. If the question has no date and the evidence covers more than one day, answer for each day separately.
8. Ignore evidence about a different problem, tower or day than the one asked about, unless you mention the \
difference.
9. Answer only what was asked. Do not list unrelated events. Keep it short: a direct answer first, then at most a \
few brief bullet points. Keep times as HH:MM:SS as in the logs.
10. Square brackets are only for evidence labels such as [E1]. Never write [FACTS] or [CHECKS], and never write \
file names, times or ids inside brackets. This is a hard rule even when the CHECKS wording itself looks like a \
sentence you could just copy: rewrite it, do not copy it verbatim with a bracket stuck on the end.
Example — wrong: "31 disconnects were recorded [FACTS]."
Example — right: "31 disconnects were recorded, per the parsed logs."
Example — wrong: "No log data exists for the requested date [CHECKS]."
Example — right: "No log data exists for the requested date, per the coverage check above."
11. When you describe a past incident, say whether a fix was applied. If a note says none was applied or it is \
still to do, say so. Never describe it as done."""

PROCEDURAL = re.compile(r"\bhow (do|can|should|to)\b|\bsteps?\b|\bfix\b|\brespond\b|\btroubleshoot|\bplaybook|"
                        r"\bwhat should\b|\bprocedure\b|\bresolve\b", re.I)
COUNTISH = re.compile(r"\bhow many\b|\bmost\b|\bcount\b|\bnumber of\b|\btop\b|\bwhich (tower|customer|user|ip|"
                      r"address|device|ap)\b|\btotal\b|\bhighest\b|\bmore than\b", re.I)
OUTAGE = re.compile(r"\boutage\b|\bwent down\b|\bwas down\b|\boffline\b|\bwent dark\b|\blost service\b|"
                    r"\bcompletely down\b", re.I)
NOT_IN_DATA = re.compile(r"\bphone\b|\bemail\b|\bbilling\b|\binvoice\b|\bpayment\b|\bhome address\b|"
                         r"\bcustomer name\b|\bwho is cust|\bwhose\b", re.I)
COUNT_TOPIC = re.compile(r"disconnect|\bdrop|outage|offline|lost service|went down|went dark|dark", re.I)
# Specific problem types, matching the incident_type values in your notes and playbooks. Used to keep only notes
# and playbooks about the problem asked, and to say so when no playbook exists for it.
TOPICS = {
    "ssh_brute_force": re.compile(r"\bssh\b|brute", re.I),
    "backhaul_down": re.compile(r"backhaul", re.I),
    "power_failure": re.compile(r"\bpower\b|blackout", re.I),
    "interference": re.compile(r"interference|channel change|\bnoise\b", re.I),
    "pppoe_auth_failures": re.compile(r"authentication fail|auth fail|pppoe.*(password|profile)", re.I),
    "address_pool_exhausted": re.compile(r"address pool|pool exhausted|no free address", re.I),
    "upstream_flap": re.compile(r"upstream|uplink|link flap|\bflap", re.I),
    "chronic_customer": re.compile(r"chronic|keeps? (dropping|disconnecting)|same customer", re.I),
}


def topic_of(question):
    hits = [t for t, rx in TOPICS.items() if rx.search(question)]
    return hits[0] if len(hits) == 1 else None


CREDENTIALS = re.compile(r"\bpassword\b|\bcredentials?\b|\bapi key\b|\bsecret\b", re.I)
RECOVERY_TOPIC = re.compile(r"reconnect|recover|restor|back online|came back|came up|service return|resum", re.I)
MAX_CHUNK_CHARS = 3500


# --------------------------------------------------------------------------
# Exact counts from SQL
# --------------------------------------------------------------------------
def _scope(f, use_tower=True):
    where, params, label = [], [], []
    if f.get("date"):
        where.append("date = ?")
        params.append(f["date"])
        label.append(f["date"])
    if use_tower and f.get("tower"):
        where.append("tower = ?")
        params.append(f["tower"])
        label.append(f"tower {f['tower']}")
    if f.get("date") and f.get("time_from"):
        where.append("substr(ts, 12, 5) >= ?")
        params.append(f["time_from"])
        label.append(f"from {f['time_from']}")
    if f.get("date") and f.get("time_to"):
        where.append("substr(ts, 12, 5) <= ?")
        params.append(f["time_to"])
        label.append(f"to {f['time_to']}")
    return where, params, (", ".join(label) or "all dates in the data")


def _grouped(con, etype, col, f, use_tower=True, distinct=None):
    where, params, label = _scope(f, use_tower)
    where.insert(0, "etype = ?")
    params.insert(0, etype)
    where.append(f"{col} IS NOT NULL")
    by_date = not f.get("date")
    agg = f"COUNT(DISTINCT {distinct})" if distinct else "COUNT(*)"
    if by_date:
        sql = (f"SELECT date, {col}, {agg} FROM events WHERE {' AND '.join(where)} "
               f"GROUP BY date, {col} ORDER BY date, 3 DESC")
    else:
        sql = (f"SELECT {col}, {agg} FROM events WHERE {' AND '.join(where)} "
               f"GROUP BY {col} ORDER BY 2 DESC")
    return con.execute(sql, params).fetchall(), label


def _distinct_customers(con, f):
    where, params, label = _scope(f)
    where.insert(0, "etype = 'pppoe_disconnected'")
    if f.get("date"):
        n = con.execute(f"SELECT COUNT(DISTINCT customer) FROM events WHERE {' AND '.join(where)}",
                        params).fetchone()[0]
        return f"Distinct customers with a PPPoE disconnect ({label}): {n}"
    rows = con.execute(f"SELECT date, COUNT(DISTINCT customer) FROM events WHERE {' AND '.join(where)} "
                       "GROUP BY date ORDER BY date", params).fetchall()
    return f"Distinct customers with a PPPoE disconnect ({label}): " + "; ".join(f"{d}: {n}" for d, n in rows)


def _fmt(rows, by_date, limit=5):
    if not rows:
        return "none"
    if not by_date:
        return ", ".join(f"{k}={n}" for k, n in rows[:limit])
    days = {}
    for d, k, n in rows:
        days.setdefault(d, []).append(f"{k}={n}")
    return "; ".join(f"{d}: " + ", ".join(v[:limit]) for d, v in sorted(days.items()))


def sql_facts(question, f, events_db):
    ql = question.lower()
    if not COUNTISH.search(question) or not Path(events_db).exists():
        return []
    con = sqlite3.connect(events_db)
    facts = []
    by_date = not f.get("date")
    if re.search(r"disconnect|drop|offline|lost service|dropped", ql):
        rows, label = _grouped(con, "pppoe_disconnected", "tower", f, use_tower=False)
        facts.append(f"PPPoE disconnect lines by tower ({label}): {_fmt(rows, by_date)}")
        facts.append(_distinct_customers(con, f))
        rows, label = _grouped(con, "pppoe_disconnected", "customer", f)
        facts.append(f"Customers with the most disconnect lines ({label}): {_fmt(rows, by_date)}")
    if re.search(r"login|brute|ssh|attack|password", ql):
        for col, name in (("ip", "source address"), ("user", "router user name")):
            rows, label = _grouped(con, "login_failure", col, f, use_tower=False)
            facts.append(f"Router login failures (SSH or winbox) by {name} ({label}): {_fmt(rows, by_date)}")
    if re.search(r"login|password|authenticat|auth\b|pppoe", ql):
        rows, label = _grouped(con, "pppoe_auth_failed", "customer", f)
        facts.append(f"PPPoE authentication failure lines in the parsed logs by customer ({label}): "
                     f"{_fmt(rows, by_date)}")
    if re.search(r"wireless|signal|\bap\b|interference", ql):
        rows, label = _grouped(con, "wireless_disconnected", "host", f, use_tower=False)
        facts.append(f"Wireless disconnects by device ({label}): {_fmt(rows, by_date)}")
    con.close()
    return facts


# --------------------------------------------------------------------------
# Retrieval
# --------------------------------------------------------------------------
def _meta_count(meta, key, etype):
    """A count stored on a chunk. Falls back to the event_types text for indexes built before the field existed."""
    if key in meta:
        return int(meta[key])
    m = re.search(rf"(?:^|,){etype}:(\d+)", str(meta.get("event_types", "")))
    return int(m.group(1)) if m else 0


class Assistant:
    def __init__(self, db="chroma_db", events_db="events.db"):
        client = get_client(db)
        try:
            self.coll = client.get_collection(COLLECTION)
        except Exception:
            sys.exit(f"no index in {db!r}. Run wisp_rag.py ingest first.")
        self.model_key = (self.coll.metadata or {}).get("model", "bge-small")
        self.embedder = Embedder(self.model_key)
        self.events_db = events_db
        metas = self.coll.get(include=["metadatas"])["metadatas"]
        self.known_dates = sorted({m["date"] for m in metas if "date" in m})
        self.log_dates = sorted({m["date"] for m in metas if m.get("type") == "log" and "date" in m})

    def _ns(self, **kw):
        base = dict(tower=None, date=None, type=None, incident_type=None, time_from=None, time_to=None)
        base.update(kw)
        return argparse.Namespace(**base)

    def gather(self, question, f, counting=False):
        evidence, seen, checks = [], set(), []

        def add(hits):
            for cid, dist, meta, doc in hits:
                if cid not in seen:
                    seen.add(cid)
                    evidence.append((cid, dist, meta, doc))
            return len(hits)

        days = f.get("dates") or [f.get("date")]
        scope = " ".join(x for x in (f"tower {f['tower']}" if f.get("tower") else "any tower",
                                     "on " + ", ".join(d for d in days if d) if any(days) else "") if x)
        topic = topic_of(question)
        for day in days:
            if day and self.log_dates and day not in self.log_dates:
                checks.append(f"No log data exists for {day}. The logs cover: {', '.join(self.log_dates)}.")
        # 1. incident notes (only the asked problem type, when some note of that type was found)
        note_hits = []
        for day in days:
            ns = self._ns(tower=f.get("tower"), date=day, type="incident")
            note_hits += run_query(self.coll, self.embedder, question, 3, build_where(ns))
        notes_found = len(note_hits)
        if topic and any(h[2].get("incident_type") == topic for h in note_hits):
            note_hits = [h for h in note_hits if h[2].get("incident_type") == topic]
        add(note_hits)
        if (f.get("tower") or any(days)) and notes_found == 0:
            checks.append(f"No incident notes exist for {scope}.")
        # 2. playbooks (for a known problem type, look for exactly that playbook)
        if PROCEDURAL.search(question):
            if topic:
                found = run_query(self.coll, self.embedder, question, 1,
                                  build_where(self._ns(type="playbook", incident_type=topic)))
                if found:
                    add(found)
                else:
                    metas = self.coll.get(where={"type": "playbook"}, include=["metadatas"])["metadatas"]
                    avail = sorted({str(m.get("incident_type", "?")).replace("_", " ") for m in metas})
                    checks.append(f"No playbook exists for {topic.replace('_', ' ')}. The playbooks that exist "
                                  f"cover: {', '.join(avail) or 'nothing'}.")
            else:
                add(run_query(self.coll, self.embedder, question, 2, build_where(self._ns(type="playbook"))))
        # 3. log chunks
        wide = False
        if f.get("time_from") and f.get("time_to"):
            h1, m1 = map(int, f["time_from"].split(":"))
            h2, m2 = map(int, f["time_to"].split(":"))
            wide = (h2 * 60 + m2) - (h1 * 60 + m1) >= 180
        k_logs = 8 if wide else (6 if (f.get("tower") or any(days)) else 4)
        if counting and not wide:
            k_logs = 3  # the exact counts come from SQL, so extra log chunks only add noise
        # anchor chunks: the log windows with the most disconnects (outage) or reconnects (recovery). Meaning-based
        # ranking tends to miss these big chunks in favour of many one-line chunks, so they are added by rule.
        specs = []
        if COUNT_TOPIC.search(question):
            specs.append(("n_disconnects", "pppoe_disconnected"))
        if RECOVERY_TOPIC.search(question):
            specs.append(("n_reconnects", "pppoe_connected"))
        if specs and (f.get("tower") or any(days)):
            for day in days:
                ns = self._ns(tower=f.get("tower"), date=day, type="log",
                              time_from=f.get("time_from") if day else None,
                              time_to=f.get("time_to") if day else None)
                got = self.coll.get(where=build_where(ns), include=["documents", "metadatas"])
                rows = list(zip(got["ids"], got["metadatas"], got["documents"]))
                for key, etype in specs:
                    ranked = sorted(rows, key=lambda r: -_meta_count(r[1], key, etype))
                    add([(cid, -1.0, meta, doc) for cid, meta, doc in ranked[:2]
                         if _meta_count(meta, key, etype) >= 5])
        for day in days:
            ns = self._ns(tower=f.get("tower"), date=day, type="log",
                          time_from=f.get("time_from") if day else None,
                          time_to=f.get("time_to") if day else None)
            add(run_query(self.coll, self.embedder, question, k_logs, build_where(ns)))
        if NOT_IN_DATA.search(question):
            checks.append("The records contain no customer names, phone numbers, addresses or billing data, "
                          "only PPPoE user ids such as cust-B007.")
        if CREDENTIALS.search(question):
            checks.append("The records never contain actual passwords, keys or credentials, only descriptions "
                          "of them in notes.")
        # 4. outage guard
        if OUTAGE.search(question) and (f.get("tower") or any(days)):
            has_pattern = any("mass disconnect" in d for _, _, _, d in evidence)
            has_note = any(m.get("incident_type") in ("backhaul_down", "power_failure")
                           for _, _, m, _ in evidence)
            if not (has_pattern or has_note):
                checks.append(f"No outage evidence (no mass-disconnect pattern in the logs and no "
                              f"backhaul or power incident note) was found for {scope}.")
                others = sorted({(m.get("incident_type"), m.get("date")) for _, _, m, _ in evidence
                                 if m.get("type") == "incident"
                                 and (not f.get("tower") or m.get("tower") == f["tower"])})
                if others:
                    checks.append("Incident notes found for this scope are of other types and are not "
                                  "outages: " + ", ".join(f"{t} on {d}" for t, d in others) + ".")
        return evidence, checks

    def build_prompt(self, question):
        f, notes = extract_filters(question, self.known_dates)
        if not f.get("date") and not f.get("dates") and f.get("time_from") and self.log_dates:
            f["dates"] = list(self.log_dates)
            notes.append("a time was given without a date, so every log date is searched")
        facts = sql_facts(question, f, self.events_db)
        evidence, checks = self.gather(question, f, counting=bool(facts))
        multi = len({m.get("date") for _, _, m, _ in evidence if m.get("date")}) > 1
        if not f.get("date") and multi:
            checks.append("The question gives no date and the evidence spans several days.")
        lines = [f"QUESTION: {question}",
                 f"FILTERS USED: {f or 'none'}" + (f" ({'; '.join(notes)})" if notes else ""), ""]
        lines.append("The following counts come from SQL over the parsed logs, not the evidence below:")
        lines += [f"- {x}" for x in facts] or ["- none for this question"]
        lines.append("\nThe following has already been verified against the full dataset and should be treated as settled:")
        lines += [f"- {x}" for x in checks] or ["- none"]
        lines.append("\nEVIDENCE:")
        if not evidence:
            lines.append("(nothing retrieved)")
        labels = {}
        for n, (cid, dist, meta, doc) in enumerate(evidence, 1):
            labels[f"E{n}"] = cid
            tag = " | ".join(str(meta[k]) for k in ("type", "tower", "date", "incident_type",
                                                    "root_cause_status") if k in meta)
            text = doc if len(doc) <= MAX_CHUNK_CHARS else doc[:MAX_CHUNK_CHARS] + "\n[...truncated...]"
            lines.append(f"\n[E{n}] ({tag})\n{text}")
        return {"system": SYSTEM_PROMPT, "user": "\n".join(lines), "filters": f, "facts": facts,
                "checks": checks, "evidence": evidence, "labels": labels}

    def dashboard_data(self, days=3):
        """Per-tower snapshot: recent event counts from events.db (last `days` distinct dates in the
        data, not wall-clock days, since the logs are historical fixtures) plus incident/playbook
        counts from the Chroma index. Returns (rows, window_label)."""
        con = sqlite3.connect(self.events_db)
        all_dates = [r[0] for r in con.execute("SELECT DISTINCT date FROM events ORDER BY date DESC")]
        window = sorted(all_dates[:days])
        window_label = ", ".join(window) if window else "no data"
        placeholders = ",".join("?" * len(window))
        towers = [r[0] for r in con.execute("SELECT DISTINCT tower FROM events WHERE tower IS NOT NULL "
                                            "ORDER BY tower")]
        metas = self.coll.get(include=["metadatas"])["metadatas"]

        def cnt(tower, etype):
            if not window:
                return 0
            if tower is None:
                return con.execute(f"SELECT COUNT(*) FROM events WHERE tower IS NULL AND etype = ? "
                                   f"AND date IN ({placeholders})", [etype, *window]).fetchone()[0]
            return con.execute(f"SELECT COUNT(*) FROM events WHERE tower = ? AND etype = ? "
                               f"AND date IN ({placeholders})", [tower, etype, *window]).fetchone()[0]

        def row_for(tower, label):
            n_incidents = sum(1 for m in metas if m.get("type") == "incident" and m.get("tower") == tower)
            n_playbooks = sum(1 for m in metas if m.get("type") == "playbook" and m.get("tower") == tower)
            return {
                "tower": label,
                "disconnects": cnt(tower, "pppoe_disconnected"),
                "auth failures": cnt(tower, "pppoe_auth_failed"),
                "login failures": cnt(tower, "login_failure"),
                "wireless drops": cnt(tower, "wireless_disconnected"),
                "incident notes": n_incidents,
                "playbooks": n_playbooks,
            }

        rows = [row_for(t, t) for t in towers]
        rows.append(row_for(None, "CORE / ungrouped"))
        con.close()
        return rows, window_label


# --------------------------------------------------------------------------
# LLM call (standard library only). One function, so providers are easy to swap.
# --------------------------------------------------------------------------
def load_dotenv(path=".env"):
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip("'\""))


class LLMError(Exception):
    pass


PROVIDERS = {
    "kimi": {"keys": ["MOONSHOT_API_KEY", "KIMI_API_KEY"], "base": "https://api.moonshot.ai/v1"},
    "gemini": {"keys": ["GEMINI_API_KEY"]},
    "openrouter": {"keys": ["OPENROUTER_API_KEY"], "base": "https://openrouter.ai/api/v1"},
    "openai": {"keys": ["OPENAI_API_KEY"], "base": "https://api.openai.com/v1"},
    "anthropic": {"keys": ["ANTHROPIC_API_KEY"]},
    "ollama": {"keys": [], "base": "http://localhost:11434"},
}
ALIASES = {"moonshot": "kimi", "google": "gemini"}
GEMINI = "https://generativelanguage.googleapis.com/v1beta"


def _request(url, headers, body=None, timeout=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", **headers},
                                 method="POST" if body is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout or float(os.environ.get("LLM_TIMEOUT", 180))) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raise LLMError(f"request failed ({e.code}): {e.read().decode(errors='replace')[:500]}")
    except urllib.error.URLError as e:
        raise LLMError(f"could not reach the provider: {e.reason}")
    except TimeoutError:
        raise LLMError("the request timed out. Local models can be slow: raise LLM_TIMEOUT (seconds).")


OLLAMA_HINT = (" | Is Ollama running? Start the Ollama app (or run 'ollama serve') and check with: "
               "python wisp_assistant.py check-keys")


def _is_ollama(url):
    return "/api/chat" in url or "/api/tags" in url


GEMINI_HINT = (" | Google did not accept the key. It must be a Gemini API key made in Google AI Studio "
               "(aistudio.google.com, 'Get API key'), set as GEMINI_API_KEY in this same terminal, with no "
               "quotes or spaces. Run: python wisp_assistant.py check-keys")


def _post(url, headers, body, timeout=None):
    try:
        return _request(url, headers, body, timeout)
    except LLMError as e:
        if "generativelanguage" in url and any(c in str(e) for c in ("(401)", "(403)", "API key not valid")):
            raise LLMError(str(e) + GEMINI_HINT)
        if _is_ollama(url) and "could not reach" in str(e):
            raise LLMError(str(e) + OLLAMA_HINT)
        raise


def _get(url, headers, timeout=None):
    try:
        return _request(url, headers, None, timeout)
    except LLMError as e:
        if "generativelanguage" in url and any(c in str(e) for c in ("(401)", "(403)", "API key not valid")):
            raise LLMError(str(e)[:300] + GEMINI_HINT)
        if _is_ollama(url) and "could not reach" in str(e):
            raise LLMError(str(e) + OLLAMA_HINT)
        raise


def key_report():
    """Key and model status for every provider. Keys themselves are never printed."""
    lines = []
    for prov, cfg in PROVIDERS.items():
        if prov == "ollama":
            base = os.environ.get("OLLAMA_BASE_URL", cfg["base"]).rstrip("/")
            try:
                n = len(_get(f"{base}/api/tags", {}, timeout=3).get("models", []))
                key_txt = f"no key needed. Ollama is running at {base} with {n} model(s) installed"
            except LLMError:
                key_txt = f"no key needed. Ollama is NOT reachable at {base} (start the Ollama app)"
            model = os.environ.get("OLLAMA_MODEL", "")
            if not model and os.environ.get("LLM_MODEL") and os.environ.get("LLM_PROVIDER", "").lower() == "ollama":
                model = os.environ["LLM_MODEL"]
            lines.append(f"{prov:11} {key_txt}")
            lines.append(f"{'':11} model: {model or 'not set (OLLAMA_MODEL)'}")
            continue
        var = next((k for k in cfg["keys"] if os.environ.get(k) is not None), cfg["keys"][0])
        v = os.environ.get(var)
        if v is None:
            key_txt = f"{var} not set"
        else:
            flags = []
            if v != v.strip():
                flags.append("spaces or a line break at the ends")
            if v.strip() and (v.strip()[0] in "'\"" or v.strip()[-1] in "'\""):
                flags.append("quote marks around it")
            if " " in v.strip():
                flags.append("a space inside it")
            if not v.strip():
                flags.append("EMPTY")
            if prov == "gemini" and v.strip() and not v.strip().startswith("AIza"):
                flags.append("does not start with AIza, which AI Studio keys usually do")
            key_txt = (f"{var} length {len(v)}, starts with {v[:4]!r}"
                       + (f"  <-- {'; '.join(flags)}" if flags else " (looks fine)"))
        model = os.environ.get(f"{prov.upper()}_MODEL", "")
        if not model and os.environ.get("LLM_MODEL") and ALIASES.get(
                os.environ.get("LLM_PROVIDER", "").lower(), os.environ.get("LLM_PROVIDER", "").lower()) == prov:
            model = os.environ["LLM_MODEL"]
        lines.append(f"{prov:11} key: {key_txt}")
        lines.append(f"{'':11} model: {model or f'not set ({prov.upper()}_MODEL)'}")
    lines.append(f"\nask and chat use: {os.environ.get('LLM_PROVIDER') or 'not set (LLM_PROVIDER)'}")
    return lines


def configured_specs():
    """Every provider that has both a key and a model, for --with all."""
    use, skipped = [], []
    for prov in PROVIDERS:
        try:
            _, model, _, _ = settings(prov, "")
        except LLMError:
            skipped.append(f"{prov} (no key)")
            continue
        (use if model else skipped).append((prov, "") if model else f"{prov} (no model)")
    return use, skipped


def settings(provider=None, model=None):
    """Resolve provider, model, key and base URL. Model order: given > <PROVIDER>_MODEL > LLM_MODEL."""
    env_provider = ALIASES.get(os.environ.get("LLM_PROVIDER", "").lower(), os.environ.get("LLM_PROVIDER", "").lower())
    provider = ALIASES.get((provider or env_provider).lower(), (provider or env_provider).lower())
    if provider not in PROVIDERS:
        raise LLMError("set LLM_PROVIDER to kimi, gemini, openrouter, openai, anthropic or ollama (or use --dry-run)")
    cfg = PROVIDERS[provider]
    key = next((os.environ[k] for k in cfg["keys"] if os.environ.get(k)), "")
    if not key and provider != "ollama":
        raise LLMError(f"set {' or '.join(cfg['keys'])} (environment variable or .env file). "
                       "Variables set with $env: only exist in that terminal window.")
    base = cfg.get("base")
    if provider == "kimi":
        base = os.environ.get("KIMI_BASE_URL", base)
    elif provider == "ollama":
        base = os.environ.get("OLLAMA_BASE_URL", base).rstrip("/")
    model = (model or os.environ.get(f"{provider.upper()}_MODEL", "")
             or (os.environ.get("LLM_MODEL", "") if provider == env_provider else ""))
    return provider, model, key, base


def parse_spec(spec):
    prov, _, model = spec.partition(":")
    return ALIASES.get(prov.lower(), prov.lower()), model


def _per_million(x):
    try:
        return f"{float(x) * 1e6:.2f}"
    except (TypeError, ValueError):
        return "?"


def list_models(provider=None, contains=None):
    provider, _, key, base = settings(provider, "x")
    if provider == "ollama":
        r = _get(f"{base}/api/tags", {}, timeout=10)  # plain names, exactly what OLLAMA_MODEL needs
        out = [m["name"] for m in r.get("models", [])]
    elif provider == "anthropic":
        r = _get("https://api.anthropic.com/v1/models", {"x-api-key": key, "anthropic-version": "2023-06-01"})
        out = [m["id"] for m in r.get("data", [])]
    elif provider == "gemini":
        r = _get(f"{GEMINI}/models?pageSize=200", {"x-goog-api-key": key})
        out = [m["name"].removeprefix("models/") for m in r.get("models", [])
               if "generateContent" in m.get("supportedGenerationMethods", [])]
    else:
        r = _get(f"{base}/models", {"Authorization": f"Bearer {key}"})
        out = []
        for m in r.get("data", []):
            pr = m.get("pricing") or {}
            price = (f"   (listed USD per million tokens: in {_per_million(pr.get('prompt'))}, "
                     f"out {_per_million(pr.get('completion'))})") if provider == "openrouter" and pr else ""
            out.append(m["id"] + price)
    if contains:
        out = [x for x in out if contains.lower() in x.lower()]
    return sorted(out)


def ask_llm(system: str, user: str, provider=None, model=None):
    """Returns (answer_text, usage). One function, so providers are easy to swap."""
    provider, model, key, base = settings(provider, model)
    if not model:
        raise LLMError(f"set {provider.upper()}_MODEL in .env, or use --with {provider}:<model id> "
                       "(run the 'models' command to see the ids your key can use)")
    mt = int(os.environ["LLM_MAX_TOKENS"]) if os.environ.get("LLM_MAX_TOKENS") else None
    effort = os.environ.get("LLM_REASONING_EFFORT")
    if provider == "ollama":
        # The native API is used on purpose: Ollama's OpenAI-style /v1 endpoint cannot set the context
        # window, so it silently cuts long prompts to ~4096 tokens and the rules at the top get lost.
        est = int((len(system) + len(user)) / 2.6) + 1500
        num_ctx = int(os.environ["OLLAMA_NUM_CTX"]) if os.environ.get("OLLAMA_NUM_CTX") else \
            min(max(8192, -(-est // 1024) * 1024), 32768)
        opts = {"num_ctx": num_ctx, "temperature": float(os.environ.get("OLLAMA_TEMPERATURE", 0))}
        if mt:
            opts["num_predict"] = mt
        body = {"model": model, "stream": False, "options": opts,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        # think defaults to false (much faster for local models). true, or low/medium/high for models that use levels.
        think = os.environ.get("OLLAMA_THINK", "false").strip().lower()
        body["think"] = (True if think in ("1", "true", "yes", "on") else
                         think if think in ("low", "medium", "high") else False)
        timeout = float(os.environ.get("LLM_TIMEOUT") or 900)
        try:
            r = _post(f"{base}/api/chat", {}, body, timeout)
        except LLMError as e:
            if "think" in str(e).lower() and "think" in body:  # this model rejects the think option: retry without it
                body.pop("think")
                r = _post(f"{base}/api/chat", {}, body, timeout)
            else:
                raise
        if r.get("error"):
            raise LLMError(str(r["error"])[:300])
        text = ((r.get("message") or {}).get("content") or "").strip()
        pe = r.get("prompt_eval_count")
        if pe and pe >= 0.97 * num_ctx:
            raise LLMError(f"the prompt ({pe} tokens) fills the whole context window ({num_ctx}), so the model "
                           "may not have seen the start of it. Set OLLAMA_NUM_CTX higher (uses more memory) "
                           "or ask a narrower question.")
        if not text:
            raise LLMError(f"the model returned an empty answer (done_reason={r.get('done_reason')}). "
                           "Thinking models can use the whole budget on reasoning: try OLLAMA_THINK=false.")
        return text, {"in": pe, "out": r.get("eval_count"), "via": f"local, {num_ctx} context"}
    if provider == "anthropic":
        r = _post("https://api.anthropic.com/v1/messages",
                  {"x-api-key": key, "anthropic-version": "2023-06-01"},
                  {"model": model, "max_tokens": mt or 1500, "system": system,
                   "messages": [{"role": "user", "content": user}]})
        u = r.get("usage", {})
        return ("".join(b.get("text", "") for b in r.get("content", [])),
                {"in": u.get("input_tokens"), "out": u.get("output_tokens")})
    if provider in ("openai", "kimi", "openrouter"):
        body = {"model": model, "messages": [{"role": "system", "content": system},
                                             {"role": "user", "content": user}]}
        if mt:
            body["max_completion_tokens" if provider == "openai" else "max_tokens"] = mt
        if effort:
            if provider == "openrouter":
                body["reasoning"] = {"effort": effort}
            else:
                body["reasoning_effort"] = effort
        if provider == "openrouter" and os.environ.get("OPENROUTER_DATA_COLLECTION"):
            body["provider"] = {"data_collection": os.environ["OPENROUTER_DATA_COLLECTION"]}
        r = _post(f"{base}/chat/completions", {"Authorization": f"Bearer {key}"}, body)
        if not r.get("choices"):
            raise LLMError(f"no answer returned: {str(r.get('error') or r)[:300]}")
        choice = r["choices"][0]
        text = (choice.get("message", {}).get("content") or "").strip()
        u = r.get("usage", {})
        if not text:
            raise LLMError(f"the model returned an empty answer (finish_reason={choice.get('finish_reason')}). "
                           "If it is 'length', reasoning used the whole budget: raise LLM_MAX_TOKENS.")
        via = r.get("provider") if isinstance(r.get("provider"), str) else None
        return text, {"in": u.get("prompt_tokens"), "out": u.get("completion_tokens"), "via": via}
    # gemini
    body = {"systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}]}
    if mt:
        body["generationConfig"] = {"maxOutputTokens": mt}
    r = _post(f"{GEMINI}/models/{model.removeprefix('models/')}:generateContent",
              {"x-goog-api-key": key}, body)
    cands = r.get("candidates") or []
    if not cands:
        raise LLMError(f"Gemini returned no answer: {r.get('promptFeedback') or str(r)[:300]}")
    text = "".join(p.get("text", "") for p in cands[0].get("content", {}).get("parts", [])).strip()
    if not text:
        raise LLMError(f"Gemini returned an empty answer (finishReason={cands[0].get('finishReason')}). "
                       "Try raising LLM_MAX_TOKENS.")
    u = r.get("usageMetadata", {})
    return text, {"in": u.get("promptTokenCount"),
                  "out": (u.get("candidatesTokenCount") or 0) + (u.get("thoughtsTokenCount") or 0)}


CITE_RE = re.compile(r"\[([^\[\]]+)\]")


BANNED_BRACKETS = {"FACTS", "CHECKS", "CHECK", "FACT"}


def check_citations(answer: str, evidence_ids, labels=None) -> list[str]:
    """Flag any citation that is not a real evidence label or id, and the literal [FACTS]/[CHECKS] rule 10 bans."""
    labels = labels or {}
    problems = []
    for inner in CITE_RE.findall(answer):
        for tok in (x.strip() for x in re.split(r"[,;]", inner)):
            if not tok or re.fullmatch(r"\d{2}:\d{2}(:\d{2})?", tok):
                continue
            if tok.upper() in BANNED_BRACKETS:
                problems.append(f"[{tok}]")
            elif re.fullmatch(r"E\d+", tok):
                if tok not in labels:
                    problems.append(tok)
            elif re.search(r"^[NP]-\d|:", tok) and not any(tok == e or e.startswith(tok + ":")
                                                          for e in evidence_ids):
                problems.append(tok)
    return problems


def uncited_sources(answer: str, evidence, labels) -> list[str]:
    """A playbook that was in the prompt but whose label never appears anywhere in the raw answer.
    Scoped to playbooks only: they are added specifically because the question asked how to do something,
    so describing their steps without naming them is the exact rule-1 violation this catches. Incident
    notes and log chunks are excluded here, because they are added to every question regardless of
    relevance and a short factual answer legitimately may not need to reference one that's just along
    for context. A model occasionally writes the real id instead of the label it was given; either counts
    as cited."""
    cited_labels = set(re.findall(r"\bE\d+\b", answer))
    missing = []
    for label, cid in labels.items():
        meta = next((m for c, _, m, _ in evidence if c == cid), {})
        if meta.get("type") == "playbook" and label not in cited_labels and cid not in answer:
            missing.append(cid)
    return missing


def expand_labels(text: str, labels) -> str:
    """Replace [E1] with the real chunk id, so answers show exact ids the model never had to copy."""
    def sub(m):
        parts = [x.strip() for x in re.split(r"[,;]", m.group(1))]
        if parts and all(re.fullmatch(r"E\d+", x) for x in parts):
            return "[" + ", ".join(labels.get(x, x) for x in parts) + "]"
        return m.group(0)
    return CITE_RE.sub(sub, text)


def answer_question(assistant, question, dry_run=False, provider=None, model=None):
    p = assistant.build_prompt(question)
    ids = [e[0] for e in p["evidence"]]
    if dry_run:
        return p, None, [], None
    raw, usage = ask_llm(p["system"], p["user"], provider, model)
    problems = check_citations(raw, ids, p["labels"]) + [f"never cited: {c}" for c in
                                                         uncited_sources(raw, p["evidence"], p["labels"])]
    return p, expand_labels(raw, p["labels"]), problems, usage


def grade(answer, t):
    """Rough string checks from the test file. Read the answers too: these are only a hint."""
    a, notes = answer.lower(), []
    notes += [f"missing {x!r}" for x in t.get("expect_all", [])
              if not any(alt.strip().lower() in a for alt in x.split("|"))]
    anyof = t.get("expect_any", [])
    if anyof and not any(x.lower() in a for x in anyof):
        notes.append("none of: " + " / ".join(anyof))
    notes += [f"contains {x!r}" for x in t.get("forbid", []) if x.lower() in a]
    return not notes, notes


def run_compare(assistant, questions, specs, report_path=None):
    """questions: list of dicts with 'question' and optional checks. specs: [(provider, model)]."""
    rows, md = [], ["# Provider comparison\n"]
    for t in questions:
        p = assistant.build_prompt(t["question"])
        ids = [e[0] for e in p["evidence"]]
        md.append(f"## {t['question']}\n\nFilters: `{p['filters']}`; evidence chunks: {len(ids)}; "
                  f"prompt: {len(p['system']) + len(p['user'])} characters\n")
        for prov, model in specs:
            t0 = time.perf_counter()
            try:
                model = settings(prov, model)[1] or model
            except LLMError:
                pass
            try:
                raw, usage = ask_llm(p["system"], p["user"], prov, model)
                text, err = expand_labels(raw, p["labels"]), None
            except LLMError as e:
                raw, text, usage, err = "", "", {}, str(e)
            secs = time.perf_counter() - t0
            bad = (check_citations(raw, ids, p["labels"])
                  + [f"never cited: {c}" for c in uncited_sources(raw, p["evidence"], p["labels"])]) if raw else []
            ok, notes = grade(text, t) if text else (False, [err or "no answer"])
            rows.append((t["question"], f"{prov}:{model}", ok, bad, secs, usage, err))
            md.append(f"### {prov}:{model}  ({secs:.1f}s, tokens in/out: "
                      f"{usage.get('in')}/{usage.get('out')}"
                      + (f"; served by {usage['via']}" if usage.get("via") else "")
                      + f"; checks: {'PASS' if ok else 'FAIL'}"
                      + (f" - {'; '.join(notes)}" if notes else "") + ")\n")
            if bad:
                md.append(f"**Citations not in the evidence:** {', '.join(bad)}\n")
            md.append((text or f"ERROR: {err}") + "\n")
    if report_path:
        Path(report_path).write_text("\n".join(md), encoding="utf-8")
    return rows


# --------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------
def show(p, text, problems, dry_run, usage=None):
    if dry_run:
        print("=== SYSTEM ===\n" + p["system"] + "\n\n=== USER ===\n" + p["user"])
        print(f"\n(dry run: nothing was sent. prompt size {len(p['system']) + len(p['user'])} characters, "
              f"{len(p['evidence'])} evidence chunks)")
        return
    print(text.strip() + "\n")
    if problems:
        print("WARNING: citation problems:", "; ".join(problems))
    print("Evidence used:")
    for cid, dist, meta, _ in p["evidence"]:
        print(f"  {cid}  ({'largest event in scope' if dist < 0 else f'dist {dist:.3f}'})")
    if usage and usage.get("in") is not None:
        print(f"\ntokens: {usage.get('in')} in, {usage.get('out')} out")


UI_CSS = """
:root {
    --wisp-bg: #0a0e14; --wisp-panel: #10151f; --wisp-border: #22303f;
    --wisp-accent: #39ff9d; --wisp-accent-dim: #1fae6b; --wisp-cyan: #4fd6e8;
    --wisp-text: #cfe8dd; --wisp-dim: #6f8a80; --wisp-warn: #ffb454; --wisp-bad: #ff5d5d;
}
.gradio-container {
    background: var(--wisp-bg) !important;
    font-family: "JetBrains Mono", "Fira Code", "Consolas", monospace !important;
}
#wisp-header {
    border-bottom: 1px solid var(--wisp-border); padding-bottom: 10px; margin-bottom: 6px;
}
#wisp-header h1 {
    color: var(--wisp-accent); letter-spacing: 1px; font-size: 1.4rem; margin: 0;
}
#wisp-header p { color: var(--wisp-dim); margin: 2px 0 0 0; font-size: 0.85rem; }
.wisp-panel {
    background: var(--wisp-panel) !important; border: 1px solid var(--wisp-border) !important;
    border-radius: 6px !important;
}
#wisp-answer { color: var(--wisp-text) !important; }
#wisp-answer h1, #wisp-answer h2, #wisp-answer h3 { color: var(--wisp-cyan) !important; }
#wisp-citations, #wisp-evidence {
    font-size: 0.82rem !important; color: var(--wisp-text) !important;
}
#wisp-citations code, #wisp-evidence code {
    color: var(--wisp-accent) !important; background: rgba(57,255,157,0.08) !important;
}
#wisp-warning { color: var(--wisp-warn) !important; }
button.primary {
    background: var(--wisp-accent-dim) !important; border: none !important; color: #04140b !important;
}
"""

def _wisp_theme(gr):
    return gr.themes.Base(
        primary_hue=gr.themes.colors.emerald, neutral_hue=gr.themes.colors.slate,
        font=[gr.themes.GoogleFont("JetBrains Mono"), "monospace"],
    ).set(
        body_background_fill="#0a0e14", body_text_color="#cfe8dd",
        block_background_fill="#10151f", block_border_color="#22303f",
        border_color_primary="#22303f", input_background_fill="#0d1420",
    )


def _cited_evidence(text, p):
    """Evidence chunks whose real id appears in the final (label-expanded) answer text."""
    used = []
    for cid, dist, meta, _ in p["evidence"]:
        if cid in text:
            tag = " | ".join(str(meta[k]) for k in ("type", "tower", "date", "incident_type") if k in meta)
            used.append((cid, tag))
    return used


def build_ui(assistant, host, port):
    import gradio as gr

    def respond(q):
        if not q.strip():
            return "Type a question.", "_(none yet)_", "_(none yet)_", ""
        try:
            p, text, problems, _ = answer_question(assistant, q)
        except LLMError as e:
            return f"**Error:** {e}", "_(none)_", "_(none)_", ""
        cited = _cited_evidence(text, p)
        cite_md = ("\n".join(f"- `{cid}`  ({tag})" for cid, tag in cited)
                   if cited else "_no evidence chunk was directly cited_")
        ranked_md = "\n".join(
            f"- `{cid}`  " + ("**(anchor: largest event in scope)**" if dist < 0 else f"dist `{dist:.3f}`")
            + "  " + " | ".join(str(meta[k]) for k in ("type", "tower", "date", "incident_type") if k in meta)
            for cid, dist, meta, _ in p["evidence"]
        ) or "_(nothing retrieved)_"
        warn = (f"**Warning — citation problems:** {', '.join(problems)}" if problems else "")
        return text, cite_md, ranked_md, warn

    def refresh_dashboard(days):
        rows, window = assistant.dashboard_data(int(days))
        table = [[r["tower"], r["disconnects"], r["auth failures"], r["login failures"],
                  r["wireless drops"], r["incident notes"], r["playbooks"]] for r in rows]
        return table, f"window: {window}"

    with gr.Blocks(title="WISP monitoring assistant (MikroTik)") as demo:
        gr.HTML('<div id="wisp-header"><h1>&gt; WISP_MONITOR</h1>'
                '<p>RAG-backed network incident assistant for MikroTik (RouterOS) networks &mdash; '
                'cited answers over parsed logs, incident notes and playbooks</p></div>')
        with gr.Tabs():
            with gr.Tab("Ask"):
                question = gr.Textbox(label="Question", lines=2, placeholder="e.g. What happened to Tower B "
                                       "at 02:10 on 15 September?", elem_classes=["wisp-panel"])
                ask_btn = gr.Button("Run query", variant="primary")
                warning = gr.Markdown(elem_id="wisp-warning")
                with gr.Row():
                    with gr.Column(scale=3):
                        gr.Markdown("### Answer")
                        answer = gr.Markdown(elem_id="wisp-answer", elem_classes=["wisp-panel"])
                    with gr.Column(scale=2):
                        gr.Markdown("### Citations used")
                        citations = gr.Markdown(elem_id="wisp-citations", elem_classes=["wisp-panel"])
                        gr.Markdown("### Ranked evidence (retrieval)")
                        evidence = gr.Markdown(elem_id="wisp-evidence", elem_classes=["wisp-panel"])
                ask_btn.click(respond, inputs=question, outputs=[answer, citations, evidence, warning])
                question.submit(respond, inputs=question, outputs=[answer, citations, evidence, warning])
            with gr.Tab("Dashboard"):
                gr.Markdown("### Per-tower recent event counts")
                days_slider = gr.Slider(1, 14, value=3, step=1, label="Window (most recent N dates in the data)")
                window_label = gr.Markdown()
                dash_table = gr.Dataframe(
                    headers=["tower", "disconnects", "auth failures", "login failures",
                             "wireless drops", "incident notes", "playbooks"],
                    elem_classes=["wisp-panel"])
                refresh_btn = gr.Button("Refresh")
                demo.load(refresh_dashboard, inputs=days_slider, outputs=[dash_table, window_label])
                refresh_btn.click(refresh_dashboard, inputs=days_slider, outputs=[dash_table, window_label])
                days_slider.release(refresh_dashboard, inputs=days_slider, outputs=[dash_table, window_label])
    demo.launch(
        server_name=host, server_port=port, css=UI_CSS, theme=_wisp_theme(gr),
        auth=((os.environ["WISP_UI_USER"], os.environ["WISP_UI_PASSWORD"])
              if os.environ.get("WISP_UI_USER") and os.environ.get("WISP_UI_PASSWORD") else None))


def main(argv=None):
    load_dotenv()
    ap = argparse.ArgumentParser(description="WISP monitoring assistant")
    ap.add_argument("--db", default=os.environ.get("WISP_DB", "chroma_db"))
    ap.add_argument("--events-db", default=os.environ.get("WISP_EVENTS_DB", "events.db"))
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("ask", help="answer one question")
    a.add_argument("question")
    a.add_argument("--dry-run", action="store_true", help="print the prompt, do not call the LLM")
    sub.add_parser("chat", help="ask several questions in the terminal")
    u = sub.add_parser("ui", help="open a browser chat window (needs gradio)")
    u.add_argument("--host", default=os.environ.get("WISP_HOST", "127.0.0.1"),
                   help="use 0.0.0.0 inside Docker; keep 127.0.0.1 otherwise")
    u.add_argument("--port", type=int, default=int(os.environ.get("WISP_PORT", 7860)))
    sub.add_parser("check-keys", help="show which key variables are set (keys are not printed)")
    m = sub.add_parser("models", help="list the model ids your key can use")
    m.add_argument("--provider")
    m.add_argument("--filter", help="only ids containing this text, e.g. kimi or gemini")
    c = sub.add_parser("compare", help="ask one question with several providers")
    c.add_argument("question")
    c.add_argument("--with", dest="specs", action="append", metavar="PROVIDER[:MODEL] | all",
                   help="repeat for several; defaults to LLM_PROVIDER")
    ct = sub.add_parser("compare-tests", help="run a test file with several providers, write a report")
    ct.add_argument("--tests", default="assistant_tests.json")
    ct.add_argument("--with", dest="specs", action="append", metavar="PROVIDER[:MODEL] | all",
                    help="repeat for several; defaults to LLM_PROVIDER")
    ct.add_argument("--report", default="compare_report.md")
    ct.add_argument("--min-pass", type=float, default=None, metavar="0.8",
                    help="exit with an error if a model passes fewer than this share of the tests")
    args = ap.parse_args(argv)
    if args.cmd == "compare":
        args.min_pass = None
    if args.cmd in ("compare", "compare-tests") and not args.specs:
        if not os.environ.get("LLM_PROVIDER"):
            ap.error("give --with PROVIDER (or 'all'), or set LLM_PROVIDER in .env")
        args.specs = [os.environ["LLM_PROVIDER"]]

    try:
        if args.cmd == "check-keys":
            print("\n".join(key_report()))
            return
        if args.cmd == "models":
            names = list_models(args.provider, args.filter)
            print("\n".join(names) if names else "no models matched")
            return
        assistant = Assistant(args.db, args.events_db)
        if args.cmd == "ask":
            p, text, problems, usage = answer_question(assistant, args.question, args.dry_run)
            show(p, text, problems, args.dry_run, usage)
        elif args.cmd == "chat":
            print("Ask a question (empty line to quit).")
            while True:
                q = input("\n> ").strip()
                if not q:
                    break
                p, text, problems, usage = answer_question(assistant, q)
                show(p, text, problems, False, usage)
        elif args.cmd in ("compare", "compare-tests"):
            if any(x.lower() == "all" for x in args.specs):
                specs, skipped = configured_specs()
                if not specs:
                    sys.exit("no provider has both a key and a model. Run: python wisp_assistant.py check-keys")
                print("comparing:", ", ".join(f"{a} ({settings(a, '')[1]})" for a, _ in specs)
                      + (f"\nskipped: {', '.join(skipped)}" if skipped else "") + "\n")
            else:
                specs = [parse_spec(x) for x in args.specs]
            if args.cmd == "compare":
                tests = [{"question": args.question}]
                report = "compare_report.md"
            else:
                tests = json.loads(Path(args.tests).read_text(encoding="utf-8"))
                report = args.report
            rows = run_compare(assistant, tests, specs, report)
            print(f"{'question':46} {'model':44} {'checks':7} {'cites':6} {'sec':>5}")
            for q, who, ok, bad, secs, usage, err in rows:
                print(f"{q[:45]:46} {who[:43]:44} {'PASS' if ok else 'FAIL':7} "
                      f"{'bad' if bad else 'ok':6} {secs:5.1f}" + (f"  ERROR: {err[:60]}" if err else ""))
            print(f"\nfull answers in {report}")
            score = {}
            for q, who, ok, bad, secs, usage, err in rows:
                r = score.setdefault(who, [0, 0, 0, 0.0])
                r[0] += bool(ok)
                r[1] += 1
                r[2] += bool(bad)
                r[3] += secs
            print(f"\n{'scorecard':44} {'passed':>12} {'bad citations':>14} {'avg sec':>8}")
            below = []
            for who, (n_ok, n, n_bad, tot) in score.items():
                print(f"{who[:43]:44} {f'{n_ok}/{n} ({100 * n_ok // n}%)':>12} {n_bad:>14} {tot / n:8.1f}")
                if args.min_pass is not None and n_ok / n < args.min_pass:
                    below.append(who)
            if args.min_pass is not None:
                print(f"\nthreshold {args.min_pass:.0%}: " + ("BELOW for " + ", ".join(below) if below else "met"))
                if below:
                    sys.exit(1)
        else:
            try:
                import gradio  # noqa: F401
            except ImportError:
                sys.exit("run: pip install gradio")
            build_ui(assistant, args.host, args.port)
    except LLMError as e:
        sys.exit(f"LLM error: {e}")


if __name__ == "__main__":
    main()