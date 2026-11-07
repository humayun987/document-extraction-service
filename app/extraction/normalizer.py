import re
from datetime import datetime
from typing import Any, Optional, Tuple, List

DATE_FORMATS = [
    "%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d",
    "%b %d, %Y", "%B %d, %Y", "%d %b %Y", "%d %B %Y",
    "%m/%d/%y", "%Y-%m-%dT%H:%M:%S", "%m-%d-%Y"
]

NUM_RE = re.compile(r"^[+-]?\d+(\.\d+)?$")

class Normalizer:
    @staticmethod
    def normalize_value(raw: Any, expected_type: str = "auto") -> Any:
        """
        Normalize a raw extracted value into contract-compliant JSON scalar/list.
        Handles currencies, date formats, negative parentheses, booleans, and nulls.
        """
        if raw is None:
            return None

        if isinstance(raw, list):
            return [Normalizer.normalize_value(item, expected_type="auto") for item in raw]

        if isinstance(raw, bool):
            return raw

        if isinstance(raw, (int, float)):
            # If float is whole number, return int
            if isinstance(raw, float) and raw.is_integer():
                return int(raw)
            return round(float(raw), 2)

        s = str(raw).strip()
        if not s or s.lower() in {"null", "none", "n/a", "na", "-", "--", "---", "n.a."} or set(s) <= {"-", "_"}:
            return None

        # Check boolean
        low = s.lower()
        if low in {"true", "yes", "y"}:
            return True
        if low in {"false", "no", "n"}:
            return False

        # Check date
        for fmt in DATE_FORMATS:
            try:
                dt = datetime.strptime(s, fmt).date()
                return dt.isoformat()
            except ValueError:
                pass

        # Check numeric with currencies / commas / accounting parentheses
        t = s.replace(",", "").replace("$", "").replace("€", "").replace("£", "").replace("₹", "").strip()
        neg = t.startswith("(") and t.endswith(")")
        if neg:
            t = t[1:-1].strip()
        if t.endswith("%"):
            t = t[:-1].strip()

        if NUM_RE.match(t):
            val = float(t)
            if neg:
                val = -val
            if val.is_integer():
                return int(val)
            return round(val, 2)

        return s

