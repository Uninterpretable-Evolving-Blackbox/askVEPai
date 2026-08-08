#!/usr/bin/env python3
"""Fetch real VEP questions from Ensembl's issue trackers, verbatim and reproducibly.

WHY THIS EXISTS. The previous set of twenty "real" questions was transcribed by hand. Checking all nine
items it flagged `verbatim` against their source issues found none of them was: similarity to the real
body ranged from 0.03 to 0.98, none was even a substring, and five had VEP command lines stripped out —
up to twenty-four flags in one case. The edits were directional. Removing a command line that names
`--overlaps`, `--numbers`, `--protein` makes a question look *more* under-specified than the user's
actual question was, which is the direction that flatters the conclusion the set was used to support.

So nothing here is retyped. Each record stores the body exactly as the API returned it, a SHA-256 of
that text, and the time it was fetched. Re-running `--verify` re-fetches and compares hashes, so a later
edit — by hand, by a model, by anything — is detectable rather than invisible.

SELECTION IS A SCRIPT, NOT A JUDGEMENT. "Selected on topicality" cannot be audited. This draws a seeded
random sample from a stated frame and records every item it drew, including the ones later ruled out of
scope, so the exclusion rate is a reported number and the exclusions can be read.

  python work/harness/fetch_real_queries.py --repair       # re-fetch the 9 known issues, verbatim
  python work/harness/fetch_real_queries.py --sample 60    # seeded random draw from the frame
  python work/harness/fetch_real_queries.py --verify       # re-fetch and compare hashes
"""
import argparse
import hashlib
import json
import random
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "work" / "preliminary_examples" / "real_queries_fetched.json"

# The sampling frame, stated so it can be argued with: user-opened issues on Ensembl's two VEP
# repositories. Pull requests are excluded by the API filter, not by us.
FRAME = [("Ensembl/ensembl-vep", 1264), ("Ensembl/VEP_plugins", 236)]

# The nine the old set claimed were verbatim. Re-fetched so the repair is exact rather than a re-edit.
KNOWN = [("Ensembl/ensembl-vep", n) for n in (1834, 1929, 685, 1980, 1638, 1595, 1769, 1889)] + \
        [("Ensembl/VEP_plugins", 694)]


def gh(path, jq="."):
    r = subprocess.run(["gh", "api", path, "--jq", jq], capture_output=True, text=True)
    if r.returncode:
        return None
    return r.stdout.strip()


def fetch_issue(repo, number):
    raw = gh(f"repos/{repo}/issues/{number}",
             '{number:.number, title:.title, body:.body, user:.user.login, '
             'created_at:.created_at, state:.state, labels:[.labels[].name], '
             'is_pr:(has("pull_request")), url:.html_url}')
    if not raw:
        return None
    d = json.loads(raw)
    body = d.get("body") or ""
    return {
        "repo": repo, "number": d["number"], "url": d["url"], "title": d["title"],
        "author": d["user"], "created_at": d["created_at"], "state": d["state"],
        "labels": d["labels"], "is_pull_request": d["is_pr"],
        # The body EXACTLY as returned. Nothing is stripped, reflowed or reworded here or anywhere.
        "body": body,
        "body_sha256": hashlib.sha256(body.encode()).hexdigest(),
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def load():
    return json.load(open(OUT)) if OUT.exists() else []


def save(items):
    OUT.parent.mkdir(parents=True, exist_ok=True)
    json.dump(items, open(OUT, "w"), indent=1)
    print(f"  wrote {len(items)} records -> {OUT.relative_to(ROOT)}")


def cmd_repair():
    print(f"Re-fetching the {len(KNOWN)} issues the previous set claimed as verbatim.")
    items, seen = load(), {(i["repo"], i["number"]) for i in load()}
    for repo, n in KNOWN:
        if (repo, n) in seen:
            continue
        it = fetch_issue(repo, n)
        if it:
            it["origin"] = "repair-of-hand-curated-set"
            items.append(it)
            print(f"  {repo}#{n}  {len(it['body']):5d} chars  {it['body_sha256'][:12]}")
        time.sleep(0.2)
    save(items)


def cmd_sample(n, seed):
    """Seeded random draw. Every drawn number is recorded, including ones that turn out to be PRs or
    empty, so the frame is reconstructable and the losses are visible rather than quietly skipped."""
    rng = random.Random(seed)
    draws = []
    for repo, hi in FRAME:
        k = max(1, round(n * hi / sum(h for _, h in FRAME)))
        draws += [(repo, rng.randint(1, hi)) for _ in range(k)]
    print(f"Seeded draw (seed={seed}): {len(draws)} issue numbers from {len(FRAME)} repositories.")
    items, seen = load(), {(i["repo"], i["number"]) for i in load()}
    drawn_log, ok = [], 0
    for repo, num in draws:
        if (repo, num) in seen:
            drawn_log.append({"repo": repo, "number": num, "outcome": "already held"})
            continue
        it = fetch_issue(repo, num)
        if it is None:
            drawn_log.append({"repo": repo, "number": num, "outcome": "not found / deleted"})
        elif it["is_pull_request"]:
            drawn_log.append({"repo": repo, "number": num, "outcome": "pull request"})
        elif len((it["body"] or "").strip()) < 40:
            drawn_log.append({"repo": repo, "number": num, "outcome": "body too short to be a question"})
        else:
            it["origin"] = f"random-sample seed={seed}"
            items.append(it)
            drawn_log.append({"repo": repo, "number": num, "outcome": "kept"})
            ok += 1
        time.sleep(0.2)
    save(items)
    json.dump(drawn_log, open(OUT.with_name("real_queries_draw_log.json"), "w"), indent=1)
    from collections import Counter
    print(f"  kept {ok}/{len(draws)}: {dict(Counter(d['outcome'] for d in drawn_log))}")
    print(f"  draw log -> {OUT.with_name('real_queries_draw_log.json').relative_to(ROOT)}")


def cmd_verify():
    items = load()
    if not items:
        print("nothing stored yet")
        return
    bad = []
    for it in items:
        fresh = fetch_issue(it["repo"], it["number"])
        if fresh is None:
            bad.append((it["number"], "could not re-fetch"))
        elif fresh["body_sha256"] != it["body_sha256"]:
            bad.append((it["number"], "body changed upstream or was edited locally"))
        time.sleep(0.15)
    print(f"  verified {len(items)} records; {len(bad)} mismatched")
    for n, why in bad:
        print(f"    #{n}: {why}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--repair", action="store_true")
    ap.add_argument("--sample", type=int, default=0)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--verify", action="store_true")
    a = ap.parse_args()
    if a.repair:
        cmd_repair()
    if a.sample:
        cmd_sample(a.sample, a.seed)
    if a.verify:
        cmd_verify()
    if not (a.repair or a.sample or a.verify):
        ap.print_help()
