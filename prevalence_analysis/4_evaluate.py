import json
from datetime import datetime, timezone
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.patches as mpatches
from matplotlib.ticker import FixedLocator
import numpy as np
from scipy import stats

# CONFIG
# ====================
POTENTIAL_QT_PROJECTS = "analysis/potential_qt_projects.jsonl"
VERIFIED_QT_PROJECTS = "analysis/verified_qt_projects.jsonl"
QDATASTREAM_PROJECTS = "analysis/qdatastream_projects.jsonl"
RANKED_QDATASTREAM_PROJECTS = "analysis/ranked_qdatastream_projects.jsonl"
PLOTS_DIR = Path("plots")

# LOAD JSONL SAFELY
# ====================
def load_jsonl(path: str):
    data = []
    
    p = Path(path)
    if not p.exists():
        return data
    
    with open(p, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                data.append(json.loads(line))
            except json.JSONDecodeError:
                print(f"[WARN] {path}: invalid JSON at line {i}")
    return data

# EVALUATION FUNCTIONS
# ====================
def top_10_projects(ranked_qdatastream_projects: list):
    """Show the 20 projects with the highest score."""

    top_10 = sorted(
        ranked_qdatastream_projects,
        key=lambda x: x.get("score", 0),
        reverse=True
    )[:10]

    print("\nTop 10 Projects:\n")

    for i, repo in enumerate(top_10, 1):
        name = repo.get("nameWithOwner", "unknown")
        score = repo.get("score", 0)

        print(f"{i}. {name}")
        print(f"   Score: {score:.5f}")
        print()

def plot_project_counts(potential_qt_projects: list, verified_qt_projects: list, qdatastream_projects: list):
    """Plot count of projects in every category."""

    labels = ["Potential Qt Projects", "Verified Qt Projects", "QDataStream Projects"]
    counts = [len(potential_qt_projects), len(verified_qt_projects), len(qdatastream_projects)]
    colors = ["#4c9be8", "#f5a623", "#7ed321"]
    fig, ax = plt.subplots(figsize=(7, 5))
    bars = ax.bar(labels, counts, color=colors, edgecolor="white", width=0.5)
    for bar, count in zip(bars, counts):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + max(counts) * 0.01,
            str(count),
            ha="center", va="bottom", fontweight="bold"
        )
    ax.set_ylabel("Number of Projects")
    ax.set_ylim(0, max(counts) * 1.15)
    plt.tight_layout()
    PLOTS_DIR.mkdir(exist_ok=True)
    out = PLOTS_DIR / "project_counts.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)

def plot_score_distribution(ranked_qdatastream_projects: list):
    """Plot score distribution of QDataStream Projects."""

    scores = [r.get("score", 0) for r in ranked_qdatastream_projects if "score" in r]
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(range(1, len(scores) + 1), scores, color="#4c9be8", linewidth=1)
    ax.set_xlabel("Number of Projects")
    ax.set_ylabel("Score")
    ax.set_yscale("log")
    ax.set_xlim(left=1)
    ax.set_ylim(bottom=0.01)
    ticks = [0.01,1,10,100,1000,10000]
    ax.yaxis.set_major_locator(FixedLocator(ticks))
    ax.yaxis.set_minor_locator(mticker.NullLocator()) 
    fmt = mticker.ScalarFormatter()
    fmt.set_scientific(False)        
    fmt.set_useMathText(False)
    ax.yaxis.set_major_formatter(fmt)
    plt.tight_layout()
    PLOTS_DIR.mkdir(exist_ok=True)
    out = PLOTS_DIR / "score_distribution.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)

