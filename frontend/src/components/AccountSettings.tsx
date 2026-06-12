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
import { startRegistration } from "@simplewebauthn/browser";
import { api } from "../api";
import type { Invite, Passkey, User } from "../types";

interface Props {
  user: User;
  onLoggedOut: () => void;
  onError: (msg: string) => void;
  onSuccess: (msg: string) => void;
}

export default function AccountSettings({ user, onLoggedOut, onError, onSuccess }: Props) {
  // Passkeys
  const [passkeys, setPasskeys] = useState<Passkey[]>([]);
  const [addingPasskey, setAddingPasskey] = useState(false);

  // Admin invite state
  const [invites, setInvites] = useState<Invite[]>([]);
  const [inviteNote, setInviteNote] = useState("");
  const [newToken, setNewToken] = useState<string | null>(null);

  useEffect(() => {
    if (user.is_admin) {
      api.account.invites.list().then(setInvites).catch(() => {});
    }
    api.account.passkeys.list().then(setPasskeys).catch(() => {});
  }, [user.is_admin]);

  const revokeSessions = async () => {
    if (!confirm("Sign out everywhere? Every other device and browser will need to sign in again. You stay signed in here.")) return;
    try {
      await api.account.revokeSessions();
      onSuccess("All other sessions signed out");
    } catch {
      onError("Could not revoke sessions");
    }
  };

  const addPasskey = async () => {
    setAddingPasskey(true);
    try {
      const options = await api.account.passkeys.registerOptions();
      const credential = await startRegistration({ optionsJSON: options as any });
      const label = prompt("Name this passkey (e.g. \"laptop\", \"phone\"):") || "";
      await api.account.passkeys.registerVerify(credential, label);
      setPasskeys(await api.account.passkeys.list());
      onSuccess("Passkey added — you can now sign in with it");
    } catch (e: any) {
      if (e?.name === "NotAllowedError") {
        onError("Passkey prompt was dismissed");
      } else {
        onError(e.response?.data?.detail || "Could not add passkey");
      }
    } finally {
      setAddingPasskey(false);
    }
  };

  const removePasskey = async (id: number) => {
    if (!confirm("Remove this passkey? You won't be able to sign in with it anymore.")) return;
    try {
      await api.account.passkeys.delete(id);
      setPasskeys(await api.account.passkeys.list());
    } catch {
      onError("Could not remove passkey");
    }
  };

  const exportData = async () => {
    try {
      const data = await api.account.exportData();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "vibepost-export.json";
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      onError("Export failed");
    }
  };

  const deleteAccount = async () => {
    if (!confirm("Delete your account? This permanently removes your profiles, connected accounts, scheduled posts, and uploaded media. This cannot be undone.")) return;
    if (!confirm("Really delete everything? Last chance.")) return;
    try {
      await api.account.deleteAccount();
      onLoggedOut();
    } catch {
      onError("Account deletion failed — please contact the operator");
    }
  };

  const logout = async () => {
    try {
      await api.account.logout();
    } finally {
      onLoggedOut();
    }
  };

  const createInvite = async () => {
    try {
      const res = await api.account.invites.create(inviteNote);
      setNewToken(res.token);
      setInviteNote("");
      setInvites(await api.account.invites.list());
    } catch {
      onError("Could not create invite");
    }
  };

  const revokeInvite = async (id: number) => {
    try {
      await api.account.invites.revoke(id);
      setInvites(await api.account.invites.list());
    } catch {
      onError("Could not revoke invite");
    }
  };

  return (
    <>
      <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden mb-6">
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
          <h2 className="font-semibold text-gray-900">Account</h2>
          <button onClick={logout} className="text-xs text-gray-400 hover:text-gray-700">
            Sign out
          </button>
        </div>
        <div className="px-6 py-5 space-y-6">
          <p className="text-sm text-gray-600">
            Signed in as <span className="font-medium">{user.email}</span>
            {user.is_admin && <span className="ml-2 text-xs bg-brand-100 text-brand-700 px-2 py-0.5 rounded-full">admin</span>}
          </p>

          <div>
            <p className="text-xs font-medium text-gray-500 mb-2">Passkeys</p>
            <p className="text-xs text-gray-400 mb-3">
              The fastest, safest way to sign in — your device's fingerprint, face, or PIN.
              No password, nothing to phish.
            </p>
            {passkeys.length > 0 && (
              <div className="space-y-1 mb-3">
                {passkeys.map((p) => (
                  <div key={p.id} className="flex items-center gap-3 text-sm py-1">
                    <span>🔑</span>
                    <span className="text-gray-700 flex-1 truncate">{p.label}</span>
                    <span className="text-xs text-gray-400">
                      {p.last_used_at
                        ? `last used ${new Date(p.last_used_at + "Z").toLocaleDateString()}`
                        : "never used"}
                    </span>
                    <button
                      onClick={() => removePasskey(p.id)}
                      className="text-xs text-gray-400 hover:text-red-500"
                    >
                      Remove
                    </button>
                  </div>
                ))}
              </div>
            )}
            <button
              onClick={addPasskey}
              disabled={addingPasskey}
              className="px-4 py-2 bg-brand-600 text-white rounded-lg text-sm font-medium hover:bg-brand-700 disabled:opacity-50 transition-colors"
            >
              {addingPasskey ? "Follow your browser's prompt…" : "Add a passkey"}
            </button>
          </div>

          <div className="pt-2 border-t border-gray-100">
            <p className="text-xs text-gray-400">
              There are no passwords — sign-in is by passkey or emailed link.{" "}
              <button onClick={revokeSessions} className="underline hover:text-gray-600">
                Sign out everywhere
              </button>{" "}
              if you think a session may have been stolen.
            </p>
          </div>

          <div className="flex items-center gap-4 pt-2 border-t border-gray-100">
            <button onClick={exportData} className="text-sm text-brand-600 hover:underline">
              Export my data (JSON)
            </button>
            <span className="text-gray-200">|</span>
            <button onClick={deleteAccount} className="text-sm text-red-500 hover:underline">
              Delete account
            </button>
          </div>
          <p className="text-xs text-gray-400 -mt-3">
            Deletion is immediate and permanent: all profiles, credentials, posts, and media are
            removed. See the <a href="/privacy" className="underline">privacy policy</a>.
          </p>
        </div>
      </div>

      {user.is_admin && (
        <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden mb-6">
          <div className="px-6 py-4 border-b border-gray-100">
            <h2 className="font-semibold text-gray-900">Beta Invites</h2>
          </div>
          <div className="px-6 py-5 space-y-4">
            <div className="flex gap-2">
              <input
                value={inviteNote}
                onChange={(e) => setInviteNote(e.target.value)}
                placeholder="Note (who is this for?)"
                className="border border-gray-200 rounded-lg px-3 py-2 text-sm flex-1 focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
              <button
                onClick={createInvite}
                className="px-4 py-2 bg-brand-600 text-white rounded-lg text-sm font-medium hover:bg-brand-700 transition-colors"
              >
                New invite
              </button>
            </div>

            {newToken && (
              <div className="bg-green-50 border border-green-200 rounded-lg px-3 py-2">
                <p className="text-xs text-green-800 mb-1 font-medium">
                  Invite created — copy it now, it won't be shown again:
                </p>
                <div className="flex items-center gap-2">
                  <code className="text-xs text-green-900 flex-1 break-all">{newToken}</code>
                  <button
                    onClick={() => navigator.clipboard.writeText(newToken)}
                    className="text-xs text-green-700 font-medium hover:text-green-900"
                  >
                    Copy
                  </button>
                </div>
              </div>
            )}

            {invites.length > 0 && (
              <div className="space-y-1">
                {invites.map((i) => {
                  const state = i.revoked ? "revoked" : i.used_at ? "used" : "open";
                  return (
                    <div key={i.id} className="flex items-center gap-3 text-sm py-1">
                      <span
                        className={`text-xs px-2 py-0.5 rounded-full ${
                          state === "open"
                            ? "bg-amber-100 text-amber-700"
                            : state === "used"
                            ? "bg-green-100 text-green-700"
                            : "bg-gray-100 text-gray-500"
                        }`}
                      >
                        {state}
                      </span>
                      <span className="text-gray-600 flex-1 truncate">{i.note || "(no note)"}</span>
                      {state === "open" && (
                        <button
                          onClick={() => revokeInvite(i.id)}
                          className="text-xs text-gray-400 hover:text-red-500"
                        >
                          Revoke
                        </button>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
}
