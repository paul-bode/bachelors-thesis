import json
import os
import time
import random
import requests
from pathlib import Path
from datetime import datetime

# CONFIG
# ====================
QUERY_BASE = "qt language:cpp mirror:false template:false archived:false"
START_DATE = datetime(2008, 2, 1)
END_DATE   = datetime(2026, 5, 31)
MIN_INTERVAL_DAYS = 1
MAX_RETRIEVABLE = 980
STATE_FILE = "analysis/state.json"
POTENTIAL_QT_PROJECTS = "analysis/potential_qt_projects.jsonl"
GRAPHQL_URL = "https://api.github.com/graphql"

# CREDENTIALS
# ====================
def load_github_token() -> str:
    """Load github token from the same directory the script is in."""

    env_path = Path(__file__).parent / ".env"
    for line in env_path.read_text().splitlines():
        if line.startswith("GITHUB_TOKEN="):
            return line.split("=", 1)[1].strip()
    raise ValueError("[ERROR] GITHUB_TOKEN not found in .env")

TOKEN = load_github_token()
SESSION = requests.Session()
SESSION.headers.update({
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
})

# TIME FORMATTING
# ====================
def serialize_dt(dt: datetime) -> str:
    return dt.isoformat()

def deserialize_dt(s: str) -> datetime:
    return datetime.fromisoformat(s)

# GRAPHQL HELPERS
# ====================
def graphql(query: str) -> dict:
    """Execute a GraphQL query, raising on HTTP or API-level errors."""

    try:
        resp = SESSION.post(GRAPHQL_URL, json={"query": query}, timeout=30)
        resp.raise_for_status()
    except requests.exceptions.Timeout:
        raise RuntimeError("[ERROR] Request timed out")
    except requests.exceptions.HTTPError as e:
        raise RuntimeError(f"[ERROR] HTTP error: {e.response.status_code} {e.response.text}")
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"[ERROR] Request failed: {e}")

    data = resp.json()
    if "errors" in data:
        raise RuntimeError(f"[ERROR] GraphQL errors: {data['errors']}")

    return data

def check_rate_limit() -> dict:
    """Query github for the current rate limit"""

    data = graphql("""
    {
      rateLimit {
        limit
        remaining
        resetAt
        used
      }
    }
    """)
    return data["data"]["rateLimit"]

def run_count_query(query: str) -> int:
    """Get the total repository count for a search query."""
    gql = f"""
    {{
      search(query: "{query}", type: REPOSITORY) {{
        repositoryCount
      }}
    }}
    """
    data = graphql(gql)
    return data["data"]["search"]["repositoryCount"]

def make_query(start: datetime, end: datetime) -> str:
    return f'{QUERY_BASE} created:{start:%Y-%m-%d}..{end:%Y-%m-%d}'

def split_interval(start: datetime, end: datetime) -> tuple:
    mid = start + (end - start) * 0.5
    return start, mid, mid, end

# STATE MANAGEMENT
# ====================
def load_state() -> dict:
    if Path(STATE_FILE).exists():
        with open(STATE_FILE) as f:
            raw = json.load(f)

        return {
            "queue": [
                (deserialize_dt(start), deserialize_dt(end), retry)
                for start, end, retry in raw["queue"]
            ],
        }

    return {"queue": []}

def save_state(state: dict) -> None:
    clean = {
        "queue": [
            (serialize_dt(start), serialize_dt(end), retry)
            for start, end, retry in state["queue"]
        ],
    }

    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(clean, f, indent=2)

    os.replace(tmp, STATE_FILE)

def seed_state(state: dict) -> None:
    """Populate the queue with 1-year chunks on a fresh start."""

    if state["queue"]:
        print(f"Resuming with {len(state['queue'])} intervals remaining.")
        return

    print("Fresh start - seeding queue.")
    current = START_DATE
    while current < END_DATE:
        next_year = datetime(current.year + 1, 1, 1)
        state["queue"].append((current, min(next_year, END_DATE), 0))
        current = next_year

