/**
 * Mock data for the public marketing storefront.
 *
 * The hi-fi homepage design ships with hardcoded copy for 9 of its
 * 12 sections (per Charles + Daryl, 2026-05-28 — see CLAUDE.md
 * "What To Work On Next" and the design handoff README). The
 * editable surfaces (hero, footer tagline, logo) come from the
 * Storefront API; everything below is fixed for v1.
 *
 * Structured as typed `as const` arrays so each section reads
 * like data, not markup. When Daryl asks for editing on any of
 * these (most likely: projects, then stats, then testimonial),
 * the Phase B migration moves the literal here into the DB
 * without restructuring the component that renders it.
 *
 * Numbers, names, and phone digits are all placeholders pending
 * Daryl's asset bundle — clearly mock, not invented credentials.
 */

// =============================================================
// Utility bar + CTAs (shared across multiple sections)
// =============================================================

export const EMERGENCY_PHONE = '(512) 369-2719'
export const EMERGENCY_PHONE_HREF = 'tel:5123692719'
export const TAGLINE_SINCE = 'Serving the Tri-State region since 1989'
export const TAGLINE_TRUST = 'Licensed · Bonded · Insured'

// =============================================================
// Services directory — 7 grouped categories.
//
// These are intentionally a `slug` + `title` + `items[]` shape
// (not a flat list) because the design groups them visually and
// the existing DB schema (`storefront_services`, flat) doesn't
// fit. Daryl confirmed (2026-05-28) the current DB list was temp
// data; we ignore it for v1 and use this hardcoded structure.
// =============================================================

export type ServiceGroup = {
  slug:
    | 'hvac'
    | 'electrical'
    | 'plumbing'
    | 'doors'
    | 'exterior'
    | 'construction'
    | 'general'
  title: string
  items: string[]
}

export const SERVICE_GROUPS: readonly ServiceGroup[] = [
  {
    slug: 'hvac',
    title: 'HVAC & Mechanical',
    items: [
      'HVAC install & repair',
      'Refrigeration',
      'Boilers & chillers',
      'Ventilation & ductwork',
      'Building controls / BAS',
      'Preventive maintenance',
    ],
  },
  {
    slug: 'electrical',
    title: 'Electrical',
    items: [
      'Lighting & retrofits',
      'Panel upgrades',
      'Generators & backup power',
      'EV charging',
      'Wiring & rewires',
      'Emergency power',
    ],
  },
  {
    slug: 'plumbing',
    title: 'Plumbing',
    items: [
      'Repairs & leaks',
      'Water heaters',
      'Backflow testing',
      'Drain cleaning',
      'Fixtures & restrooms',
      'Gas lines',
    ],
  },
  {
    slug: 'doors',
    title: 'Doors & Openings',
    items: [
      'Overhead & dock doors',
      'Automatic doors',
      'Glass & storefront',
      'Locks & hardware',
      'Gates & access',
    ],
  },
  {
    slug: 'exterior',
    title: 'Exterior & Grounds',
    items: [
      'Landscaping',
      'Irrigation',
      'Snow & ice removal',
      'Parking lot & striping',
      'Pressure washing',
      'Pest control',
    ],
  },
  {
    slug: 'construction',
    title: 'Construction & Remodel',
    items: [
      'Tenant build-out',
      'Remodels',
      'New construction',
      'Painting',
      'Flooring',
      'Roofing',
    ],
  },
  {
    slug: 'general',
    title: 'General Maintenance',
    items: [
      'Handyman services',
      'Drywall & ceilings',
      'Carpentry',
      'Janitorial coordination',
      '24/7 emergency repair',
    ],
  },
] as const

// =============================================================
// Stats band — credibility at a glance.
// Placeholder figures pending Daryl confirming real numbers.
// =============================================================

export const STATS = [
  { num: '35+', label: 'Years in business' },
  { num: '1,200+', label: 'Facilities served' },
  { num: '24/7', label: 'Emergency response' },
  { num: '98%', label: 'Client retention' },
] as const

export const CREDENTIALS = [
  'Licensed & bonded',
  'Insured to $5M',
  'OSHA-trained crews',
  'EPA certified',
] as const

// =============================================================
// Logo cloud — placeholder client names.
// Replace with real grayscale logos when Daryl provides them.
// =============================================================

export const CLIENT_LOGOS = [
  'CLIENT LOGO',
  'CLIENT LOGO',
  'CLIENT LOGO',
  'CLIENT LOGO',
  'CLIENT LOGO',
  'CLIENT LOGO',
] as const

// =============================================================
// Why Brenk — value-prop cards.
// =============================================================

export type ValueProp = {
  iconKey: 'cluster' | 'clock' | 'shield' | 'calendar'
  title: string
  body: string
}

