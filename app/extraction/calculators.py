from datetime import datetime
from typing import Dict, Any, List, Optional
from decimal import Decimal

class DerivedCalculators:
    @staticmethod
    def calculate_months_between(start_iso: str, end_iso: str) -> Optional[int]:
        """Calculate inclusive calendar months between two dates."""
        try:
            d1 = datetime.strptime(start_iso, "%Y-%m-%d").date()
            d2 = datetime.strptime(end_iso, "%Y-%m-%d").date()
            if d2 < d1:
                return None
            months = (d2.year - d1.year) * 12 + (d2.month - d1.month)
            # Check if inclusive end of month or full month span
            if d2.day >= 28 and d1.day == 1:
                months += 1
            return max(1, months)
        except Exception:
            return None

    @staticmethod
    def compute_lease_fields(entry: Dict[str, Any]) -> Dict[str, Any]:
        """Reconcile derived lease fields deterministically."""
        # Rent schedule alignment & annual rent per RSF
        rsf = None
        if "rentable_square_footage" in entry and entry["rentable_square_footage"].get("value"):
            try:
                rsf = float(entry["rentable_square_footage"]["value"])
            except Exception:
                pass

        m_rents = entry.get("rent_schedule_monthly_rent", {}).get("value")
        if isinstance(m_rents, list) and rsf and rsf > 0:
            ann_rates = entry.get("rent_schedule_annual_rent_per_rsf", {}).get("value")
            if not ann_rates or not isinstance(ann_rates, list) or len(ann_rates) != len(m_rents):
                computed_ann = [round((m * 12.0) / rsf, 2) for m in m_rents]
                entry.setdefault("rent_schedule_annual_rent_per_rsf", {})
                entry["rent_schedule_annual_rent_per_rsf"]["value"] = computed_ann
                entry["rent_schedule_annual_rent_per_rsf"]["confidence"] = 0.95
                entry["rent_schedule_annual_rent_per_rsf"]["citation"] = (
                    f"Computed deterministically: (Monthly Rent * 12) / RSF ({rsf})"
                )

        # Term months calculation if missing
        comm = entry.get("lease_commencement_date", {}).get("value")
        exp = entry.get("lease_expiration_date", {}).get("value")
        term_m = entry.get("lease_term_months", {}).get("value")
        if term_m is None and comm and exp:
            calc_m = DerivedCalculators.calculate_months_between(str(comm), str(exp))
            if calc_m:
                entry.setdefault("lease_term_months", {})
                entry["lease_term_months"]["value"] = calc_m
                entry["lease_term_months"]["confidence"] = 0.95
                entry["lease_term_months"]["citation"] = f"Calculated from {comm} to {exp} ({calc_m} months)"

        return entry

    @staticmethod
    def compute_om_fields(entry: Dict[str, Any]) -> Dict[str, Any]:
        """Compute derived OM ratios if inputs are present."""
        units = entry.get("total_units", {}).get("value")
        sqft = entry.get("total_square_footage", {}).get("value")
        avg_sz = entry.get("average_unit_size", {}).get("value")
        
        if avg_sz is None and units and sqft:
            try:
                u, s = float(units), float(sqft)
                if u > 0:
                    entry.setdefault("average_unit_size", {})
                    entry["average_unit_size"]["value"] = round(s / u, 1)
                    entry["average_unit_size"]["confidence"] = 0.95
                    entry["average_unit_size"]["citation"] = f"Computed: Total SF ({sqft}) / Total Units ({units})"
            except Exception:
                pass

        parking = entry.get("total_parking_spaces", {}).get("value")
        park_ratio = entry.get("parking_ratio", {}).get("value")
        if park_ratio is None and units and parking:
            try:
                u, p = float(units), float(parking)
                if u > 0:
                    entry.setdefault("parking_ratio", {})
                    entry["parking_ratio"]["value"] = round(p / u, 2)
                    entry["parking_ratio"]["confidence"] = 0.95
                    entry["parking_ratio"]["citation"] = f"Computed: Parking ({parking}) / Total Units ({units})"
            except Exception:
                pass

        return entry

