// vibepost - social media scheduling and posting tool
// Copyright (C) 2026  Travis West
//
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU General Public License for more details.
//
// You should have received a copy of the GNU General Public License
// along with this program.  If not, see <https://www.gnu.org/licenses/>.

export default function PrivacyPolicy() {
  return (
    <div className="min-h-screen bg-gray-50 py-12 px-4">
      <div className="max-w-2xl mx-auto bg-white rounded-2xl border border-gray-200 p-8 prose-sm">
        <a href="/" className="text-sm text-brand-600 hover:underline">← Back to vibepost</a>
        <h1 className="text-2xl font-bold text-gray-900 mt-4 mb-1">Privacy Policy</h1>
        <p className="text-xs text-gray-400 mb-6">Closed beta · Last updated June 2026</p>

        <div className="space-y-5 text-sm text-gray-600">
          <p>
            vibepost is a tool, not a data business. We store only what is needed to schedule
            and publish your posts, keep it only as long as needed, and treat everything as
            yours, not ours.
          </p>

          <section>
            <h2 className="font-semibold text-gray-900 mb-1">What we store, and why</h2>
            <ul className="list-disc pl-5 space-y-1">
              <li>
                <strong>Email address</strong> — to send you single-use sign-in links and to
                contact you about failures or security issues. Sign-in emails go through our
                email provider (Resend); we send nothing else. Never used for marketing, never
                shared, never sold.
              </li>
              <li>
                <strong>Passkey public keys, and a password hash if you choose to set a
                password</strong> — to sign you in. A passkey's private key never leaves your
                device; we only ever hold the public half, which is useless to anyone else.
              </li>
              <li>
                <strong>Social platform credentials</strong> (OAuth tokens, Bluesky app
                passwords) — to post on your behalf. We request only posting permissions, not
                your followers, messages, or analytics. Deleted immediately when you disconnect
                a channel or delete your account.
              </li>
              <li>
                <strong>Your posts</strong> (text and media) — so we can publish them at the
                scheduled time. They stay until you delete them; deleting a post also deletes
                its media files from our server.
              </li>
              <li>
                <strong>Server logs</strong> (IP address, request path, timestamp) — for
                diagnosing errors and detecting abuse, kept on a short rolling window, then
                discarded. Post content is never written to logs.
              </li>
            </ul>
          </section>

          <section>
            <h2 className="font-semibold text-gray-900 mb-1">What we deliberately don't collect</h2>
            <p>
              No name, phone number, date of birth, or location. No tracking pixels, no
              third-party analytics, no advertising identifiers, no cookies other than the one
              that keeps you signed in.
            </p>
          </section>

          <section>
            <h2 className="font-semibold text-gray-900 mb-1">Who we share data with</h2>
            <p>
              The social platforms you explicitly connect and post to (that sharing is the whole
              point of the service), our hosting infrastructure provider, and our email provider
              (Resend), which sees your address and the sign-in emails we send you — nothing
              else. Nothing is shared with data brokers, advertisers, or analytics companies.
            </p>
          </section>

          <section>
            <h2 className="font-semibold text-gray-900 mb-1">Your rights</h2>
            <ul className="list-disc pl-5 space-y-1">
              <li>
                <strong>Access &amp; portability:</strong> Settings → Account → &ldquo;Export my
                data&rdquo; gives you everything we hold, as JSON, any time.
              </li>
              <li>
                <strong>Erasure:</strong> Settings → Account → &ldquo;Delete account&rdquo;
                immediately and permanently removes your account, profiles, credentials, posts,
                and media. No archive is kept. Log entries age out on their rolling window.
              </li>
              <li>
                <strong>Withdrawal:</strong> disconnecting a channel immediately deletes its
                stored credential.
              </li>
            </ul>
          </section>

          <section>
            <h2 className="font-semibold text-gray-900 mb-1">Legal basis (GDPR)</h2>
            <p>
              We process your data to perform the contract you signed up for (scheduling and
              publishing posts), and keep short-lived server logs under legitimate interest for
              security. We do not rely on consent for core processing, and there is nothing
              here that needs a cookie banner.
            </p>
          </section>

          <section>
            <h2 className="font-semibold text-gray-900 mb-1">Contact</h2>
            <p>
              Questions, or a request you can't fulfil through the app? Email{" "}
              <a href="mailto:westerncompass@gmail.com" className="text-brand-600 underline">
                westerncompass@gmail.com
              </a>
              .
            </p>
          </section>

          <p className="text-xs text-gray-400 pt-2 border-t border-gray-100">
            vibepost is free software (GPLv3) — you can read exactly what the code does at{" "}
            <a href="https://github.com/DocSunset/vibepost" className="underline">
              github.com/DocSunset/vibepost
            </a>
            .
          </p>
        </div>
      </div>
    </div>
  );
}
