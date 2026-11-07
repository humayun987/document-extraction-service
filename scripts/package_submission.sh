#!/usr/bin/env bash
set -euo pipefail

ROLLNO="${1:-230480}"
FIRSTNAME="${2:-humayun}"
LASTNAME="${3:-ahmad}"
ROLE="${4:-aiml}"

ZIPNAME="${ROLLNO}_${FIRSTNAME}_${LASTNAME}_${ROLE}.zip"
ZIPNAME=$(echo "$ZIPNAME" | tr '[:upper:]' '[:lower:]')

echo "Packaging submission archive: ../$ZIPNAME"

cd "$(dirname "$0")/.."
python scripts/package_submission.py "$ROLLNO" "$FIRSTNAME" "$LASTNAME" "$ROLE"

echo "Done."
