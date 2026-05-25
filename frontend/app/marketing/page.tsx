import Image from 'next/image'
import { EnvelopeIcon, MapPinIcon, PhoneIcon } from '@heroicons/react/24/outline'

import { ServiceIcon } from '@/components/marketing/ServiceIcon'
import { getStorefrontPublic } from '@/lib/api/storefront'

/** Validate an operator-supplied href before rendering.
 *
 *  Allow:
 *   - empty / null (caller falls back to a safe default)
 *   - anchors (#contact)
 *   - http: / https: (absolute)
 *   - mailto: / tel:
 *   - relative paths that START WITH / (e.g. '/services') so the
 *     anchor stays on the bare domain
 *
 *  Block everything else — most importantly `javascript:`,
 *  `data:`, vbscript:, etc. — which would otherwise be a stored-
 *  XSS vector if a malicious editor user planted one.
 *
 *  Defense in depth — the editor has authenticated access only,
 *  but trusting operator input on render means we don't have to
 *  audit every code path that writes the field. */
function safeHref(raw: string | null, fallback = '#contact'): string {
  if (!raw) return fallback
  const trimmed = raw.trim()
  if (!trimmed) return fallback
  if (trimmed.startsWith('#')) return trimmed
  if (trimmed.startsWith('/')) return trimmed
  // Anything with a colon needs a scheme allowlist.
  if (trimmed.includes(':')) {
    const lower = trimmed.toLowerCase()
    const allowed = ['http://', 'https://', 'mailto:', 'tel:']
    if (!allowed.some((p) => lower.startsWith(p))) {
      return fallback
    }
  }
  return trimmed
}

export default async function StorefrontPage() {
  const content = await getStorefrontPublic()

  return (
    <main className="bg-white">
      <SiteHeader logoUrl={content.logo_url} />

      <Hero
        title={content.hero_title}
        subtitle={content.hero_subtitle}
        ctaText={content.hero_cta_text}
        ctaLink={content.hero_cta_link}
        imageUrl={content.hero_image_url}
      />

      {content.services.length > 0 ? <Services items={content.services} /> : null}

      {content.about_heading || content.about_body ? (
        <About
          heading={content.about_heading}
          body={content.about_body}
          imageUrl={content.about_image_url}
        />
      ) : null}

      {content.service_area_heading || content.service_area_body ? (
        <ServiceArea
          heading={content.service_area_heading}
          body={content.service_area_body}
        />
      ) : null}

      <Contact
        email={content.contact_email}
        phone={content.contact_phone}
        address={content.contact_address}
        hours={content.contact_hours}
      />

      <SiteFooter
        tagline={content.footer_tagline}
        copyright={content.footer_copyright}
      />
    </main>
  )
}

// =============================================================================
// Sections
// =============================================================================

function SiteHeader({ logoUrl }: { logoUrl: string | null }) {
  return (
    <header className="border-b border-gray-100">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-5">
        <a href="/" className="flex items-center gap-3">
          {logoUrl ? (
            // next/image with unoptimized=true because the URL is
            // remote and the marketing site doesn't ship a custom
            // remote-image config yet.
            <Image
              src={logoUrl}
              alt="Brenk Facility Services"
              width={40}
              height={40}
              unoptimized
              className="size-10 rounded-md object-contain"
            />
          ) : (
            <div className="flex size-10 items-center justify-center rounded-md bg-blue-700 text-white">
              <span className="text-lg font-semibold">B</span>
            </div>
          )}
          <span className="text-base font-semibold tracking-tight text-gray-900">
            Brenk Facility Services
          </span>
        </a>
        <nav className="hidden gap-6 text-sm font-medium text-gray-600 md:flex">
          <a href="#services" className="hover:text-blue-700">
            Services
          </a>
          <a href="#about" className="hover:text-blue-700">
            About
          </a>
          <a href="#service-area" className="hover:text-blue-700">
            Service area
          </a>
          <a href="#contact" className="hover:text-blue-700">
            Contact
          </a>
        </nav>
      </div>
    </header>
  )
}

function Hero({
  title,
  subtitle,
  ctaText,
  ctaLink,
  imageUrl,
}: {
  title: string | null
  subtitle: string | null
  ctaText: string | null
  ctaLink: string | null
  imageUrl: string | null
}) {
  return (
    <section className="relative isolate overflow-hidden bg-gradient-to-b from-blue-50 to-white">
      <div className="mx-auto grid max-w-6xl grid-cols-1 items-center gap-10 px-6 py-20 md:grid-cols-2 md:py-28">
        <div>
          <h1 className="text-4xl font-semibold tracking-tight text-gray-900 sm:text-5xl">
            {title ?? 'Brenk Facility Services'}
          </h1>
          {subtitle ? (
            <p className="mt-6 max-w-xl text-lg text-gray-600">{subtitle}</p>
          ) : null}
          {ctaText ? (
            <div className="mt-8">
              <a
                href={safeHref(ctaLink, '#contact')}
                className="inline-flex items-center rounded-md bg-blue-700 px-5 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-blue-600"
              >
                {ctaText}
              </a>
            </div>
          ) : null}
        </div>
        {imageUrl ? (
          <div className="relative aspect-[4/3] overflow-hidden rounded-2xl shadow-xl ring-1 ring-gray-200">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={imageUrl}
              alt=""
              className="size-full object-cover"
            />
          </div>
        ) : (
          // No image yet — fill the right column with a soft gradient
          // so the hero doesn't look lopsided.
          <div className="aspect-[4/3] rounded-2xl bg-gradient-to-br from-blue-100 via-blue-50 to-white ring-1 ring-blue-100" />
        )}
      </div>
    </section>
  )
}

