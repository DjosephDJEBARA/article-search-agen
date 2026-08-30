"""
Hourly literature search agent.

What it does, each time it runs:
1. Queries the Semantic Scholar API (free, no key needed) with several
   search queries relevant to the target composite material configuration.
2. Skips papers already seen in previous runs (tracked in seen_papers.json).
3. Sends each NEW paper's title + abstract to Claude, asking whether it
   matches the detailed criteria (rigid matrix + two softer spherical
   inclusion populations, 3D RVE, K and G reported, HS bounds, etc.).
4. Appends any MATCH or PARTIAL result to results.md, with Claude's
   reasoning, so you have a running log you can check whenever you like.

Designed to be run automatically every hour by the GitHub Actions workflow
in .github/workflows/hourly_search.yml — but you can also just run it
manually with `python search_agent.py` to test it.
"""

import os
import json
import time
from datetime import datetime, timezone

import requests
import anthropic

# ---------------------------------------------------------------------------
# 1. CONFIGURE YOUR SEARCH HERE
# ---------------------------------------------------------------------------

# Add / remove / edit queries freely. Each one is sent separately to
# Semantic Scholar. Keep them short (a handful of keywords) — that's how
# academic search APIs work best.
QUERIES = [
    "three-phase composite bimodal spherical inclusions rigid matrix",
    "representative volume element two soft inclusion populations Hashin-Shtrikman",
    "ductile particle ceramic matrix composite porosity finite element RVE",
    "rigid matrix soft spherical inclusions bulk shear modulus Mori-Tanaka",
    "three-phase composite random spherical inclusions bulk shear modulus 3D",
]

# The detailed criteria Claude will check each paper against.
# This is the same logic as the research prompt built earlier in your
# conversation with Claude — edit freely if your criteria change.
EVALUATION_CRITERIA = """
I am looking for a peer-reviewed journal article that studies the elastic
behavior of a THREE-PHASE particulate composite with the following EXACT
characteristics.

REFERENCE STUDY TO MATCH IN METHODOLOGY: Shahzamanian, M.M. et al. (2022),
"Thermo-mechanical properties prediction of Ni-reinforced Al2O3 composites
using micro-mechanics based representative volume elements," Scientific
Reports, 12, 11076. That paper uses a 3D RVE (Dream.3D + Abaqus) with
randomly distributed spherical particles and spherical porosity, KUBC/PBC
boundary conditions, compared against Voigt/Reuss/Hashin/Mori-Tanaka/
SwiftComp/FFT, and validated against experimental data across several
volume fractions.

1. MATERIAL STRUCTURE (the key difference sought vs. the reference):
   - A continuous, rigid/stiff MATRIX phase
   - TWO DISTINCT populations of spherical inclusions, both SOFTER than
     the matrix: E(matrix) > E(inclusion population 1) > E(inclusion
     population 2). Population 2 may be voids/porosity or a second solid
     phase.

2. GEOMETRY: spherical inclusions, randomly distributed, genuine 3D RVE
   explicitly generated and meshed (not 2D, not purely analytical).
   Volume fractions of each phase explicitly reported.

3. METHOD: FE-based homogenization and/or analytical micromechanics
   (Mori-Tanaka, Hashin-Shtrikman bounds, differential scheme). Reports
   EFFECTIVE BULK MODULUS (K) and EFFECTIVE SHEAR MODULUS (G/mu)
   SEPARATELY, not just Young's modulus E.

4. IDEAL (not mandatory): experimental validation. Material identity does
   NOT matter (ceramic-metal, polymer-filler, concrete, nuclear fuel,
   etc.) — only the structural/stiffness/methodology profile matters.

EXCLUDE papers where the reinforcement/filler is STIFFER than the matrix
(the common "hard particle in soft matrix" case) — that is the opposite
configuration and must be rejected.
"""

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


def evaluate_with_claude(client: "anthropic.Anthropic", paper: dict) -> str:
    """Ask Claude whether this paper matches the criteria. Returns raw text."""
    abstract = paper.get("abstract") or "(no abstract available)"
    prompt = (
        EVALUATION_CRITERIA
        + "\n\n---\n\nCandidate paper to evaluate:\n\n"
        + f"Title: {paper.get('title', '')}\n"
        + f"Year: {paper.get('year', '')}\n"
        + f"Venue: {paper.get('venue', '')}\n"
        + f"Abstract: {abstract}\n\n"
        + "---\n\nRespond in this exact format:\n"
        + "VERDICT: <MATCH, PARTIAL, or NO>\n"
        + "REASON: <one or two sentences explaining which criteria are met "
        + "and which are not>"
    )
    response = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=250,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


def append_results(entries: list) -> None:
    if not entries:
        return
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    with open(RESULTS_FILE, "a", encoding="utf-8") as f:
        f.write(f"\n\n## Run: {timestamp}\n\n")
        for e in entries:
            f.write(f"### {e['title']} ({e.get('year', 'n.d.')})\n")
            if e.get("url"):
                f.write(f"{e['url']}\n\n")
            f.write(f"{e['evaluation']}\n")


def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit(
            "ANTHROPIC_API_KEY is not set. Add it as a GitHub Actions secret "
            "(see README) or export it locally before running this script."
        )
    client = anthropic.Anthropic(api_key=api_key)

    seen = load_seen()
    new_matches = []
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

            evaluation = evaluate_with_claude(client, paper)
            print(f"  - {paper.get('title', '')[:70]}... -> "
                  f"{evaluation.splitlines()[0]}")

            if evaluation.startswith("VERDICT: MATCH") or evaluation.startswith("VERDICT: PARTIAL"):
                new_matches.append({
                    "title": paper.get("title", ""),
                    "year": paper.get("year", ""),
                    "url": paper.get("url", ""),
                    "evaluation": evaluation,
                })

    save_seen(seen)
    append_results(new_matches)

    print(f"\nDone. Checked {total_checked} new papers this run, "
          f"found {len(new_matches)} match(es)/partial match(es).")


if __name__ == "__main__":
    main()
