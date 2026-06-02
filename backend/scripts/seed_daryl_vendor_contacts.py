"""Seed vendor contacts + service areas from Daryl's 2026-05-19 notes.

Daryl sent a list of his real vendor contacts with phone, email,
preferred contact channel, payment terms, the trades each handles, and
(per the 2026-05-19 follow-up) the geographic area they'll travel for.
This script applies that data to the existing vendor rows in the dev
database.

It's idempotent — safe to re-run. Trade specializations and contact
fields are replaced entirely with the values listed here; Brenk-internal
fields (markup_notes, communication_notes, mobile_app_capable) are
left alone.

Trade labels are Daryl's preferred phrasing, in Title Case. We prefer
his wording over SC's ALL-CAPS catalog so the dashboard reads how Daryl
talks. Most of these get created as Brenk-custom trades (sc_trade_id=
NULL) and the SC catalog trades stay around for any future work-order
auto-tagging. Three trades that earlier runs of this script created
under SC-style names (WINDOWS/GLASS, BACKFLOW, DRYWALL) get renamed in
place to Daryl's labels so we don't leave orphan rows behind.

Service areas are free text — Brenk's footprint is the Austin + San
Antonio corridor, so most vendors default to that. Two have explicit
overrides: Dean Ballard ("All areas") and OH Door Longview ("Longview
only"). Charles inferred the remaining values from area codes + the
general assumption that Daryl works with locals; Daryl can edit these
in the dashboard if anything is off.

Run with:
    python scripts/seed_daryl_vendor_contacts.py
"""

import asyncio
import logging
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import AsyncSessionLocal
from app.models.work_order import Trade, Vendor

logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


@dataclass
class VendorUpdate:
    vendor_id: int
    phone: str | None = None
    email: str | None = None
    contact_preference: str | None = None  # 'sms' | 'call' | 'email'
    payment_terms: str | None = None
    service_area: str | None = None
    notes: str | None = None
    trades: list[str] = field(default_factory=list)


# Brenk's default service footprint, applied to vendors Daryl didn't
# explicitly tag with anything else.
DEFAULT_AREA = "Austin & San Antonio"


# Daryl's trade vocabulary. Every label here gets ensured as a
# Brenk-custom trade (sc_trade_id=NULL) and is the trade we'll attach
# to vendors below.
DARYL_TRADES = [
    "Appliance Repair",
    "Backflow Inspections",
    "Carpet",
    "Chain Link Fencing",
    "Commercial Door Repair",
    "Electrical",
    "Flooring",
    "Gate Repair",
    "Handyman",
    "Painting",
    "Parking Lot Striping",
    "Plumber",
    "Roll-Up Door Repair",
    "Sheet Rock Repair",
    "Tile",
    "Window and Glass Repair",
    "Wood Fence Repair",
]


# Old custom trades from the first seed pass. Renamed in place to match
# Daryl's preferred phrasing — keeps the same trade id (so any existing
# vendor_trades link survives) and avoids orphan rows in the picker.
TRADE_RENAMES: dict[str, str] = {
    "WINDOWS/GLASS": "Window and Glass Repair",
    "BACKFLOW": "Backflow Inspections",
    "DRYWALL": "Sheet Rock Repair",
}


# Each entry maps Daryl's note → an existing dev vendor row.
# `contact_preference` is normalized to our enum. When Daryl wrote
# "Text/email" we picked SMS as the primary.
VENDOR_UPDATES: list[VendorUpdate] = [
    VendorUpdate(
        vendor_id=91,  # Mario (GTY)
        email="glasstoyou2022@gmail.com",
        phone="5125410081",
        contact_preference="sms",
        payment_terms="Contract",
        service_area=DEFAULT_AREA,
        trades=["Window and Glass Repair"],
    ),
    VendorUpdate(
        vendor_id=80,  # Javier Aboytes
        email="go21do@hotmail.com",
        phone="5128033910",
        contact_preference="sms",
        payment_terms="Contract",
        service_area=DEFAULT_AREA,
        trades=["Plumber"],
    ),
    VendorUpdate(
        vendor_id=89,  # Frank (FA) Appliance
        phone="5124502643",
        contact_preference="sms",
        payment_terms="Contract",
        service_area=DEFAULT_AREA,
        trades=["Appliance Repair"],
    ),
    VendorUpdate(
        vendor_id=77,  # Dean Ballard
        email="dean.ballard@ymail.com",
        phone="2105578338",
        contact_preference="email",
        payment_terms="Contract",
        service_area="Anywhere",
        notes="Will replace parts only.",
        trades=["Commercial Door Repair"],
    ),
    VendorUpdate(
        vendor_id=86,  # Chris Brinkman
        email="aabackflow@outlook.com",
        phone="2103923650",
        contact_preference="email",
        payment_terms="Contract",
        service_area=DEFAULT_AREA,
        trades=["Backflow Inspections"],
    ),
    VendorUpdate(
        vendor_id=88,  # Richard (LPro) Hooper
        email="richard@linearpros.com",
        phone="5125849098",
        contact_preference="email",
        payment_terms="Contract",
        service_area=DEFAULT_AREA,
        trades=["Parking Lot Striping"],
    ),
    VendorUpdate(
        vendor_id=95,  # OH Door Longview (Catherine B)
        email="catherineb@overheadtyler.com",
        phone="9037580301",
        contact_preference="email",
        payment_terms="Contract",
        service_area="Longview only",
        trades=["Roll-Up Door Repair"],
    ),
    VendorUpdate(
        vendor_id=76,  # Larry Marshall
        email="larrysauto1965@yahoo.com",
        phone="7374259234",
        contact_preference="sms",
        payment_terms="Contract",
        service_area=DEFAULT_AREA,
        notes="Will do it all — broad handyman + door / gate work.",
        trades=["Commercial Door Repair", "Gate Repair", "Handyman"],
    ),
    VendorUpdate(
        vendor_id=79,  # Billy Nix
        email="billymnix@yahoo.com",
        phone="5129873376",
        contact_preference="sms",
        payment_terms="Contract",
        service_area=DEFAULT_AREA,
        trades=["Sheet Rock Repair", "Painting"],
    ),
    VendorUpdate(
        vendor_id=83,  # Colton R Roland
        phone="7372976870",
        contact_preference="sms",
        payment_terms="Hourly",
        service_area=DEFAULT_AREA,
        trades=["Electrical", "Handyman"],
    ),
    VendorUpdate(
        vendor_id=78,  # Ulay Torres
        email="ulaytorress@hotmail.com",
        phone="5129023832",
        contact_preference="sms",
        payment_terms="Contract",
        service_area=DEFAULT_AREA,
        trades=["Chain Link Fencing", "Wood Fence Repair", "Handyman"],
    ),
    VendorUpdate(
        vendor_id=96,  # Lalo Vecino
        phone="5125076335",
        contact_preference="sms",
        payment_terms="Contract",
        service_area=DEFAULT_AREA,
        trades=["Flooring", "Tile", "Carpet"],
    ),
]