function Services({
  items,
}: {
  items: Awaited<ReturnType<typeof getStorefrontPublic>>['services']
}) {
  return (
    <section id="services" className="mx-auto max-w-6xl px-6 py-20">
      <div className="max-w-2xl">
        <h2 className="text-3xl font-semibold tracking-tight text-gray-900">
          What we do
        </h2>
        <p className="mt-3 text-gray-600">
          Commercial facility maintenance across every trade your business
          needs.
        </p>
      </div>
      <ul className="mt-12 grid grid-cols-1 gap-x-8 gap-y-10 sm:grid-cols-2 lg:grid-cols-3">
        {items.map((s) => (
          <li key={s.sort_order} className="flex gap-4">
            <div className="flex size-10 shrink-0 items-center justify-center rounded-md bg-blue-50 text-blue-700">
              <ServiceIcon name={s.icon} className="size-5" />
            </div>
            <div>
              <h3 className="text-base font-semibold text-gray-900">{s.title}</h3>
              {s.description ? (
                <p className="mt-1 text-sm text-gray-600">{s.description}</p>
              ) : null}
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}

function About({
  heading,
  body,
  imageUrl,
}: {
  heading: string | null
  body: string | null
  imageUrl: string | null
}) {
  return (
    <section id="about" className="bg-gray-50">
      <div className="mx-auto grid max-w-6xl grid-cols-1 items-center gap-10 px-6 py-20 md:grid-cols-2">
        {imageUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={imageUrl}
            alt=""
            className="aspect-[4/3] rounded-2xl object-cover shadow-xl ring-1 ring-gray-200"
          />
        ) : (
          <div className="aspect-[4/3] rounded-2xl bg-gradient-to-br from-blue-100 to-blue-50 ring-1 ring-blue-100" />
        )}
        <div>
          {heading ? (
            <h2 className="text-3xl font-semibold tracking-tight text-gray-900">
              {heading}
            </h2>
          ) : null}
          {body ? (
            <div className="mt-5 space-y-4 text-gray-600">
              {body.split(/\n\n+/).map((para, i) => (
                <p key={i}>{para}</p>
              ))}
            </div>
          ) : null}
        </div>
      </div>
    </section>
  )
}

function ServiceArea({
  heading,
  body,
}: {
  heading: string | null
  body: string | null
}) {
  return (
    <section id="service-area" className="mx-auto max-w-6xl px-6 py-20">
      <div className="max-w-3xl">
        {heading ? (
          <h2 className="text-3xl font-semibold tracking-tight text-gray-900">
            {heading}
          </h2>
        ) : null}
        {body ? (
          <div className="mt-5 space-y-4 text-gray-600">
            {body.split(/\n\n+/).map((para, i) => (
              <p key={i}>{para}</p>
            ))}
          </div>
        ) : null}
      </div>
    </section>
  )
}

function Contact({
  email,
  phone,
  address,
  hours,
}: {
  email: string | null
  phone: string | null
  address: string | null
  hours: string | null
}) {
  return (
    <section id="contact" className="bg-blue-700 text-white">
      <div className="mx-auto max-w-6xl px-6 py-20">
        <div className="grid grid-cols-1 gap-10 md:grid-cols-3">
          <div className="md:col-span-1">
            <h2 className="text-3xl font-semibold tracking-tight">
              Get in touch
            </h2>
            <p className="mt-3 text-blue-100">
              Tell us about your project. We respond to most inquiries within
              one business day.
            </p>
          </div>
          <dl className="grid grid-cols-1 gap-6 md:col-span-2 sm:grid-cols-2">
            {phone ? (
              <ContactRow icon={<PhoneIcon className="size-5" />} label="Phone">
                <a href={`tel:${phone.replace(/[^+\d]/g, '')}`} className="hover:text-white">
                  {phone}
                </a>
              </ContactRow>
            ) : null}
            {email ? (
              <ContactRow
                icon={<EnvelopeIcon className="size-5" />}
                label="Email"
              >
                <a href={`mailto:${email}`} className="hover:text-white">
                  {email}
                </a>
              </ContactRow>
            ) : null}
            {address ? (
              <ContactRow icon={<MapPinIcon className="size-5" />} label="Office">
                {address}
              </ContactRow>
            ) : null}
            {hours ? (
              <ContactRow label="Hours" icon={null}>
                {hours}
              </ContactRow>
            ) : null}
          </dl>
        </div>
      </div>
    </section>
  )
}

function ContactRow({
  icon,
  label,
  children,
}: {
  icon: React.ReactNode
  label: string
  children: React.ReactNode
}) {
  return (
    <div className="flex gap-3">
      {icon ? (
        <div className="mt-0.5 text-blue-200" aria-hidden>
          {icon}
        </div>
      ) : (
        <div className="mt-0.5 size-5 shrink-0" aria-hidden />
      )}
      <div>
        <dt className="text-xs font-medium tracking-wide text-blue-200 uppercase">
          {label}
        </dt>
        <dd className="mt-0.5 text-base text-blue-50">{children}</dd>
      </div>
    </div>
  )
}

function SiteFooter({
  tagline,
  copyright,
}: {
  tagline: string | null
  copyright: string | null
}) {
  return (
    <footer className="bg-gray-900 text-gray-400">
      <div className="mx-auto flex max-w-6xl flex-col items-start gap-3 px-6 py-10 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm">{tagline}</p>
        <p className="text-xs">{copyright}</p>
      </div>
    </footer>
  )
}
