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

import { useEffect, useState } from "react";
import { browserSupportsWebAuthn, startRegistration } from "@simplewebauthn/browser";
import { api } from "../api";

/**
 * Shown to any signed-in user who has no passkey yet, on every visit, until
 * they add one — passkeys are the first-class sign-in method and the emailed
 * link is meant as the fallback. Hidden entirely on devices without WebAuthn.
 */
export default function PasskeyNudge() {
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!browserSupportsWebAuthn()) return;
    api.account.passkeys
      .list()
      .then((list) => setShow(list.length === 0))
      .catch(() => {});
  }, []);

  if (!show) return null;

  const add = async () => {
    setBusy(true);
    setError(null);
    try {
      const options = await api.account.passkeys.registerOptions();
      const credential = await startRegistration({ optionsJSON: options as any });
      await api.account.passkeys.registerVerify(credential, "");
      setShow(false);
    } catch (e: any) {
      setError(
        e?.name === "NotAllowedError"
          ? "Prompt dismissed — you can add one any time"
          : e.response?.data?.detail || "Could not add a passkey"
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed top-3 left-1/2 -translate-x-1/2 z-50 w-[min(560px,calc(100vw-2rem))]">
      <div className="bg-indigo-600 text-white rounded-xl shadow-lg px-4 py-3 flex items-center gap-3">
        <span className="text-xl">🔑</span>
        <div className="flex-1 text-sm">
          <span className="font-semibold">Add a passkey</span> — sign in instantly with your
          fingerprint, face, or PIN instead of waiting for an email.
          {error && <span className="block text-xs text-indigo-200 mt-0.5">{error}</span>}
        </div>
        <button
          onClick={add}
          disabled={busy}
          className="px-3 py-1.5 bg-white text-indigo-700 rounded-lg text-xs font-semibold hover:bg-indigo-50 disabled:opacity-60 whitespace-nowrap"
        >
          {busy ? "Follow the prompt…" : "Add passkey"}
        </button>
        <button
          onClick={() => setShow(false)}
          className="text-indigo-200 hover:text-white text-lg leading-none"
          title="Not now"
        >
          ×
        </button>
      </div>
    </div>
  );
}