async def main() -> None:
    async with AsyncSessionLocal() as session:
        # 1. Rename the legacy custom trades from the first pass so
        #    they line up with Daryl's preferred labels.
        for old_name, new_name in TRADE_RENAMES.items():
            row = (
                await session.execute(select(Trade).where(Trade.name == old_name))
            ).scalar_one_or_none()
            if row is None:
                continue
            # If the new label already exists (because we re-ran after
            # already creating it), drop the stale row; ON CONFLICT-safe
            # because the destination is canonical.
            collision = (
                await session.execute(select(Trade).where(Trade.name == new_name))
            ).scalar_one_or_none()
            if collision is not None and collision.id != row.id:
                await session.delete(row)
                print(f"- removed stale duplicate trade {old_name!r}")
            else:
                row.name = new_name
                print(f"↻ renamed trade {old_name!r} → {new_name!r}")
        await session.flush()

        # 2. Ensure every Daryl-labeled trade exists. Idempotent.
        for trade_name in DARYL_TRADES:
            existing = (
                await session.execute(select(Trade).where(Trade.name == trade_name))
            ).scalar_one_or_none()
            if existing is None:
                session.add(Trade(name=trade_name, sc_trade_id=None))
                print(f"+ created Brenk trade: {trade_name}")
        await session.flush()

        # 3. Pre-load every trade so we can look them up by name without
        #    a round-trip per vendor.
        trades_by_name = {t.name: t for t in (await session.execute(select(Trade))).scalars().all()}

        # 4. Apply each vendor update.
        for upd in VENDOR_UPDATES:
            vendor = (
                await session.execute(
                    select(Vendor)
                    .options(selectinload(Vendor.trade_specializations))
                    .where(Vendor.id == upd.vendor_id)
                )
            ).scalar_one_or_none()
            if vendor is None:
                raise RuntimeError(f"Vendor id={upd.vendor_id} not found — re-check the mapping.")

            # Resolve trade names; fail loudly on typos.
            new_trades = []
            for name in upd.trades:
                t = trades_by_name.get(name)
                if t is None:
                    raise RuntimeError(f"Trade {name!r} not found for vendor {vendor.name!r}")
                new_trades.append(t)

            # Update scalar fields only when Daryl actually provided one
            # — don't clobber data already curated in the dashboard.
            if upd.phone is not None:
                vendor.phone = upd.phone
            if upd.email is not None:
                vendor.email = upd.email
            if upd.contact_preference is not None:
                vendor.contact_preference = upd.contact_preference
            if upd.payment_terms is not None:
                vendor.payment_terms = upd.payment_terms
            if upd.service_area is not None:
                vendor.service_area = upd.service_area
            if upd.notes is not None:
                vendor.notes = upd.notes
            # Trade specializations are replaced wholesale.
            vendor.trade_specializations = new_trades

            print(
                f"✓ #{vendor.id:>3} {vendor.name:<32} "
                f"area={vendor.service_area!r:24} "
                f"terms={vendor.payment_terms} "
                f"trades={[t.name for t in new_trades]}"
            )

        await session.commit()
        print(f"\nDone. Updated {len(VENDOR_UPDATES)} vendors.")


if __name__ == "__main__":
    asyncio.run(main())