export const VALUE_PROPS: readonly ValueProp[] = [
  {
    iconKey: 'cluster',
    title: 'One vendor, every trade',
    body: 'Stop juggling a dozen contractors. One contract, one invoice, one team accountable for your whole facility.',
  },
  {
    iconKey: 'clock',
    title: 'Rapid emergency response',
    body: 'A live 24/7 dispatch line and crews on call, so most emergencies are on-site in under two hours.',
  },
  {
    iconKey: 'shield',
    title: 'Compliance-ready',
    body: 'Licensed, bonded, OSHA-trained, and insured to $5M. Certificates and safety records ready for procurement.',
  },
  {
    iconKey: 'calendar',
    title: 'Preventive programs',
    body: 'Scheduled maintenance plans that catch problems early, extend equipment life, and smooth your budget.',
  },
] as const

// =============================================================
// Certifications & safety — procurement-facing trust panel.
// =============================================================

export type Certification = {
  iconKey: 'badge' | 'globe' | 'doc' | 'shield'
  title: string
  caption: string
}

export const CERTIFICATIONS: readonly Certification[] = [
  { iconKey: 'badge', title: 'OSHA', caption: '30-hr trained crews' },
  { iconKey: 'globe', title: 'EPA certified', caption: 'Refrigerant handling' },
  { iconKey: 'doc', title: 'Licensed & bonded', caption: 'State lic. #000000' },
  {
    iconKey: 'shield',
    title: 'Insured to $5M',
    caption: 'Certificates on request',
  },
] as const

// =============================================================
// Featured projects — case studies, placeholder copy.
// Likely the first surface Daryl asks to edit, so the shape
// here is the shape we want in the DB later.
// =============================================================

export type Project = {
  tag: string
  title: string
  description: string
  metrics: { value: string; label: string }[]
  photoCaption: string
}

export const PROJECTS: readonly Project[] = [
  {
    tag: 'Multi-site retail',
    title: '40-store HVAC modernization',
    description:
      'Phased rooftop unit replacement across a regional retail portfolio with zero store closures.',
    metrics: [
      { value: '−22%', label: 'energy use' },
      { value: '40', label: 'sites' },
    ],
    photoCaption: 'Retail HVAC replacement',
  },
  {
    tag: 'Commercial office',
    title: 'Class-A tenant build-out',
    description:
      'Full-floor remodel (electrical, plumbing, doors, and finishes) delivered two weeks early.',
    metrics: [
      { value: '28,000', label: 'sq ft' },
      { value: '11', label: 'weeks' },
    ],
    photoCaption: 'Office tenant build-out',
  },
  {
    tag: 'Industrial / logistics',
    title: 'Distribution center upkeep',
    description:
      'Preventive maintenance program covering dock doors, lighting, and grounds across 3 shifts.',
    metrics: [
      { value: '99.6%', label: 'uptime' },
      { value: '24/7', label: 'coverage' },
    ],
    photoCaption: 'Warehouse dock doors',
  },
] as const

// =============================================================
// Testimonial — single quote, placeholder.
// =============================================================

export const TESTIMONIAL = {
  quote:
    'Brenk replaced five vendors with one. We make a single call and it gets handled, and the response time on emergencies is genuinely the best we’ve worked with.',
  attribution: 'Director of Facilities · Regional Property Group',
} as const

// =============================================================
// Footer link blocks.
// =============================================================

export type FooterLink = { label: string; href: string }
export type FooterColumn = { heading: string; links: FooterLink[] }

export const FOOTER_COLUMNS: readonly FooterColumn[] = [
  {
    heading: 'Services',
    links: [
      { label: 'HVAC & Mechanical', href: '/#services' },
      { label: 'Electrical', href: '/#services' },
      { label: 'Plumbing', href: '/#services' },
      { label: 'Doors & Openings', href: '/#services' },
      { label: 'Construction & Remodel', href: '/#services' },
    ],
  },
  {
    heading: 'Company',
    links: [
      { label: 'About / Our Story', href: '#' },
      { label: 'Projects', href: '/#projects' },
      { label: 'Certifications & Safety', href: '/#certs' },
      { label: 'Service Areas', href: '#' },
      { label: 'Careers', href: '#' },
    ],
  },
  {
    heading: 'Get in touch',
    links: [
      { label: 'Request a Quote', href: '/quote' },
      { label: '24/7 Emergency Line', href: EMERGENCY_PHONE_HREF },
      { label: EMERGENCY_PHONE, href: EMERGENCY_PHONE_HREF },
      {
        label: 'daryl@brenkfacilityservices.com',
        href: 'mailto:daryl@brenkfacilityservices.com',
      },
    ],
  },
] as const

// =============================================================
// Main nav links — single source of truth used by both the
// desktop nav and the mobile drawer.
// =============================================================

export const NAV_LINKS: readonly FooterLink[] = [
  { label: 'Services', href: '/#services' },
  { label: 'Projects', href: '/#projects' },
  { label: 'Service Areas', href: '#' },
  { label: 'Certifications', href: '/#certs' },
  { label: 'About', href: '#' },
] as const
