import os
import sys
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

EXCLUDE_PATTERNS = {
    "venv", ".venv", "env", "ENV", "node_modules",
    "__pycache__", ".pytest_cache", ".coverage", "htmlcov",
    ".idea", ".vscode", "tmp", "temp", "storage/uploads",
    "sample", "sample-data-documents", "sample-data-output-validated",
    ".env", "*.pyc", "*.bin", "test_extraction.db", "extraction.db"
}

def should_exclude(rel_path: str) -> bool:
    parts = Path(rel_path).parts
    for part in parts:
        if part in EXCLUDE_PATTERNS or part.endswith(".pyc") or part.endswith(".db"):
            return True
        if part.startswith(".env"):
            return True
    return False

def package(
    rollno: str = "230480",
    firstname: str = "humayun",
    lastname: str = "ahmad",
    role: str = "aiml"
) -> Path:
    zip_name = f"{rollno}_{firstname}_{lastname}_{role}.zip".lower()
    dest_path = PROJECT_ROOT.parent / zip_name

    print(f"Creating submission package: {dest_path}")
    count = 0

    with zipfile.ZipFile(dest_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(PROJECT_ROOT):
            rel_dir = os.path.relpath(root, PROJECT_ROOT)
            
            # Filter directories
            dirs[:] = [d for d in dirs if not should_exclude(os.path.join(rel_dir, d))]

            for file in files:
                rel_file = os.path.normpath(os.path.join(rel_dir, file)).replace("\\", "/")
                if should_exclude(rel_file):
                    continue
                abs_file = Path(root) / file
                # Write to zip preserving root relative path
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
    rl = sys.argv[4] if len(sys.argv) > 4 else "aiml"
    package(r_no, fn, ln, rl)
