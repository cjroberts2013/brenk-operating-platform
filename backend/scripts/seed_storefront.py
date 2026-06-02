"""Seed initial storefront content for Brenk Facility Services.

Sets reasonable starting values for the marketing site at
`brenkfacilityservices.com`. Daryl edits any of this via the
dashboard `/storefront` editor — the values here are just so a
fresh database (or a fresh prod cutover) doesn't show an empty
hero block to the first visitor.

Run with:
    python scripts/seed_storefront.py

Idempotent — running twice doesn't duplicate the singleton row.
Will OVERWRITE existing values if you run it again with edits in
between; intentional, since the script is meant to reset to
"known defaults" when invoked.
"""

import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import AsyncSessionLocal
from app.models.storefront import StorefrontContent, StorefrontService

logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


# Page-level copy. Voice is intentionally warm + concrete — Daryl
# can tighten this later. References to specific years / decades
# are deliberately vague so the copy doesn't go stale before Daryl
# proofs it.
PAGE_CONTENT = {
    "hero_title": "Brenk Facility Services",
    "hero_subtitle": (
        "Family-owned commercial facility maintenance serving Austin, "
        "San Antonio, and the I-35 corridor. One call gets every trade "
        "your property needs."
    ),
    "hero_cta_text": "Get a quote",
    "hero_cta_link": "/quote",
    "hero_image_url": None,
    "about_heading": "A family business, built on relationships.",
    "about_body": (
        "Brenk Facility Services has been quietly keeping commercial "
        "properties running across Central Texas for years. Daryl Brenk "
        "runs the business the way his family always has — answer the "
        "phone, show up on time, and treat every property like it's our "
        "own.\n\n"
        "We coordinate a vetted network of trade specialists so you "
        "don't have to. Whether it's a midnight plumbing emergency or "
        "a scheduled maintenance walk-through, one call goes a long way."
    ),
    "about_image_url": None,
    "service_area_heading": "Serving Austin & San Antonio",
    "service_area_body": (
        "We cover commercial properties across the I-35 corridor "
        "between Austin and San Antonio, with established crews in "
        "Buda, Kyle, San Marcos, New Braunfels, Schertz, and "
        "surrounding communities. Out-of-area work considered case "
        "by case."
    ),
    "contact_email": "brenkconstruction@gmail.com",
    "contact_phone": "(512) 369-2719",
    "contact_address": "Buda, TX 78610",
    "contact_hours": "Mon-Fri, 8am-6pm CT",
    "footer_tagline": "Commercial facility maintenance, done right.",
    "footer_copyright": "(c) Brenk Facility Services, LLC.",
    "logo_url": None,
}


# Default service list. Editor lets Daryl reorder, edit, add, remove.
# Icons are Heroicon outline names that the storefront's
# ServiceIcon component knows how to resolve.
SERVICES = [
    {
        "title": "Plumbing",
        "description": "Commercial plumbing repair, replacement, and emergency service.",
        "icon": "wrench-screwdriver",
    },
    {
        "title": "Electrical",
        "description": "Licensed electricians for commercial repair and lighting.",
        "icon": "bolt",
    },
    {
        "title": "Doors & Gates",
        "description": "Overhead, roll-up, commercial, and gate systems.",
        "icon": "home-modern",
    },
    {
        "title": "Painting & Drywall",
        "description": "Interior and exterior commercial painting plus drywall repair.",
        "icon": "paintbrush",
    },
    {
        "title": "Flooring",
        "description": "Tile, carpet, and flooring installation and repair.",
        "icon": "stack",
    },
    {
        "title": "General Building",
        "description": "Handyman, fencing, appliance repair, and one-call coordination.",
        "icon": "building",
    },
]


async def main() -> None:
    async with AsyncSessionLocal() as session:
        # Fetch the singleton (or create if missing).
        stmt = (
            select(StorefrontContent)
            .options(selectinload(StorefrontContent.services))
            .where(StorefrontContent.id == 1)
        )
        content = (await session.execute(stmt)).scalar_one_or_none()
        if content is None:
            content = StorefrontContent(id=1)
            session.add(content)
            print("+ created storefront_content row")
        else:
            print("↻ updating existing storefront_content row")

        for k, v in PAGE_CONTENT.items():
            setattr(content, k, v)

        # Wipe and replace services. Cascade handles delete-orphan.
        content.services = []
        await session.flush()
        for i, item in enumerate(SERVICES):
            content.services.append(
                StorefrontService(
                    content_id=content.id,
                    sort_order=i,
                    title=item["title"],
                    description=item["description"],
                    icon=item["icon"],
                )
            )

        await session.commit()

        print(f"✓ {len(PAGE_CONTENT)} page fields set")
        print(f"✓ {len(SERVICES)} services seeded:")
        for i, s in enumerate(SERVICES):
            print(f"    {i + 1}. {s['title']}")


if __name__ == "__main__":
    asyncio.run(main())
