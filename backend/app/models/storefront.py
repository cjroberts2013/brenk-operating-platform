"""ORM models for the public-facing storefront content.

The storefront is the marketing site at the bare domain
(`brenkfacilityservices.com`) — distinct from the dashboard at
`app.brenkfacilityservices.com`. Content is editable from the
dashboard's `/storefront` page; the public site reads (no auth)
via `GET /api/v1/storefront`.

Data model (kept intentionally small for v1):

- `storefront_content` — a **singleton** row that holds every
  page-level field (hero, about, contact, footer, etc.). One row,
  one site. We constrain `id = 1` so accidental inserts can't
  produce a second "draft" row.
- `storefront_services` — an ordered list of service offerings
  (Plumbing, Electrical, etc.) displayed in the Services section.

If we ever need multi-page or block-based layouts, we refactor
without losing data — the singleton row becomes the homepage and
new tables join in.
"""

from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class StorefrontService(Base, TimestampMixin):
    """One service-offering card on the Services section.

    The set is replaced wholesale on each PATCH from the editor —
    simpler than partial CRUD for a list this small (<= ~20 items).
    """

    __tablename__ = "storefront_services"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    content_id: Mapped[int] = mapped_column(
        ForeignKey("storefront_content.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    """0-indexed render order. Editor reorders by re-numbering."""

    title: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    icon: Mapped[str | None] = mapped_column(String(50))
    """Heroicon name (e.g. 'wrench-screwdriver'). Renderer maps to the
    actual icon component. NULL = no icon, plain title."""

    # back_populates set via string here because StorefrontContent
    # isn't defined yet — that's the one forward-ref we can't avoid
    # without an explicit relationship config block on the parent.
    # `from __future__ import annotations` makes this safe at runtime.
    content: Mapped[StorefrontContent] = relationship(back_populates="services")


class StorefrontContent(Base, TimestampMixin):
    """Singleton row holding every editable page-level field.

    Why one row instead of one row per section: at v1 scale the
    overhead of a normalized schema (joins, ordering, partial
    updates per section) buys nothing. A single row is trivially
    fetched in one query, the editor PATCH payload is small, and
    NULL columns let us leave optional sections blank without
    inventing a "section type" enum.
    """

    __tablename__ = "storefront_content"

    # Locked to id=1 by app convention (see endpoint code). The DB
    # doesn't enforce singleton-ness — we trust the small surface
    # area + the upsert pattern in the endpoint.
    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # --- Hero section ---
    hero_title: Mapped[str | None] = mapped_column(String(200))
    hero_subtitle: Mapped[str | None] = mapped_column(String(500))
    hero_cta_text: Mapped[str | None] = mapped_column(String(100))
    """e.g. 'Get a quote' — the primary call-to-action button label."""
    hero_cta_link: Mapped[str | None] = mapped_column(String(500))
    """URL or anchor — '#contact' jumps to the contact section."""
    hero_image_url: Mapped[str | None] = mapped_column(String(1000))
    """Public URL (Supabase Storage). Hero background or right-side image."""

    # --- About section ---
    about_heading: Mapped[str | None] = mapped_column(String(200))
    about_body: Mapped[str | None] = mapped_column(Text)
    """Plain text, newlines preserved. Markdown not parsed in v1 — keeps
    the editor + renderer simple. Revisit if Daryl wants formatting."""
    about_image_url: Mapped[str | None] = mapped_column(String(1000))

    # --- Service area ---
    service_area_heading: Mapped[str | None] = mapped_column(String(200))
    service_area_body: Mapped[str | None] = mapped_column(Text)
    """e.g. 'Serving Austin, San Antonio, and surrounding communities...'"""

    # --- Contact ---
    contact_email: Mapped[str | None] = mapped_column(String(255))
    contact_phone: Mapped[str | None] = mapped_column(String(50))
    contact_address: Mapped[str | None] = mapped_column(String(500))
    contact_hours: Mapped[str | None] = mapped_column(String(200))
    """Free text, e.g. 'Mon-Fri 8am-6pm CT'."""

    # --- Footer ---
    footer_tagline: Mapped[str | None] = mapped_column(String(300))
    footer_copyright: Mapped[str | None] = mapped_column(String(200))

    # --- Branding ---
    logo_url: Mapped[str | None] = mapped_column(String(1000))
    """The mark shown in the header. Daryl uploads via the editor."""

    services: Mapped[list[StorefrontService]] = relationship(
        back_populates="content",
        order_by="StorefrontService.sort_order",
        cascade="all, delete-orphan",
    )
