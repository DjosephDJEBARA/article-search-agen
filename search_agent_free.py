"""
Hourly literature search agent — 100% FREE VERSION.

No paid API used anywhere. Only:
- Semantic Scholar API (free, no key needed) for searching papers
- GitHub Actions (free) for running this every hour
- A keyword-based scoring system (no AI) to rank how well each paper
  matches your criteria

What it does, each time it runs:
1. Queries Semantic Scholar with several search queries relevant to the
   target composite material configuration.
2. Skips papers already seen in previous runs (tracked in seen_papers.json).
3. Scores each NEW paper's title + abstract against a list of
   "positive" keywords (things that should be present) and "negative"
   keywords (things that disqualify a match, e.g. the opposite stiffness
   configuration).
4. Appends papers above a score threshold to results.md, so you have a
   running log to check whenever you like.

This is less precise than an AI-based evaluation (it can't understand
nuance the way a language model reading the full abstract can), but it
costs nothing to run, indefinitely.
"""

import os
import json
import time
from datetime import datetime, timezone

import requests

# ---------------------------------------------------------------------------
# 1. CONFIGURE YOUR SEARCH HERE
# ---------------------------------------------------------------------------

QUERIES = [
    "three-phase composite bimodal spherical inclusions rigid matrix",
    "representative volume element two soft inclusion populations Hashin-Shtrikman",
    "ductile particle ceramic matrix composite porosity finite element RVE",
    "rigid matrix soft spherical inclusions bulk shear modulus Mori-Tanaka",
    "three-phase composite random spherical inclusions bulk shear modulus 3D",
]

# Words/phrases that should appear if the paper is a good match.
# Each hit adds +1 to the paper's score (case-insensitive).
POSITIVE_KEYWORDS = [
    "three-phase", "3-phase", "three phase",
    "representative volume element", "rve",
    "spherical inclusion", "spherical particle",
    "bulk modulus", "shear modulus",
    "hashin-shtrikman", "hashin shtrikman",
    "mori-tanaka", "mori tanaka",
    "soft inclusion", "compliant inclusion", "soft particle",
    "ductile particle", "porosity", "void",
    "finite element", "homogenization", "homogenisation",
    "random distribution", "volume fraction",
]

# Words/phrases that suggest the OPPOSITE configuration (stiff filler in a
# soft matrix) — each hit SUBTRACTS 2 points, since this is what we want
# to exclude.
NEGATIVE_KEYWORDS = [
    "stiff filler", "hard particle", "hard inclusion", "rigid filler",
    "rigid inclusion", "reinforcing filler", "stiffening",
]

# Minimum score for a paper to be reported. Tune this up/down depending on
# how much noise vs. how many misses you're willing to accept.
SCORE_THRESHOLD = 4

# ---------------------------------------------------------------------------
# 2. FILES USED TO TRACK STATE BETWEEN RUNS (kept in the GitHub repo)
# ---------------------------------------------------------------------------

SEEN_FILE = "seen_papers.json"
RESULTS_FILE = "results.md"

SEMANTIC_SCHOLAR_URL = "https://api.semanticscholar.org/graph/v1/paper/search"


def search_papers(query: str, limit: int = 10) -> list:
    """Query Semantic Scholar for a single search string."""
    params = {
        "query": query,
        "fields": "title,abstract,year,url,venue,externalIds",
        "limit": limit,
    }
    try:
        r = requests.get(SEMANTIC_SCHOLAR_URL, params=params, timeout=30)
        r.raise_for_status()
        return r.json().get("data", [])
    except requests.RequestException as e:
        print(f"  [warning] search failed for query '{query}': {e}")
        return []


def load_seen() -> set:
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def save_seen(seen: set) -> None:
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(seen), f, indent=2)


def paper_key(paper: dict) -> str:
    """Stable identifier for a paper, preferring DOI, falling back to title."""
    doi = (paper.get("externalIds") or {}).get("DOI")
    return doi if doi else paper.get("title", "")


def score_paper(paper: dict) -> tuple:
    """Score a paper against the keyword lists. Returns (score, matched_terms)."""
    text = ((paper.get("title") or "") + " " + (paper.get("abstract") or "")).lower()

    matched = []
    score = 0

    for kw in POSITIVE_KEYWORDS:
        if kw in text:
            score += 1
            matched.append(f"+{kw}")

    for kw in NEGATIVE_KEYWORDS:
        if kw in text:
            score -= 2
            matched.append(f"-{kw}")

    return score, matched


def append_results(entries: list) -> None:
    if not entries:
        return
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    with open(RESULTS_FILE, "a", encoding="utf-8") as f:
        f.write(f"\n\n## Run: {timestamp}\n\n")
        for e in entries:
            f.write(f"### {e['title']} ({e.get('year', 'n.d.')}) — score: {e['score']}\n")
            if e.get("url"):
                f.write(f"{e['url']}\n\n")
            f.write(f"Matched terms: {', '.join(e['matched'])}\n\n")
            if e.get("abstract"):
                snippet = e["abstract"][:400]
                f.write(f"> {snippet}...\n")


def main():
    seen = load_seen()
    candidates = []
    total_checked = 0

    for query in QUERIES:
        print(f"Searching: {query}")
        papers = search_papers(query)
        time.sleep(1)  # be polite to the free API

        for paper in papers:
            key = paper_key(paper)
            if not key or key in seen:
                continue
            seen.add(key)
            total_checked += 1

            score, matched = score_paper(paper)
            print(f"  - {paper.get('title', '')[:70]}... -> score {score}")

            if score >= SCORE_THRESHOLD:
                candidates.append({
                    "title": paper.get("title", ""),
                    "year": paper.get("year", ""),
                    "url": paper.get("url", ""),
                    "abstract": paper.get("abstract", ""),
                    "score": score,
                    "matched": matched,
                })

    # Show the best matches first
    candidates.sort(key=lambda e: e["score"], reverse=True)

    save_seen(seen)
    append_results(candidates)

    print(f"\nDone. Checked {total_checked} new papers this run, "
          f"found {len(candidates)} above the score threshold ({SCORE_THRESHOLD}).")


if __name__ == "__main__":
    main()
