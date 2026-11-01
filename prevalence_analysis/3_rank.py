import json
import math
from pathlib import Path

# CONFIG
# ====================
QDATASTREAM_PROJECTS = Path("analysis/qdatastream_projects.jsonl")
RANKED_QDATASTREAM_PROJECTS = Path("analysis/ranked_qdatastream_projects.jsonl")
WEIGHT_STARS = 0.5
WEIGHT_FORKS = 0.35
WEIGHT_WATCHERS = 0.15
RHO = 0.3
NOW = 2026

# SCORING FUNCTION
# ====================
def compute_score(project: dict) -> float:
    stars = project.get("stargazerCount", 0)
    forks = project.get("forkCount", 0)
    watchers = project.get("watchers", {}).get("totalCount", 0)
    created_at = project.get("createdAt", str(NOW))
    year_of_creation = int(created_at[:4])

    popularity = WEIGHT_STARS * stars + WEIGHT_FORKS * forks + WEIGHT_WATCHERS * watchers

    z_t = math.exp(-RHO * (NOW - year_of_creation))
    popularity_normalized = z_t * popularity

    return popularity_normalized

# MAIN
# ====================
def main():

    projects = []
    with open(QDATASTREAM_PROJECTS, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            projects.append(json.loads(line))

    for project in projects:
        project["score"] = compute_score(project)

    projects.sort(key=lambda x: x["score"], reverse=True)

    with open(RANKED_QDATASTREAM_PROJECTS, "w", encoding="utf-8") as f:
        for project in projects:
            json.dump(project, f, ensure_ascii=False)
            f.write("\n")

    print(f"Processed {len(projects)} projects -> {RANKED_QDATASTREAM_PROJECTS}")

if __name__ == "__main__":
    main()
