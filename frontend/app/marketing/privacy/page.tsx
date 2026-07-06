import { SiteFooter } from '@/components/marketing/SiteFooter'
import { SiteHeader } from '@/components/marketing/SiteHeader'
import { getStorefrontPublic } from '@/lib/api/storefront'

export const metadata = {
  title: 'Privacy Policy · Brenk Facility Services',
  description:
    'How Brenk Facility Services collects, uses, and protects personal information, including SMS/text-messaging consent and data.',
}

const EFFECTIVE_DATE = 'July 5, 2026'

/**
 * Public privacy policy at the bare domain (`/privacy`, rewritten to
 * `/marketing/privacy` by proxy.ts). Written to satisfy carrier A2P 10DLC
 * campaign review, which requires the policy to state that mobile numbers
 * are not shared with third parties, note message frequency, and include a
 * "message and data rates may apply" disclosure. Static copy — edit here.
 */
export default async function PrivacyPage() {
  const content = await getStorefrontPublic()

  return (
    <>
      <SiteHeader logoUrl={content.logo_url} />

      <main className="mx-auto w-full max-w-[820px] px-5 py-16 sm:px-8 sm:py-20">
        <h1 className="font-display text-[clamp(34px,5vw,52px)] leading-[1.04] font-extrabold tracking-[-0.02em] text-ink">
          Privacy Policy
        </h1>
        <p className="mt-3 font-mono-brand text-[12.5px] tracking-[0.06em] text-signal uppercase">
          Effective {EFFECTIVE_DATE}
        </p>

        <div className="mt-10 space-y-8 text-[16px] leading-relaxed text-slate-body">
          <p>
            Brenk Facility Services, LLC (&ldquo;Brenk,&rdquo; &ldquo;we,&rdquo;
            &ldquo;us&rdquo;) is a family-owned facility services company based in
            Austin, Texas. This policy describes the personal information we
            collect, how we use it, and the choices you have.
          </p>

          <Section heading="Information we collect">
            <ul className="list-disc space-y-2 pl-6">
              <li>
                <strong className="text-ink">Quote requests:</strong> when you
                submit our &ldquo;Request a Quote&rdquo; form, we collect the
                contact details and project information you provide (such as
                name, email address, phone number, and a description of the
                work).
              </li>
              <li>
                <strong className="text-ink">Business contacts and
                subcontractors:</strong> we keep contact information (name,
                phone number, email address, trade specialties) for the
                clients we serve and the subcontractors we dispatch work to.
              </li>
            </ul>
          </Section>

          <Section heading="How we use information">
            <p>
              We use this information solely to operate our business: to respond
              to quote requests, coordinate and dispatch facility-maintenance
              work, communicate about active jobs, and invoice for completed
              work. We do not sell personal information, and we do not use it
              for third-party advertising.
            </p>
          </Section>

          <Section heading="Text messaging (SMS/MMS)">
            <p>
              With consent, we send work-order dispatch text messages to our
              contracted subcontractors. These are one-to-one, transactional
              messages about jobs you are hired to perform — job location, work
              description, site-access details, and job-site photos. Typical
              frequency is 0–5 messages per week, varying with job volume.
            </p>
            <ul className="mt-3 list-disc space-y-2 pl-6">
              <li>
                <strong className="text-ink">
                  Mobile phone numbers and SMS consent are never sold or shared
                  with third parties or affiliates for marketing or promotional
                  purposes.
                </strong>{' '}
                Text messaging originator opt-in data will not be shared with
                any third party, except with service providers acting on our
                behalf solely to deliver the messages (e.g., our SMS provider).
              </li>
              <li>Message and data rates may apply.</li>
              <li>
                You can opt out at any time by replying <strong className="text-ink">STOP</strong>,
                or reply <strong className="text-ink">HELP</strong> for help. You may also contact us
                directly using the information below. See our{' '}
                <a href="/sms-terms" className="text-signal underline hover:text-signal-ink">
                  SMS Terms &amp; Conditions
                </a>{' '}
                for full details.
              </li>
            </ul>
          </Section>

          <Section heading="Data retention and security">
            <p>
              We retain business records for as long as needed to operate the
              business and meet legal and accounting obligations. Access to our
              systems is limited to authorized personnel and protected by
              authentication.
            </p>
          </Section>

          <Section heading="Your choices">
            <p>
              To ask what information we hold about you, request a correction or
              deletion, or opt out of communications, contact us and we will
              respond promptly.
            </p>
          </Section>

          <Section heading="Contact us">
            <p>
              Brenk Facility Services, LLC — Austin, TX
              <br />
              Phone: <a href="tel:5123692719" className="text-signal underline hover:text-signal-ink">(512) 369-2719</a>
              <br />
              Email:{' '}
              <a
                href="mailto:daryl@brenkfacilityservices.com"
                className="text-signal underline hover:text-signal-ink"
              >
                daryl@brenkfacilityservices.com
              </a>
            </p>
          </Section>

          <p className="text-[14px] text-slate-body/80">
            We may update this policy from time to time; the effective date
            above reflects the latest revision.
          </p>
        </div>
      </main>

      <SiteFooter
        tagline={content.footer_tagline}
        copyright={content.footer_copyright}
      />
    </>
  )
}

function Section({
  heading,
  children,
}: {
  heading: string
  children: React.ReactNode
}) {
  return (
    <section>
      <h2 className="font-display text-[22px] leading-tight font-extrabold tracking-[-0.01em] text-ink">
        {heading}
      </h2>
      <div className="mt-3">{children}</div>
    </section>
  )
}
