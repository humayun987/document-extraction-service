#!/usr/bin/env bash
set -euo pipefail

ROLL_NO="230480"
FIRST_NAME="humayun"
LAST_NAME="ahmad"
ROLE="software"

echo "Building submission package for $ROLL_NO ($FIRST_NAME $LAST_NAME, role: $ROLE)..."
python3 scripts/package_submission.py "$ROLL_NO" "$FIRST_NAME" "$LAST_NAME" "$ROLE"
