#!/usr/bin/env python3
"""wisp_rag.py - step 2 and 3: index logs, notes and playbooks, then test retrieval.

No LLM in here. The point is to prove that the right chunks come back
BEFORE you connect a language model.

Needs wisp_log_tools.py and wisp_query.py in the same folder, and:
  pip install chromadb sentence-transformers

Commands:
  python wisp_rag.py ingest --log day1.log@2026-09-14 --notes notes --playbooks playbooks
  (add --iface-map ether3=B only if your log has link up/down lines;
   add --window 30 for longer incidents)
  python wisp_rag.py search "why did tower B go down at 02:10" -k 5
  python wisp_rag.py search "backhaul down steps" --type playbook
  python wisp_rag.py search "tower B outage" --tower B --date 2026-09-14
  python wisp_rag.py search "what happened" --tower B --date 2026-09-14 --from 02:00 --to 03:00
  python wisp_rag.py search "What happened to Tower B at 02:10 on 15 September?" --auto
  (search and eval use meaning + keywords; add --mode vector for meaning only)
  python wisp_rag.py make-tests --key day1_key.json --out retrieval_tests.json
  python wisp_rag.py eval --tests retrieval_tests.json -k 5

Notes and playbooks are Markdown files with a front matter block (--- ... ---).
Front matter fields become searchable metadata.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sqlite3
import statistics
import sys
import zlib
from collections import Counter
from datetime import date, datetime
from pathlib import Path

from wisp_log_tools import UNANSWERABLE_RE, chunk_events, parse_log
from wisp_query import extract_filters

# key: (hugging face name, passage prefix, query prefix)
MODELS = {
    "bge-small": ("BAAI/bge-small-en-v1.5", "",
                  "Represent this sentence for searching relevant passages: "),
    "e5-small": ("intfloat/multilingual-e5-small", "passage: ", "query: "),
    "hash": (None, "", ""),  # offline smoke test only, not for real use
}
COLLECTION = "wisp"
MAX_WORDS = 400  # notes longer than this are split by "## " sections


# --------------------------------------------------------------------------
# Embeddings
# --------------------------------------------------------------------------
class Embedder:
    def __init__(self, key: str):
        if key not in MODELS:
            sys.exit(f"unknown model {key!r}; choose from {', '.join(MODELS)}")
        self.key = key
        name, self.doc_prefix, self.query_prefix = MODELS[key]
        self.model = None
        if name:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError:
                sys.exit("run: pip install sentence-transformers")
            self.model = SentenceTransformer(name)

    def _encode(self, texts):
        if self.model is not None:
            return self.model.encode(texts, normalize_embeddings=True).tolist()
        out = []
        for t in texts:
            v = [0.0] * 512
            for tok in re.findall(r"\w+", t.lower()):
                v[zlib.crc32(tok.encode()) % 512] += 1.0
            norm = sum(x * x for x in v) ** 0.5 or 1.0
            out.append([x / norm for x in v])
        return out

    def docs(self, texts):
        return self._encode([self.doc_prefix + t for t in texts])

    def queries(self, texts):
        return self._encode([self.query_prefix + t for t in texts])


# --------------------------------------------------------------------------
# Loading documents
# --------------------------------------------------------------------------
def parse_front_matter(text: str):
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", text, re.S)
    if not m:
        return {}, text.strip()
    meta = {}
    for line in m.group(1).splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        k, v = k.strip(), v.strip()
        if v.startswith("[") and v.endswith("]"):
            v = ",".join(x.strip().strip("'\"") for x in v[1:-1].split(",") if x.strip())
        elif re.fullmatch(r"-?\d+", v):
            v = int(v)
        else:
            v = v.strip("'\"")
        meta["doc_id" if k == "id" else k] = v
    return meta, m.group(2).strip()


def load_markdown_dir(folder: Path, default_type: str):
    docs = []
    for path in sorted(folder.rglob("*")):
        if path.suffix.lower() not in (".md", ".txt"):
            continue
        meta, body = parse_front_matter(path.read_text(encoding="utf-8"))
        meta.setdefault("type", default_type)
        meta["source"] = path.relative_to(folder.parent).as_posix()
        header = " | ".join(str(meta[k]).replace("_", " ")
                            for k in ("type", "tower", "incident_type", "date") if k in meta)
        if len(body.split()) > MAX_WORDS:
            parts = [p for p in re.split(r"\n(?=## )", body) if p.strip()]
        else:
            parts = [body]
        for i, part in enumerate(parts):
            base = str(meta.get("doc_id", path.stem))
            docs.append({
                "id": f"{base}:{i}",
                "text": f"{header}\n{part}" if header else part,
                "metadata": {**meta, "part": i},
            })
    return docs


def load_logs(specs, default_date, iface_map, window=15, max_lines=40, events_out=None):
    docs = []
    for spec in specs:
        path_str, _, d = spec.partition("@")
        d = d or default_date
        year = date.fromisoformat(d).year if d else datetime.now().year
        path = Path(path_str)
        events, bad = parse_log(path.read_text(encoding="utf-8").splitlines(), year, iface_map)
        if bad:
            print(f"warning: {path.name}: {len(bad)} unparsable lines skipped", file=sys.stderr)
        docs.extend(chunk_events(events, path.name, window, max_lines))
        if events_out is not None:
            events_out.extend((path.name, e) for e in events)
    return docs


# --------------------------------------------------------------------------
# Chroma helpers
# --------------------------------------------------------------------------
def write_events_db(path, rows):
    """Every parsed log line as a row, so counts come from SQL and not from an LLM."""
    con = sqlite3.connect(path)
    con.execute("DROP TABLE IF EXISTS events")
    con.execute("""CREATE TABLE events (date TEXT, ts TEXT, host TEXT, tower TEXT, etype TEXT,
                   customer TEXT, user TEXT, ip TEXT, iface TEXT, mac TEXT, signal INTEGER,
                   source TEXT, line_no INTEGER, raw TEXT)""")
    con.executemany(
        "INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [(e.ts.strftime("%Y-%m-%d"), e.ts.strftime("%Y-%m-%d %H:%M:%S"), e.host, e.tower, e.etype,
          e.customer, e.user, e.ip, e.iface, e.mac, e.signal, src, e.line_no, e.raw)
         for src, e in rows])
    con.execute("CREATE INDEX idx_events ON events (date, etype, tower)")
    con.commit()
    con.close()


def get_client(db: str):
    try:
        import chromadb
    except ImportError:
        sys.exit("run: pip install chromadb")
    return chromadb.PersistentClient(path=db)


def build_where(args):
    conds = [{k: v} for k, v in (("tower", getattr(args, "tower", None)),
                                 ("type", getattr(args, "type", None)),
                                 ("incident_type", getattr(args, "incident_type", None)),
                                 ("date", getattr(args, "date", None))) if v]
    day, t_from, t_to = (getattr(args, "date", None), getattr(args, "time_from", None),
                         getattr(args, "time_to", None))
    if day and (t_from or t_to):
        d = date.fromisoformat(day)

        def epoch(hm):
            h, m = (int(x) for x in hm.split(":"))
            return int((datetime(d.year, d.month, d.day, h, m) - datetime(1970, 1, 1)).total_seconds())

        if t_to:
            conds.append({"start_ts": {"$lte": epoch(t_to)}})
        if t_from:
            conds.append({"end_ts": {"$gte": epoch(t_from)}})
    elif t_from or t_to:
        sys.exit("--from and --to need --date")
    if not conds:
        return None
    return conds[0] if len(conds) == 1 else {"$and": conds}


STOP = set("a an and are as at be by do does for from how i in is it of on or the to was what when "
           "which who why with my me did go".split())


def _tokens(text):
    toks = re.findall(r"[a-z0-9][a-z0-9._:\-]*", text.lower())
    parts = [p for t in toks for p in re.split(r"[._:\-]", t) if p] if toks else []
    return [t for t in toks + parts if t not in STOP]


def bm25_scores(query, docs, k1=1.5, b=0.75):
    toks = [_tokens(d) for d in docs]
    n = len(docs)
    avg = (sum(len(t) for t in toks) / n) or 1.0
    df = Counter()
    for t in toks:
        df.update(set(t))
    q = set(_tokens(query))
    scores = []
    for t in toks:
        tf, s = Counter(t), 0.0
        for term in q:
            if term in tf:
                idf = math.log(1 + (n - df[term] + 0.5) / (df[term] + 0.5))
                s += idf * tf[term] * (k1 + 1) / (tf[term] + k1 * (1 - b + b * len(t) / avg))
        scores.append(s)
    return scores


def run_query(coll, embedder, question, k, where=None, mode="hybrid"):
    """Vector search, or vector + keyword (BM25) search fused by rank."""
    qemb = embedder.queries([question])
    n_vec = k if mode == "vector" else max(k * 4, 20)
    res = coll.query(query_embeddings=qemb, n_results=n_vec, where=where)
    vec = list(zip(res["ids"][0], res["distances"][0], res["metadatas"][0], res["documents"][0]))
    if mode == "vector":
        return vec[:k]
    allc = coll.get(where=where, include=["documents", "metadatas"])
    ids, docs, metas = allc["ids"], allc["documents"], allc["metadatas"]
    if not ids:
        return []
    sc = bm25_scores(question, docs)
    order = [i for i in sorted(range(len(ids)), key=lambda i: -sc[i]) if sc[i] > 0][:n_vec]
    vrank = {h[0]: r for r, h in enumerate(vec)}
    krank = {ids[i]: r for r, i in enumerate(order)}
    fused = {c: (1 / (60 + vrank[c]) if c in vrank else 0.0) + (1 / (60 + krank[c]) if c in krank else 0.0)
             for c in set(vrank) | set(krank)}
    top = sorted(fused, key=lambda c: -fused[c])[:k]
    info = {ids[i]: (metas[i], docs[i]) for i in range(len(ids))}
    dist = {h[0]: h[1] for h in vec}
    missing = [c for c in top if c not in dist]
    if missing:
        got = coll.get(ids=missing, include=["embeddings"])
        for cid, emb in zip(got["ids"], got["embeddings"]):
            dist[cid] = 1.0 - float(sum(a * b for a, b in zip(qemb[0], emb)))
    return [(c, dist[c], info[c][0], info[c][1]) for c in top]


def open_collection(args):
    client = get_client(args.db)
    try:
        coll = client.get_collection(COLLECTION)
    except Exception:
        sys.exit(f"no index found in {args.db!r}. Run the ingest command first.")
    model = (coll.metadata or {}).get("model", "bge-small")
    if getattr(args, "model", None) and args.model != model:
        print(f"note: index was built with {model!r}, using that for queries", file=sys.stderr)
    return coll, Embedder(model)


# --------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------
def cmd_ingest(args):
    iface_map = dict(p.split("=", 1) for p in args.iface_map.split(",") if "=" in p)
    docs = []
    event_rows = []
    if args.log:
        found = load_logs(args.log, args.date, iface_map, args.window, args.max_lines, event_rows)
        print(f"log: {len(found)} chunks", flush=True)
        docs += found
    if args.notes:
        found = load_markdown_dir(Path(args.notes), "incident")
        print(f"notes: {len(found)} chunks from {args.notes}", flush=True)
        docs += found
    if args.playbooks:
        found = load_markdown_dir(Path(args.playbooks), "playbook")
        print(f"playbooks: {len(found)} chunks from {args.playbooks}", flush=True)
        docs += found
    if not docs:
        sys.exit("nothing to ingest. Use --log, --notes or --playbooks "
                 "(check the folder names and that files end in .md or .txt).")
    ids = [d["id"] for d in docs]
    if len(set(ids)) != len(ids):
        dup = sorted({i for i in ids if ids.count(i) > 1})[:5]
        sys.exit(f"duplicate chunk ids, fix the source files: {dup}")

    if event_rows:
        write_events_db(args.events_db, event_rows)
        print(f"events database: {len(event_rows)} rows in {args.events_db}", flush=True)
    print(f"loading embedding model {args.model!r} (first run can be slow)...", flush=True)
    embedder = Embedder(args.model)
    print("opening the vector store...", flush=True)
    client = get_client(args.db)
    try:
        client.delete_collection(COLLECTION)
    except Exception:
        pass
    coll = client.create_collection(
        COLLECTION, metadata={"hnsw:space": "cosine", "model": args.model},
        embedding_function=None)
    texts = [d["text"] for d in docs]
    metas = [d["metadata"] for d in docs]
    for i in range(0, len(docs), 64):
        sl = slice(i, i + 64)
        coll.add(ids=ids[sl], documents=texts[sl], metadatas=metas[sl],
                 embeddings=embedder.docs(texts[sl]))
        print(f"embedded {min(i + 64, len(docs))}/{len(docs)}", flush=True)
    by_type = {}
    for m in metas:
        by_type[m.get("type", "?")] = by_type.get(m.get("type", "?"), 0) + 1
    print(f"indexed {len(docs)} chunks with {args.model}: {by_type}")


def _print_hits(hits):
    if not hits:
        print("no results (check your filters)")
    for rank, (cid, dist, meta, doc) in enumerate(hits, 1):
        tag = ", ".join(f"{k}={meta[k]}" for k in ("type", "tower", "date", "incident_type")
                        if k in meta)
        snippet = doc.replace("\n", " ")[:170]
        print(f"{rank}. dist {dist:.3f}  {cid}\n   [{tag}]\n   {snippet}...\n")


def _known_dates(coll):
    return sorted({m["date"] for m in coll.get(include=["metadatas"])["metadatas"] if "date" in m})


def cmd_search(args):
    coll, embedder = open_collection(args)
    if not args.auto:
        _print_hits(run_query(coll, embedder, args.question, args.k, build_where(args), args.mode))
        return
    f, notes = extract_filters(args.question, _known_dates(coll))
    print("filters read from the question:", f or "none", "|", "; ".join(notes) or "no notes", "\n")
    days = f.get("dates") or [f.get("date") or args.date]
    for day in days:
        ns = argparse.Namespace(
            tower=f.get("tower") or args.tower, type=args.type,
            incident_type=args.incident_type, date=day,
            time_from=f.get("time_from") or args.time_from,
            time_to=f.get("time_to") or args.time_to)
        if len(days) > 1:
            print(f"--- {day}")
        if (ns.time_from or ns.time_to) and not ns.date:
            ns.time_from = ns.time_to = None
            print("(time of day ignored: no date in the question)\n")
        _print_hits(run_query(coll, embedder, args.question, args.k, build_where(ns), args.mode))


def cmd_make_tests(args):
    key = json.loads(Path(args.key).read_text(encoding="utf-8"))
    tests = []
    for q in key.get("test_questions", []):
        ans = str(q.get("answer", ""))
        answerable = not UNANSWERABLE_RE.search(ans.lower())
        evidence = sorted(set(re.findall(r"\d{2}:\d{2}:\d{2}", ans)
                              + re.findall(r"cust-[A-Za-z]\d+", ans))) if answerable else []
        tests.append({"question": q.get("question", ""), "answerable": answerable,
                      "match": "any", "evidence": evidence, "filters": {}})
    Path(args.out).write_text(json.dumps(tests, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {len(tests)} tests to {args.out}")
    print("Edit them: 'evidence' are strings that must appear in a retrieved chunk's id or text "
          "(a note id such as N-2026-0914-01 works). Use match=all when every string must be found.")


def cmd_eval(args):
    coll, embedder = open_collection(args)
    tests = json.loads(Path(args.tests).read_text(encoding="utf-8"))
    known = _known_dates(coll) if args.auto_filters else []
    agree = []
    ans_best, unans_best, ranks = [], [], []
    print(f"{'#':>2} {'ans':<4} {'rank':<5} {'best':>6}  question")
    for n, t in enumerate(tests, 1):
        filters = {} if args.no_filters else t.get("filters", {})
        if args.auto_filters:
            auto, _ = extract_filters(t["question"], known)
            auto.pop("dates", None)
            if "date" not in auto:
                auto.pop("time_from", None)
                auto.pop("time_to", None)
            hand = t.get("filters", {})
            agree.append(all(hand[k] == auto.get(k) for k in ("tower", "date") if k in hand))
            filters = auto
        where = build_where(argparse.Namespace(**{k: filters.get(k)
                                                  for k in ("tower", "type", "incident_type", "date",
                                                                  "time_from", "time_to")}))
        hits = run_query(coll, embedder, t["question"], args.k, where, args.mode)
        best = hits[0][1] if hits else 1.0
        texts = [(h[0] + "\n" + h[3]).lower() for h in hits]  # id + text
        rank = None
        if t.get("answerable", True) and t.get("evidence"):
            found = []
            for ev in t["evidence"]:
                r = next((i for i, tx in enumerate(texts, 1) if ev.lower() in tx), None)
                found.append(r)
            if t.get("match", "all") == "any":
                got = [r for r in found if r]
                rank = min(got) if got else None
            else:
                rank = max(found) if all(found) else None
            ranks.append(rank)
        (ans_best if t.get("answerable", True) else unans_best).append(best)
        shown = "-" if not t.get("answerable", True) else (str(rank) if rank else "MISS")
        print(f"{n:>2} {'yes' if t.get('answerable', True) else 'no':<4} {shown:<5} "
              f"{best:>6.3f}  {t['question'][:60]}")
    if agree:
        print(f"\nfilters read from the questions match the hand-written tower/date "
              f"in {sum(agree)}/{len(agree)} tests")
    scored = len(ranks)
    if scored:
        print()
        for n in (1, 3, 5):
            if n <= args.k:
                ok = sum(1 for r in ranks if r and r <= n)
                print(f"hit@{n}: {ok}/{scored}")
    if ans_best and unans_best:
        hi, lo = max(ans_best), min(unans_best)
        print(f"\nbest distance, answerable: median {statistics.median(ans_best):.3f}, "
              f"max {hi:.3f}")
        print(f"best distance, unanswerable: min {lo:.3f}")
        if hi < lo:
            print(f"a distance cutoff around {(hi + lo) / 2:.3f} separates them on this data")
        else:
            print("the two overlap: a distance cutoff alone will not decide 'I don't know'")


def main(argv=None):
    p = argparse.ArgumentParser(description="retrieval-only RAG for WISP logs and notes")
    p.add_argument("--db", default=os.environ.get("WISP_DB", "chroma_db"), help="folder for the local index")
    sub = p.add_subparsers(dest="cmd", required=True)

    i = sub.add_parser("ingest", help="(re)build the index")
    i.add_argument("--log", action="append", help="FILE or FILE@YYYY-MM-DD, repeatable")
    i.add_argument("--date", help="default log date, YYYY-MM-DD")
    i.add_argument("--iface-map", default="", help="only if your log has link up/down lines, "
                   "e.g. ether2=A,ether3=B")
    i.add_argument("--window", type=int, default=15, help="minutes per log chunk window")
    i.add_argument("--max-lines", type=int, default=40, help="max log lines per chunk")
    i.add_argument("--notes", help="folder of incident notes (.md)")
    i.add_argument("--playbooks", help="folder of playbooks (.md)")
    i.add_argument("--events-db", default=os.environ.get("WISP_EVENTS_DB", "events.db"),
                   help="SQLite file for exact counts")
    i.add_argument("--model", default="bge-small", choices=list(MODELS))

    s = sub.add_parser("search", help="show the top chunks for a question")
    s.add_argument("question")
    s.add_argument("-k", type=int, default=5)
    s.add_argument("--tower")
    s.add_argument("--type", help="log, incident or playbook")
    s.add_argument("--incident-type")
    s.add_argument("--date", help="only chunks from this day, YYYY-MM-DD")
    s.add_argument("--from", dest="time_from", help="log chunks ending after HH:MM (needs --date)")
    s.add_argument("--to", dest="time_to", help="log chunks starting before HH:MM (needs --date)")
    s.add_argument("--mode", choices=["hybrid", "vector"], default="hybrid",
                   help="hybrid = meaning + keywords (default)")
    s.add_argument("--auto", action="store_true",
                   help="read tower, date and time of day from the question itself")

    m = sub.add_parser("make-tests", help="draft retrieval tests from the answer key")
    m.add_argument("--key", required=True)
    m.add_argument("--out", default="retrieval_tests.json")

    e = sub.add_parser("eval", help="score retrieval on the tests")
    e.add_argument("--tests", default="retrieval_tests.json")
    e.add_argument("-k", type=int, default=5)
    e.add_argument("--mode", choices=["hybrid", "vector"], default="hybrid")
    e.add_argument("--no-filters", action="store_true",
                   help="ignore the filters in the tests, to see how much they help")
    e.add_argument("--auto-filters", action="store_true",
                   help="read the filters from each question with wisp_query.py "
                        "instead of using the ones written in the tests")

    args = p.parse_args(argv)
    {"ingest": cmd_ingest, "search": cmd_search,
     "make-tests": cmd_make_tests, "eval": cmd_eval}[args.cmd](args)


if __name__ == "__main__":
    main()