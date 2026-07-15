import { SiteFooter } from '@/components/marketing/SiteFooter'
import { SiteHeader } from '@/components/marketing/SiteHeader'
import { getStorefrontPublic } from '@/lib/api/storefront'

export const metadata = {
  title: 'SMS Terms & Conditions · Brenk Facility Services',
  description:
    'Terms and conditions for the Brenk Facility Services work-order dispatch text-messaging program.',
}

const EFFECTIVE_DATE = 'July 5, 2026'

/**
 * Public SMS program terms at the bare domain (`/sms-terms`, rewritten to
 * `/marketing/sms-terms` by proxy.ts). Companion page to /privacy for A2P
 * 10DLC campaign review: program description, frequency, STOP/HELP
 * keywords, rate disclosure, and carrier disclaimer. Static copy.
 */
export default async function SmsTermsPage() {
  const content = await getStorefrontPublic()

  return (
    <>
      <SiteHeader logoUrl={content.logo_url} />

      <main className="mx-auto w-full max-w-[820px] px-5 py-16 sm:px-8 sm:py-20">
        <h1 className="font-display text-[clamp(34px,5vw,52px)] leading-[1.04] font-extrabold tracking-[-0.02em] text-ink">
          SMS Terms &amp; Conditions
        </h1>
        <p className="mt-3 font-mono-brand text-[12.5px] tracking-[0.06em] text-signal uppercase">
          Effective {EFFECTIVE_DATE}
        </p>

        <div className="mt-10 space-y-8 text-[16px] leading-relaxed text-slate-body">
          <Section heading="Program description">
            <p>
              Brenk Facility Services, LLC sends work-order dispatch text
              messages (SMS/MMS) to its contracted subcontractors who have
              agreed to receive them. Messages relate to jobs you are hired to
              perform and may include the job location, work description,
              site-access details, and job-site photos. This is not a
              marketing program. See{' '}
              <a href="/sms-consent" className="text-signal underline hover:text-signal-ink">
                SMS Consent &amp; Opt-In
              </a>{' '}
              for how subcontractors opt in.
            </p>
          </Section>

          <Section heading="Message frequency">
            <p>
              Message frequency varies with job volume; a typical recipient
              receives 0–5 messages per week.
            </p>
          </Section>

          <Section heading="Fees">
            <p>
              Message and data rates may apply according to your mobile
              carrier plan. Brenk Facility Services does not charge for the
              messages.
            </p>
          </Section>

          <Section heading="Opting out">
            <p>
              Reply <strong className="text-ink">STOP</strong> at any time to stop receiving
              messages. After you opt out, you will receive one final message
              confirming your removal. You can also opt out by contacting us
              directly at{' '}
              <a href="tel:5123692719" className="text-signal underline hover:text-signal-ink">
                (512) 369-2719
              </a>
              .
            </p>
          </Section>

          <Section heading="Help">
            <p>
              Reply <strong className="text-ink">HELP</strong> for help, call{' '}
              <a href="tel:5123692719" className="text-signal underline hover:text-signal-ink">
                (512) 369-2719
              </a>
              , or email{' '}
              <a
                href="mailto:daryl@brenkfacilityservices.com"
                className="text-signal underline hover:text-signal-ink"
              >
                daryl@brenkfacilityservices.com
              </a>
              .
            </p>
          </Section>

          <Section heading="Carriers">
            <p>
              Supported carriers include all major U.S. carriers. Carriers are
              not liable for delayed or undelivered messages.
            </p>
          </Section>

          <Section heading="Privacy">
            <p>
              Mobile phone numbers and SMS consent are never sold or shared
              with third parties for marketing purposes. See our{' '}
              <a href="/privacy" className="text-signal underline hover:text-signal-ink">
                Privacy Policy
              </a>{' '}
              for details on how we handle personal information.
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