# OUTPUT
# ====================
def append_results(nodes: list) -> None:
    if not nodes:
        return

    with open(POTENTIAL_QT_PROJECTS, "a") as f:
        for node in nodes:
            if node:
                f.write(json.dumps(node) + "\n")
            else:
                print("[WARN] Null node skipped")

def deduplicate_output(filepath: str = POTENTIAL_QT_PROJECTS) -> None:
    path = Path(filepath)
    if not path.exists():
        print(f"[ERROR] File not found: {filepath}")
        return

    seen = set()
    kept = []

    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            repo = json.loads(line)
            key = repo.get("nameWithOwner")
            if key and key not in seen:
                seen.add(key)
                kept.append(line)

    duplicates = 0
    with open(path) as f:
        total = sum(1 for line in f if line.strip())
    duplicates = total - len(kept)

    tmp = filepath + ".tmp"
    with open(tmp, "w") as f:
        for line in kept:
            f.write(line + "\n")
    os.replace(tmp, filepath)

    print(f"Total before: {total}")
    print(f"Duplicates removed: {duplicates}")
    print(f"Final project count: {len(kept)}")

# GITHUB GRAPHQL SEARCH
# ====================
def run_search(query: str, cursor: str | None = None) -> dict:
    after = f', after: "{cursor}"' if cursor else ""

    gql = f"""
    {{
      search(query: "{query}", type: REPOSITORY, first: 10{after}) {{
        pageInfo {{
          hasNextPage
          endCursor
        }}
        nodes {{
          ... on Repository {{
            nameWithOwner
            url
            stargazerCount
            forkCount
            createdAt
            watchers {{ totalCount }}
          }}
        }}
      }}
    }}
    """

    data = graphql(gql)
    search = data.get("data", {}).get("search")
    if not search:
        raise RuntimeError("[ERROR] Empty search payload in response")

    return search

# CORE PROCESSOR
# ====================
def process_interval(state: dict, start: datetime, end: datetime, retry: int = 0) -> None:
    query = make_query(start, end)
    interval_days = (end - start).days
    print(f"Checking interval: {start.date()} -> {end.date()}")

    try:
        count = run_count_query(query)
        print(f"  Query size: {count}")

        if count > MAX_RETRIEVABLE and interval_days > MIN_INTERVAL_DAYS:
            print("  [WARN] Split (count-driven)")
            s1, m1, m2, e2 = split_interval(start, end)
            state["queue"].insert(0, (m2, e2, 0))
            state["queue"].insert(0, (s1, m1, 0))
            return
        
        result = run_search(query)
        append_results(result["nodes"])
        save_state(state)

        while result["pageInfo"]["hasNextPage"]:
            cursor = result["pageInfo"]["endCursor"]
            time.sleep(0.15 + random.uniform(0, 0.25))

            result = run_search(query, cursor)
            append_results(result["nodes"])
            save_state(state)

    except Exception as e:
        print(f"Error: {e}")

        if interval_days > MIN_INTERVAL_DAYS:
            print("  [WARN] Split (failure-driven)")
            s1, m1, m2, e2 = split_interval(start, end)
            state["queue"].insert(0, (m2, e2, 0))
            state["queue"].insert(0, (s1, m1, 0))
            return

        if retry < 5:
            backoff = 2 ** retry
            print(f"  [WARN] Retrying in {backoff}s... (attempt {retry + 1}/5)")
            time.sleep(backoff)
            state["queue"].insert(0, (start, end, retry + 1))
        else:
            print(f"  [ERROR] Giving up on interval: {start.date()} -> {end.date()}")

# MAIN LOOP
# ====================
def main():
    Path('analysis').mkdir(parents=True, exist_ok=True)
    state = load_state()
    seed_state(state)
    save_state(state)

    repos_count = run_count_query(QUERY_BASE)
    print("Total number of projects found:", repos_count)

    rl = check_rate_limit()
    print("Rate limit:", rl)

    while state["queue"]:
        start, end, retry = state["queue"].pop(0)
        process_interval(state, start, end, retry)
        save_state(state)

        if random.random() < 0.025:
            rl = check_rate_limit()
            print("Rate limit:", rl)

    print("Done.")
    deduplicate_output()

if __name__ == "__main__":
    main()
