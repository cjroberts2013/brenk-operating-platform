import { SiteFooter } from '@/components/marketing/SiteFooter'
import { SiteHeader } from '@/components/marketing/SiteHeader'
import { getStorefrontPublic } from '@/lib/api/storefront'

export const metadata = {
  title: 'SMS Consent & Opt-In · Brenk Facility Services',
  description:
    'How Brenk Facility Services subcontractors opt in to work-order dispatch text messages — the consent workflow, the exact consent statement, and how to opt out.',
}

const EFFECTIVE_DATE = 'July 15, 2026'

/**
 * Public SMS opt-in / consent workflow page (`/sms-consent`, rewritten to
 * `/marketing/sms-consent` by proxy.ts). Purpose-built as the "Opt-in
 * policy proof" artifact for carrier messaging verification (toll-free /
 * A2P): it documents the exact point and language by which a subcontractor
 * consents to receive dispatch texts, since consent is collected at
 * onboarding rather than through a public web form. Static copy.
 */
export default async function SmsConsentPage() {
  const content = await getStorefrontPublic()

  return (
    <>
      <SiteHeader logoUrl={content.logo_url} />

      <main className="mx-auto w-full max-w-[820px] px-5 py-16 sm:px-8 sm:py-20">
        <h1 className="font-display text-[clamp(34px,5vw,52px)] leading-[1.04] font-extrabold tracking-[-0.02em] text-ink">
          SMS Consent &amp; Opt-In
        </h1>
        <p className="mt-3 font-mono-brand text-[12.5px] tracking-[0.06em] text-signal uppercase">
          Effective {EFFECTIVE_DATE}
        </p>

        <div className="mt-10 space-y-8 text-[16px] leading-relaxed text-slate-body">
          <Section heading="Who receives messages">
            <p>
              Brenk Facility Services, LLC sends work-order dispatch text
              messages only to its own contracted subcontractors — a fixed
              group of roughly 12–20 tradespeople we hire to perform
              facility-maintenance jobs. We do not text the general public,
              and numbers are never purchased, rented, or obtained from third
              parties. Every recipient has a direct, ongoing business
              relationship with us.
            </p>
          </Section>

          <Section heading="How subcontractors opt in">
            <p>
              Consent is collected directly by the business owner during
              subcontractor onboarding, before any message is sent. When a
              subcontractor begins working with Brenk Facility Services, they
              provide their mobile number and are told they will receive
              work-order dispatch texts for the jobs they are hired to
              perform. They verbally agree to receive these messages, and
              their consent is recorded in our vendor records. Providing a
              mobile number and agreeing to dispatch texts is not a condition
              of being hired for any specific job.
            </p>
          </Section>

          <Section heading="What a subcontractor agrees to">
            <blockquote className="border-l-4 border-signal/40 bg-mist px-5 py-4 text-[15.5px] text-ink">
              &ldquo;I agree to receive work-order dispatch text messages
              (SMS/MMS) from Brenk Facility Services about jobs I am hired to
              perform. These messages may include the work-order number, job
              location, work description, site-access details, and job-site
              photos. Message frequency is typically 0–5 messages per week.
              Message and data rates may apply. I can opt out at any time by
              replying STOP.&rdquo;
            </blockquote>
          </Section>

          <Section heading="What we send">
            <p>
              Messages are one-to-one, transactional dispatch notifications:
              the work-order number, job location, work description,
              site-access details (such as gate codes), and job-site photos.
              No marketing, advertising, or promotional content is ever sent.
            </p>
          </Section>

          <Section heading="Opting out">
            <p>
              Recipients may opt out at any time by replying{' '}
              <strong className="text-ink">STOP</strong>, and their number is
              removed from the dispatch list. Reply{' '}
              <strong className="text-ink">HELP</strong> for help, or contact
              us at{' '}
              <a href="tel:5123692719" className="text-signal underline hover:text-signal-ink">
                (512) 369-2719
              </a>
              {' '}or{' '}
              <a
                href="mailto:daryl@brenkfacilityservices.com"
                className="text-signal underline hover:text-signal-ink"
              >
                daryl@brenkfacilityservices.com
              </a>
              .
            </p>
          </Section>

          <Section heading="Privacy & terms">
            <p>
              Mobile numbers and SMS consent are never sold or shared with
              third parties for marketing. See our{' '}
              <a href="/sms-terms" className="text-signal underline hover:text-signal-ink">
                SMS Terms &amp; Conditions
              </a>{' '}
              and{' '}
              <a href="/privacy" className="text-signal underline hover:text-signal-ink">
                Privacy Policy
              </a>{' '}
              for full details.
            </p>
          </Section>
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