def plot_age_distribution_comparison(verified_qt_projects: list, qdatastream_projects: list):
    """Age distribution comparision of verified Qt projects and QDataStream projects."""

    now = datetime.now(timezone.utc)
    qt_ages = []
    for r in verified_qt_projects:
        created = datetime.fromisoformat(r["createdAt"].replace("Z", "+00:00"))
        qt_ages.append((now - created).days / 365.25)
    qdatastream_ages = []
    for r in qdatastream_projects:
        created = datetime.fromisoformat(r["createdAt"].replace("Z", "+00:00"))
        qdatastream_ages.append((now - created).days / 365.25)

    bins = [x - 0.5 for x in range(0, 20)]
    PCT_COLOR = "#2ecc71"
    fig, ax = plt.subplots(figsize=(12, 6))

    qt_counts, _, qt_bars = ax.hist(qt_ages, bins=bins, color="C0", label="Verified Qt Projects", edgecolor="white")
    qs_counts, _, qs_bars = ax.hist(qdatastream_ages, bins=bins, color="C1", label="QDataStream Projects", edgecolor="white")

    for bar, count in zip(qt_bars, qt_counts):
        if count > 0:
            ax.text(
                bar.get_x() + bar.get_width() * 0.1,
                bar.get_height() + 5,
                str(int(count)),
                ha="left", va="bottom", fontsize=7, color="C0"
            )

    for bar, count in zip(qs_bars, qs_counts):
        if count > 0:
            ax.text(
                bar.get_x() + bar.get_width() * 0.9,
                bar.get_height() + 5,
                str(int(count)),
                ha="right", va="bottom", fontsize=7, color="C1"
            )

    for qt_bar, qs_bar, qt_count, qs_count in zip(qt_bars, qs_bars, qt_counts, qs_counts):
        if qt_count > 0 and qs_count > 0:
            pct = (qs_count / qt_count) * 100
            mid_x = (qt_bar.get_x() + qt_bar.get_width() / 2 + qs_bar.get_x() + qs_bar.get_width() / 2) / 2
            mid_y = max(qt_bar.get_height(), qs_bar.get_height()) + 300
            ax.text(
                mid_x, mid_y,
                f"{pct:.1f}%",
                ha="center", va="bottom", fontsize=7, color=PCT_COLOR,
                bbox=dict(boxstyle="round,pad=0.2", facecolor="white", edgecolor=PCT_COLOR, alpha=0.8)
            )

    max_count = max(max(qt_counts), max(qs_counts))
    ax.set_ylim(0, max_count * 1.25)
    ax.set_xlabel("Age (years)")
    ax.set_ylabel("Number of Projects")
    plt.xticks(range(0, 19))
    handles, labels = ax.get_legend_handles_labels()
    pct_patch = mpatches.Patch(color=PCT_COLOR, label="QDataStream usage rate per year (%)")
    handles.append(pct_patch)
    ax.legend(handles=handles)
    plt.tight_layout()
    PLOTS_DIR.mkdir(exist_ok=True)
    fig.savefig(PLOTS_DIR / "age_distribution_comparison.png", dpi=150)
    plt.close(fig)

def plot_qdatastream_usage_rate_per_year(verified_qt_projects: list, qdatastream_projects: list):
    """Plot QDataStream Usage Rate per Year."""
    now = datetime.now(timezone.utc)
    qt_ages = []
    for r in verified_qt_projects:
        created = datetime.fromisoformat(r["createdAt"].replace("Z", "+00:00"))
        qt_ages.append((now - created).days / 365.25)
    qdatastream_ages = []
    for r in qdatastream_projects:
        created = datetime.fromisoformat(r["createdAt"].replace("Z", "+00:00"))
        qdatastream_ages.append((now - created).days / 365.25)

    bins = [x - 0.5 for x in range(0, 20)]
    qt_counts, _ = np.histogram(qt_ages, bins=bins)
    qs_counts, _ = np.histogram(qdatastream_ages, bins=bins)

    bin_centers = [x for x in range(0, 19)]
    rates = []
    valid_centers = []
    for center, qt, qs in zip(bin_centers, qt_counts, qs_counts):
        if qt > 0:
            rates.append((qs / qt) * 100)
            valid_centers.append(center)

    slope, intercept, r, p, _ = stats.linregress(valid_centers, rates)
    trendline = [slope * x + intercept for x in valid_centers]

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(valid_centers, rates, color="#2ecc71", edgecolor="white", label="Usage rate per year")
    ax.plot(valid_centers, trendline, color="#e84c4c", linewidth=1.5,
            label=f"Trend (slope={slope:.4f})")
    ax.annotate(
        f"r = {r:.3f},  p = {p:.3f}",
        xy=(0.97, 0.95), xycoords="axes fraction",
        ha="right", va="top", fontsize=10,
        bbox=dict(boxstyle="round,pad=0.3", facecolor="white", edgecolor="#cccccc")
    )
    ax.set_xlabel("Age (years)")
    ax.set_ylabel("Usage Rate (%)")
    ax.set_ylim(0, max(rates) * 1.25)
    plt.xticks(valid_centers)
    plt.legend()
    plt.tight_layout()
    PLOTS_DIR.mkdir(exist_ok=True)
    fig.savefig(PLOTS_DIR / "qdatastream_usage_rate_per_year.png", dpi=150)
    plt.close(fig)

