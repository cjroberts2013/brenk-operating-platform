"""One-time remap: existing vendor trade-specializations → shared job types.

Reads each vendor's legacy `trade_specializations` (the old free-form trades)
and sets their new `job_types` (skills) using the curated mapping below —
incorporating Daryl's calls: Windows & Glass, Parking Lot Striping, Appliance
Repair stay distinct; Sheet Rock → Drywall; Backflow → Plumbing.

Idempotent: re-running sets each vendor's skills to the mapped set. Dry-run by
default; pass --commit to write. Unmapped trades (e.g. "Software Development")
are reported and skipped.

    python scripts/remap_vendor_skills.py            # dry run
    python scripts/remap_vendor_skills.py --commit    # apply
    python scripts/remap_vendor_skills.py --commit .env.production
"""

import sys

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import SessionLocal
from app.models.work_order import JobType, Vendor

# Legacy trade name -> job-type name. Anything not listed is dropped (reported).
MAPPING: dict[str, str] = {
    "Commercial Door Repair": "Doors",
    "Roll-Up Door Repair": "Doors",
    "Window and Glass Repair": "Windows & Glass",
    "Gate Repair": "Gates & Access",
    "Chain Link Fencing": "Fencing",
    "Wood Fence Repair": "Fencing",
    "Electrical": "Electrical",
    "Plumber": "Plumbing",
    "Backflow Inspections": "Plumbing",
    "Painting": "Painting",
    "Sheet Rock Repair": "Drywall",
    "Handyman": "General Building",
    "Tile": "Flooring",
    "Carpet": "Flooring",
    "Flooring": "Flooring",
    "Parking Lot Striping": "Parking Lot Striping",
    "Appliance Repair": "Appliance Repair",
}


def main() -> None:
    commit = "--commit" in sys.argv
    session = SessionLocal()
    try:
        job_types = {jt.name: jt for jt in session.execute(select(JobType)).scalars()}
        vendors = (
            session.execute(select(Vendor).options(selectinload(Vendor.trade_specializations)))
            .scalars()
            .all()
        )

        dropped: set[str] = set()
        for v in vendors:
            old = [t.name for t in v.trade_specializations]
            mapped_names: list[str] = []
            for name in old:
                target = MAPPING.get(name)
                if target is None:
                    dropped.add(name)
                elif target not in mapped_names:
                    mapped_names.append(target)
            new_types = [job_types[n] for n in mapped_names if n in job_types]
            v.job_types = new_types
            if old or mapped_names:
                print(f"  {v.name:32} {old}  ->  {[t.name for t in new_types]}")

        if dropped:
            print(f"\nDropped (no mapping): {sorted(dropped)}")

        if commit:
            session.commit()
            print("\nCOMMITTED.")
        else:
            session.rollback()
            print("\nDRY RUN — re-run with --commit to apply.")
    finally:
        session.close()


if __name__ == "__main__":
    main()
