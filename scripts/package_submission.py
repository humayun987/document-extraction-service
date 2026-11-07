import os
import sys
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

EXCLUDE_PATTERNS = {
    "venv", ".venv", "env", "ENV", "node_modules",
    "__pycache__", ".pytest_cache", ".coverage", "htmlcov",
    ".idea", ".vscode", "tmp", "temp",
    "sample", "sample-data-documents", "sample-data-output-validated"
}

def should_exclude(rel_path_str: str) -> bool:
    """Robust path exclusion matching for submission zip packaging."""
    # Normalize path with forward slashes
    norm_path = rel_path_str.replace("\\", "/").strip("/")
    parts = norm_path.split("/")

    # Exclude storage uploads and temporary uploads
    if norm_path.startswith("storage/uploads") or norm_path.startswith("storage"):
        # Allow the storage directory itself or .gitkeep, but ignore uploaded files
        if norm_path != "storage" and norm_path != "storage/uploads":
            return True

    # Exclude any directory or file matching exclude patterns
    for p in parts:
        if p in EXCLUDE_PATTERNS:
            return True
        if p.endswith(".pyc") or p.endswith(".db") or p.endswith(".sqlite"):
            return True
        if p.startswith(".env") and not p.endswith(".example"):
            return True

    return False

def package(
    rollno: str = "230480",
    firstname: str = "humayun",
    lastname: str = "ahmad",
    role: str = "software"
) -> Path:
    zip_name = f"{rollno}_{firstname}_{lastname}_{role}.zip".lower()
    dest_path = PROJECT_ROOT.parent / zip_name

    print(f"Creating submission package: {dest_path}")
    count = 0

    with zipfile.ZipFile(dest_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(PROJECT_ROOT):
            rel_dir = os.path.relpath(root, PROJECT_ROOT).replace("\\", "/")
            if rel_dir == ".":
                rel_dir = ""

            # Prune excluded directories from search
            dirs[:] = [
                d for d in dirs
                if not should_exclude(f"{rel_dir}/{d}" if rel_dir else d)
            ]

            for file in files:
                rel_file = f"{rel_dir}/{file}" if rel_dir else file
                if should_exclude(rel_file):
                    continue
                abs_file = Path(root) / file
                zf.write(abs_file, rel_file)
                count += 1

    size_mb = dest_path.stat().st_size / (1024 * 1024)
    print(f"Successfully packaged {count} files into {zip_name} ({size_mb:.2f} MB)")
    
    if size_mb > 100.0:
        print("ERROR: Package size exceeds 100 MB limit!")
        sys.exit(1)

    return dest_path

if __name__ == "__main__":
    r_no = sys.argv[1] if len(sys.argv) > 1 else "230480"
    fn = sys.argv[2] if len(sys.argv) > 2 else "humayun"
    ln = sys.argv[3] if len(sys.argv) > 3 else "ahmad"
    rl = sys.argv[4] if len(sys.argv) > 4 else "software"
    package(r_no, fn, ln, rl)