def plot_age_vs_score_relationship(ranked_qdatastream_projects: list):
    """Plot the relationship between age and score."""

    now = datetime.now(timezone.utc)
    points = []
    for r in ranked_qdatastream_projects:
        created = datetime.fromisoformat(r["createdAt"].replace("Z", "+00:00"))
        age_years = (now - created).days / 365.25
        points.append((age_years, r["score"]))

    ages, scores = zip(*points)
    ages_arr = np.array(ages)
    scores_arr = np.array(scores)

    slope, intercept, r, p, _ = stats.linregress(ages_arr, scores_arr)
    trendline = slope * ages_arr + intercept

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.scatter(ages, scores, color="#4c9be8", edgecolors="white", linewidths=0.5, alpha=0.8, label="Projects")
    ax.plot(ages_arr, trendline, color="#e84c4c", linewidth=1.5, label=f"Trend (slope={slope:.4f})")
    ax.annotate(
        f"r = {r:.3f},  p = {p:.3f}",
        xy=(0.97, 0.95), xycoords="axes fraction",
        ha="right", va="top", fontsize=10,
        bbox=dict(boxstyle="round,pad=0.3", facecolor="white", edgecolor="#cccccc")
    )
    ax.legend()
    ax.set_xlabel("Age (years)")
    ax.set_ylabel("Score")
    plt.tight_layout()
    PLOTS_DIR.mkdir(exist_ok=True)
    out = PLOTS_DIR / "age_vs_score_relationship.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)

# MAIN
# ====================
def main():
    potential_qt_projects = load_jsonl(POTENTIAL_QT_PROJECTS)
    verified_qt_projects = load_jsonl(VERIFIED_QT_PROJECTS)
    qdatastream_projects = load_jsonl(QDATASTREAM_PROJECTS)
    ranked_qdatastream_projects = load_jsonl(RANKED_QDATASTREAM_PROJECTS)
    false_positive_count = len(potential_qt_projects) - len(verified_qt_projects)
    false_positive_rate = false_positive_count / len(potential_qt_projects)
    prevalence_rate = len(qdatastream_projects) / len(verified_qt_projects)
    print("Potential Qt Projects:       " + str(len(potential_qt_projects)))
    print("Verified Qt Projects:        " + str(len(verified_qt_projects)))
    print("QDataStream Projects:        " + str(len(qdatastream_projects)))
    print("Number of false positives:   " + str(false_positive_count))
    print(f"False positive rate:        {false_positive_rate:.6f} -> {false_positive_rate * 100:.4f}%")
    print(f"Prevalence rate:            {prevalence_rate:.6f} -> {prevalence_rate * 100:.4f}%")
    top_10_projects(ranked_qdatastream_projects)
    plot_project_counts(potential_qt_projects, verified_qt_projects, qdatastream_projects)
    plot_score_distribution(ranked_qdatastream_projects)
    plot_age_distribution_comparison(verified_qt_projects, qdatastream_projects)
    plot_qdatastream_usage_rate_per_year(verified_qt_projects, qdatastream_projects)
    plot_age_vs_score_relationship(ranked_qdatastream_projects)
    
if __name__ == "__main__":
    main()
