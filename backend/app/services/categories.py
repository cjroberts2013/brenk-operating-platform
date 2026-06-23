"""Brenk job-category taxonomy.

A fixed, curated list of job *types* used for profit metrics and markup
suggestions. This is the single source of truth — the categorizer (Gemini)
must pick from `JOB_CATEGORIES`, the PATCH override validates against it,
and `GET /api/v1/categories` serves it to the frontend dropdown.

Distinct from SC's `trade` (the "skills" on a WO, often wrong) and SC's
`category` (just REPAIR/CAPITAL/MAINTENANCE). Adding/renaming a category is
a deliberate code change so historical metrics stay stable.
"""

# (name, short description) — the description guides Gemini's classification.
JOB_CATEGORY_DEFS: list[tuple[str, str]] = [
    ("Electrical", "Wiring, outlets, lighting, panels, electrical repairs."),
    ("Plumbing", "Leaks, drains, pipes, water heaters, fixtures, backflow."),
    ("Roofing", "Roof leaks, membrane, flashing, roof repair/replacement."),
    ("Doors", "Doors of any kind — roll-up, overhead, glass, swing, hardware."),
    ("Gates & Access", "Gates, keypads, access-control, gate motors/operators."),
    ("Fencing", "Fences, gates-as-fencing, posts, perimeter repair."),
    ("HVAC", "Heating, cooling, ventilation, thermostats, AC units."),
    ("Flooring", "Floors, tile, carpet, concrete floor finishes."),
    ("Painting", "Interior/exterior painting, coatings, drywall finishing."),
    ("General Building", "General carpentry/handyman/interior building repairs."),
    ("Exterior Building", "Exterior walls, siding, gutters, soffit, stucco."),
    ("Trash Removal", "Bulk trash, junk hauling, debris/dumpster removal."),
    ("Concrete & Asphalt", "Concrete, asphalt, parking lots, sidewalks, curbs."),
    ("Landscaping", "Landscaping, grounds, irrigation, tree/shrub work."),
    ("Pest Control", "Pest, rodent, insect control and exclusion."),
    ("Other", "Anything that doesn't clearly fit another category."),
]

JOB_CATEGORIES: list[str] = [name for name, _ in JOB_CATEGORY_DEFS]


def is_valid_category(value: str | None) -> bool:
    """True if `value` is one of the curated categories."""
    return value in JOB_CATEGORIES
