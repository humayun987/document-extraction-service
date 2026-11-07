import os
import sys
import json
import subprocess
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.extractors.tables import extract_document
from app.extraction.document_extractor import DocumentExtractor
from app.utils.logging import logger

SAMPLE_MAPPINGS = [
    ("boxscore_001.csv", "boxscore.json", "boxscore"),
    ("budget_001.pdf", "budget_variance.json", "budget_variance"),
    ("lease_001.pdf", "lease_abstraction.json", "lease_abstraction"),
    ("lease_002.docx", "lease_abstraction.json", "lease_abstraction"),
    ("lease_003.pdf", "lease_abstraction.json", "lease_abstraction"),
    ("om_001.pdf", "offering_memorandum.json", "offering_memorandum"),
    ("t12_001.xlsx", "operating_statement_lines.json", "operating_statement_lines"),
    ("rentroll_001.xlsx", "rent_roll_units.json", "rent_roll_units"),
]

def main():
    assignment_data_dir = os.environ.get(
        "ASSIGNMENT_DATA_DIR",
        str(PROJECT_ROOT.parent / "Outcome_Take_Home_Assignment")
    )
    data_path = Path(assignment_data_dir)
    if not data_path.exists():
        print(f"Error: Assignment data directory not found at {data_path}")
        sys.exit(1)

    schemas_dir = data_path / "sample" / "schemas"
    docs_dir = data_path / "sample" / "sample-data-documents"
    truth_dir = data_path / "sample" / "sample-data-output-validated"
    outputs_dir = PROJECT_ROOT / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)

    print(f"=== Running Sample Evaluation Pipeline ===")
    print(f"Documents Directory: {docs_dir}")
    print(f"Outputs Directory:   {outputs_dir}")

    extractor = DocumentExtractor()

    for doc_file, schema_file, schema_name in SAMPLE_MAPPINGS:
        doc_path = docs_dir / doc_file
        schema_path = schemas_dir / schema_file
        out_path = outputs_dir / f"{Path(doc_file).stem}.json"

        if not doc_path.exists():
            print(f"Warning: Missing document {doc_path}")
            continue

        print(f"\nProcessing {doc_file} against {schema_name}...")
        schema_dict = json.loads(schema_path.read_text(encoding="utf-8"))
        file_type = doc_path.suffix.lstrip(".").lower()

        parsed_doc = extract_document(str(doc_path), file_type)
        result = extractor.extract(parsed_doc, schema_dict)

        # Batch validator expects top-level "schema" key in offline output files
        result["schema"] = schema_name

        out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"  -> Generated {out_path.name} ({len(result['entries'])} rows)")

    print("\n=== Validating Outputs against Ground Truth ===")
    validator_path = PROJECT_ROOT / "tools" / "validate.py"
    cmd = [
        sys.executable,
        str(validator_path),
        str(outputs_dir),
        "--schema-dir", str(schemas_dir),
        "--truth-dir", str(truth_dir)
    ]
    subprocess.run(cmd)

if __name__ == "__main__":
    main()

