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

import { useState } from "react";
import { browserSupportsWebAuthn, startAuthentication } from "@simplewebauthn/browser";
import { api } from "../api";
import type { User } from "../types";

interface Props {
  onAuthed: (user: User, isNew: boolean) => void;
}

type Mode = "login" | "signup";

function pendingLoginToken(): string | null {
  return new URLSearchParams(window.location.search).get("login_token");
}

export default function AuthScreen({ onAuthed }: Props) {
  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [inviteCode, setInviteCode] = useState("");
  const [linkSent, setLinkSent] = useState(false);
  const [loginToken] = useState<string | null>(pendingLoginToken);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const passkeysAvailable = browserSupportsWebAuthn();

  const finish = (user: User, isNew: boolean) => {
    // Drop any ?login_token= from the address bar before entering the app
    window.history.replaceState({}, "", window.location.pathname === "/privacy" ? "/" : window.location.pathname);
    onAuthed(user, isNew);
  };

  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
    } catch (err: any) {
      if (err?.name === "NotAllowedError") {
        setError("Passkey prompt was dismissed — try again when you're ready");
      } else {
        setError(err.response?.data?.detail || "Something went wrong — please try again");
      }
    } finally {
      setBusy(false);
    }
  };

  const completeLinkSignIn = () =>
    run(async () => {
      const user = await api.account.verifyMagicLink(loginToken!);
      finish(user, false);
    });

  const sendLink = (e: React.FormEvent) => {
    e.preventDefault();
    run(async () => {
      await api.account.requestMagicLink(email);
      setLinkSent(true);
    });
  };

  const passkeySignIn = () =>
    run(async () => {
      const { challenge_id, options } = await api.account.passkeys.loginOptions();
      const credential = await startAuthentication({ optionsJSON: options as any });
      const user = await api.account.passkeys.loginVerify(challenge_id, credential);
      finish(user, false);
    });

  const signup = (e: React.FormEvent) => {
    e.preventDefault();
    run(async () => {
      const user = await api.account.signup(inviteCode, email);
      finish(user, true);
    });
  };

  const inputClass =
    "w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500";
  const primaryButton =
    "w-full py-2.5 bg-brand-600 text-white rounded-lg text-sm font-semibold hover:bg-brand-700 disabled:opacity-50 transition-colors";
  const secondaryButton =
    "w-full py-2.5 border border-gray-300 text-gray-700 rounded-lg text-sm font-semibold hover:bg-gray-50 disabled:opacity-50 transition-colors";

  // Arrived via an emailed sign-in link: confirm with a click rather than
  // signing in automatically, so an email scanner that opens the URL
  // can't consume the link.
  if (loginToken) {
    return (
      <Shell>
        <div className="bg-white rounded-2xl shadow-2xl p-8 text-center">
          <h2 className="text-lg font-semibold text-gray-900">Finish signing in</h2>
          <p className="text-sm text-gray-500 mt-2 mb-6">
            You followed a sign-in link from your email. One more click and you're in.
          </p>
          {error && <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2 mb-4">{error}</p>}
          <button onClick={completeLinkSignIn} disabled={busy} className={primaryButton}>
            {busy ? "One moment…" : "Sign in to vibepost"}
          </button>
          <button
            onClick={() => { window.history.replaceState({}, "", "/"); window.location.reload(); }}
            className="mt-3 text-xs text-gray-400 hover:text-gray-600 underline"
          >
            Cancel
          </button>
        </div>
      </Shell>
    );
  }

  if (linkSent) {
    return (
      <Shell>
        <div className="bg-white rounded-2xl shadow-2xl p-8 text-center">
          <div className="text-3xl mb-3">📬</div>
          <h2 className="text-lg font-semibold text-gray-900">Check your email</h2>
          <p className="text-sm text-gray-500 mt-2">
            If <span className="font-medium text-gray-700">{email}</span> has an account,
            a sign-in link is on its way. It works once and expires in 15 minutes.
          </p>
          <button
            onClick={() => setLinkSent(false)}
            className="mt-6 text-xs text-gray-400 hover:text-gray-600 underline"
          >
            Back
          </button>
        </div>
      </Shell>
    );
  }

  return (
    <Shell>
      <div className="bg-white rounded-2xl shadow-2xl p-8">
        <div className="flex gap-1 bg-gray-100 rounded-lg p-1 mb-6">
          {(["login", "signup"] as Mode[]).map((m) => (
            <button
              key={m}
              onClick={() => { setMode(m); setError(null); }}
              className={`flex-1 py-2 rounded-md text-sm font-medium transition-colors ${
                mode === m ? "bg-white text-gray-900 shadow" : "text-gray-500 hover:text-gray-700"
              }`}
            >
              {m === "login" ? "Sign in" : "Create account"}
            </button>
          ))}
        </div>

        {mode === "login" ? (
          <>
            {passkeysAvailable && (
              <>
                <button onClick={passkeySignIn} disabled={busy} className={primaryButton}>
                  🔑 Sign in with a passkey
                </button>
                <div className="flex items-center gap-3 my-4">
                  <div className="flex-1 h-px bg-gray-200" />
                  <span className="text-[11px] text-gray-400 uppercase tracking-wide">
                    or get a link by email
                  </span>
                  <div className="flex-1 h-px bg-gray-200" />
                </div>
              </>
            )}

            <form onSubmit={sendLink} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Email</label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  required
                  autoComplete="email"
                  className={inputClass}
                />
              </div>

              {error && <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</p>}

              <button
                type="submit"
                disabled={busy}
                className={passkeysAvailable ? secondaryButton : primaryButton}
              >
                {busy ? "One moment…" : "Email me a sign-in link"}
              </button>
            </form>
          </>
        ) : (
          <>
            <p className="text-xs text-gray-500 mb-4">
              vibepost is in closed beta. You need an invite code from whoever runs this
              instance — if you don't have one, ask them for an invite.
            </p>
            <form onSubmit={signup} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Invite code</label>
                <input
                  value={inviteCode}
                  onChange={(e) => setInviteCode(e.target.value)}
                  placeholder="Paste your invite code"
                  required
                  autoComplete="off"
                  className={`${inputClass} font-mono`}
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Email</label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  required
                  autoComplete="email"
                  className={inputClass}
                />
                <p className="text-[11px] text-gray-400 mt-1">
                  There are no passwords. You'll sign in with a passkey (recommended) or a
                  link sent to this address. Email is used only for signing in and to tell
                  you if a scheduled post fails — never for marketing, and it's encrypted at
                  rest. See our <a href="/privacy" className="underline">privacy policy</a>.
                </p>
              </div>

              {error && <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</p>}

              <button type="submit" disabled={busy} className={primaryButton}>
                {busy ? "One moment…" : "Create account"}
              </button>
            </form>
          </>
        )}
      </div>
    </Shell>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-gray-900 via-indigo-950 to-gray-900 px-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-white tracking-tight">vibepost</h1>
          <p className="text-indigo-300 mt-2 text-sm">
            Write once, post everywhere. Your content, your accounts, your schedule.
          </p>
        </div>
        {children}
        <p className="text-center text-xs text-indigo-400/60 mt-6">
          <a href="/privacy" className="hover:text-indigo-300 underline">Privacy</a>
          {" · "}
          <a
            href="https://github.com/DocSunset/vibepost"
            target="_blank"
            rel="noreferrer"
            className="hover:text-indigo-300 underline"
          >
            Free software (GPLv3)
          </a>
        </p>
      </div>
    </div>
  );
}
