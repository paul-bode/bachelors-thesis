import os
import json
import subprocess
import tempfile
from pathlib import Path
from multiprocessing import Pool, Manager, Process
import shutil
import stat

# CONFIG
# ====================
POTENTIAL_QT_PROJECTS = "analysis/potential_qt_projects.jsonl"
VERIFIED_QT_PROJECTS = "analysis/verified_qt_projects.jsonl"
QDATASTREAM_PROJECTS = "analysis/qdatastream_projects.jsonl"
SEARCH_TERM = "QDataStream"
RG_PATH = "rg"
MAX_WORKERS = 20
MAXTASKSPERCHILD = 50
SUBPROCESS_TIMEOUT = 30
QT_FILE_INDICATORS = ["*.pro","*.qml"]
QT_CODE_INDICATORS = [
    "#include <Qt",          
    "#include <Q",
    "Q_OBJECT",
    "QApplication",
    "QCoreApplication",
    "QObject",
]

# HELPERS
# ====================
def load_processed_repos(output_file: str) -> set:
    processed = set()
    p = Path(output_file)
    if not p.exists():
        return processed

    with open(p, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                processed.add(data["nameWithOwner"])
            except json.JSONDecodeError:
                print(f"[WARN] {output_file}: invalid JSON at line {i}")
            except KeyError:
                print(f"[WARN] {output_file}: missing 'nameWithOwner' at line {i}")

    return processed

def run_cmd(cmd: list, cwd: str | None = None, timeout: int = SUBPROCESS_TIMEOUT) -> tuple[int, str, str]:
    """Run a command and return (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return 1, "", f"[ERROR] Command timed out after {timeout}s: {' '.join(cmd)}"
    except Exception as e:
        return 1, "", str(e)

def _force_remove(path: str) -> None:
    """Remove a directory tree robustly, handling read-only files and non-empty dirs."""
    shutil.rmtree(path, ignore_errors=True)

    if os.path.exists(path):
        for root, dirs, files in os.walk(path):
            for d in dirs:
                try:
                    os.chmod(os.path.join(root, d), stat.S_IRWXU)
                except OSError:
                    pass
            for f in files:
                try:
                    os.chmod(os.path.join(root, f), stat.S_IRWXU)
                except OSError:
                    pass
        shutil.rmtree(path, ignore_errors=True)

    if os.path.exists(path):
        print(f"[WARN] Could not fully remove temp dir: {path}")

# CLONE
# ====================
def clone_repo(repo_url: str, target_dir: str) -> None:
    """Clone repository with no blobs and configure sparse checkout to only fetch relevant file types."""

    rc, _, err = run_cmd([
        "git", "clone",
        "--depth=1",
        "--filter=blob:none",
        "--sparse",
        "--quiet",
        repo_url,
        target_dir,
    ])
    if rc != 0:
        raise RuntimeError(f"[ERROR] git clone failed: {err.strip()}")

    rc, _, err = run_cmd([
        "git", "sparse-checkout", "set",
        "--no-cone",
        "*.cpp", "*.h", "*.hpp", "*.cxx", "*.cc",
        "*.pro", "*.pri", "*.qml",
    ], cwd=target_dir)
    if rc != 0:
        raise RuntimeError(f"[ERROR] sparse-checkout failed: {err.strip()}")

    rc, _, err = run_cmd([
        "git", "checkout",
    ], cwd=target_dir)
    if rc != 0:
        raise RuntimeError(f"[ERROR] git checkout failed: {err.strip()}")

# QT DETECTION
# ====================
def is_qt_repo(repo_path: str) -> bool:
    """Return True when the cloned repo looks like a Qt project."""

    file_globs = [arg for p in QT_FILE_INDICATORS for arg in ("-g", p)]
    rc, out, _ = run_cmd(
        [RG_PATH, "--files", "--no-messages", "--max-results", "1"] + file_globs + ["."],
        cwd=repo_path,
    )
    if rc == 0 and out.strip():
        return True

    pattern = "|".join(QT_CODE_INDICATORS)
    rc, out, _ = run_cmd([
        RG_PATH,
        "--files-with-matches",
        "--no-messages",
        "--type", "cpp",
        "--max-count", "1",
        "-e", pattern,
        ".",
    ], cwd=repo_path)

    if rc == 0 and out.strip():
        return True

    return False

# SEARCH
# ====================
def search_repo(repo_path: str, search_term: str) -> list[str]:
    """Return list of C++ files that contain the search term."""

    rc, out, err = run_cmd([
        RG_PATH,
        "--files-with-matches",
        "--no-messages",
        "--type", "cpp",
        search_term,
        ".",
    ], cwd=repo_path)

    if rc == 2:
        print(f"[ERROR] rg error in {repo_path}: {err.strip()}")
        return []

    return [line.strip() for line in out.splitlines() if line.strip()]

# WORKER
# ====================
def process_repo(repo) -> dict:
    """Process a repository by cloning, verifing qt status and searching for the term."""

    name = repo["nameWithOwner"]
    print(f"[WORKER] Processing {name}")

    result = dict(repo)

    tmpdir = tempfile.mkdtemp()
    try:
        repo_path = os.path.join(tmpdir, "repo")

        try:
            clone_repo(repo["url"], repo_path)
        except RuntimeError as e:
            result["is_qt"] = False
            result["matched_paths"] = []
            result["error"] = str(e)
            return result

        if not is_qt_repo(repo_path):
            result["is_qt"] = False
            result["matched_paths"] = []
            return result

        result["is_qt"] = True

        result["matched_paths"] = search_repo(repo_path, SEARCH_TERM)
    finally:
        _force_remove(tmpdir) 

    return result

# WRITER
# ====================
def writer(queue, qt_file: str, qdatastream_file: str) -> None:
    """Consume results from the queue and write to the appropriate output files."""

    try:
        with (
            open(qt_file, "a", encoding="utf-8") as qt_f,
            open(qdatastream_file, "a", encoding="utf-8") as qds_f,
        ):
            while True:
                item = queue.get()
                if item is None:
                    break
                
                try:
                    if item.get("is_qt"):
                        qt_f.write(json.dumps(item) + "\n")
                        qt_f.flush()

                        if item.get("matched_paths"):
                            qds_f.write(json.dumps(item) + "\n")
                            qds_f.flush()
                except Exception as e:
                    print(f"[ERROR] Writer failed on item {item.get('nameWithOwner')}: {e}")

    except Exception as e:
        print(f"[ERROR] Writer process crashed: {e}")

# MAIN
# ====================
def main():
    already_done = (
        load_processed_repos(VERIFIED_QT_PROJECTS)
        | load_processed_repos(QDATASTREAM_PROJECTS)
    )

    repos = []
    with open(POTENTIAL_QT_PROJECTS, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            repo = json.loads(line)
            if repo["nameWithOwner"] not in already_done:
                repos.append(repo)

    total = len(repos)
    print(f"Total to process: {total}  (skipping {len(already_done)} already done)")

    manager = Manager()
    queue = manager.Queue()

    writer_proc = Process(
        target=writer,
        args=(queue, VERIFIED_QT_PROJECTS, QDATASTREAM_PROJECTS),
    )
    writer_proc.start()

    completed = 0
    with Pool(processes=MAX_WORKERS, maxtasksperchild=MAXTASKSPERCHILD) as pool:
        for result in pool.imap_unordered(process_repo, repos, chunksize=1):
            queue.put(result)
            completed += 1
            if completed % 10 == 0:
                print(f"[MAIN] Completed {completed}/{total}")

    queue.put(None)
    writer_proc.join()
    if writer_proc.exitcode != 0:
        print(f"[ERROR] Writer exited with code {writer_proc.exitcode}")
    print("Done.")


if __name__ == "__main__":
    main()
