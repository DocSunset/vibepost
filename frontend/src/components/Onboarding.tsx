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
import { api } from "../api";
import type { AppSettings, Channel, Profile } from "../types";

interface Props {
  onDone: () => void;
}

const AVATAR_COLORS = [
  "#6366f1", "#8b5cf6", "#ec4899", "#ef4444",
  "#f59e0b", "#10b981", "#06b6d4", "#3b82f6",
];

function StepDot({ n, active, done }: { n: number; active: boolean; done: boolean }) {
  return (
    <div
      className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-semibold ${
        done ? "bg-green-500 text-white" : active ? "bg-brand-600 text-white" : "bg-gray-200 text-gray-500"
      }`}
    >
      {done ? "✓" : n}
    </div>
  );
}

function CopyField({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="flex items-center gap-2 bg-gray-50 border border-gray-200 rounded-lg px-3 py-2">
      <code className="text-xs text-gray-700 flex-1 break-all">{value}</code>
      <button
        onClick={() => {
          navigator.clipboard.writeText(value);
          setCopied(true);
          setTimeout(() => setCopied(false), 1500);
        }}
        className="text-xs text-brand-600 hover:text-brand-700 font-medium flex-shrink-0"
      >
        {copied ? "Copied!" : "Copy"}
      </button>
    </div>
  );
}

export default function Onboarding({ onDone }: Props) {
  const [step, setStep] = useState(0);

  // Step 1: profile
  const [profileName, setProfileName] = useState("");
  const [profileColor, setProfileColor] = useState(AVATAR_COLORS[0]);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Step 2: connections
  const [settings, setSettings] = useState<Partial<AppSettings>>({});
  const [channels, setChannels] = useState<Channel[]>([]);
  const [openGuide, setOpenGuide] = useState<string | null>("bluesky");
  const [bskyHandle, setBskyHandle] = useState("");
  const [bskyPassword, setBskyPassword] = useState("");
  const [bskyBusy, setBskyBusy] = useState(false);
  const [bskyMsg, setBskyMsg] = useState<string | null>(null);

  useEffect(() => {
    api.auth.getSettings().then(setSettings).catch(() => {});
    // If the user already has a profile (e.g. returning mid-onboarding), pick it up
    api.profiles.list().then((list) => {
      if (list.length > 0) {
        setProfile(list[0]);
        setStep((s) => Math.max(s, 1));
        api.channels.list(list[0].id).then(setChannels).catch(() => {});
      }
    }).catch(() => {});
  }, []);

  const createProfile = async () => {
    if (!profileName.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const p = await api.profiles.create(profileName.trim(), profileColor);
      setProfile(p);
      setStep(1);
    } catch {
      setError("Could not create the profile — please try again");
    } finally {
      setBusy(false);
    }
  };

  const saveSettings = async () => {
    try {
      await api.auth.saveSettings(settings);
      const fresh = await api.auth.getSettings();
      setSettings(fresh);
    } catch {
      setError("Could not save credentials");
    }
  };

  const connectBluesky = async () => {
    if (!profile) return;
    setBskyBusy(true);
    setBskyMsg(null);
    try {
      await api.auth.connectBluesky(profile.id, bskyHandle.trim(), bskyPassword);
      setBskyHandle("");
      setBskyPassword("");
      setBskyMsg("Connected!");
      const list = await api.channels.list(profile.id);
      setChannels(list);
    } catch (e: any) {
      setBskyMsg(e.response?.data?.detail || "Connection failed — check handle and app password");
    } finally {
      setBskyBusy(false);
    }
  };

  const startOAuth = async (platform: "meta" | "threads" | "linkedin") => {
    if (!profile) return;
    await saveSettings();
    try {
      const data =
        platform === "meta"
          ? await api.auth.metaOAuthUrl(profile.id)
          : platform === "threads"
          ? await api.auth.threadsOAuthUrl(profile.id)
          : await api.auth.linkedinOAuthUrl(profile.id);
      window.location.href = data.url;
    } catch (e: any) {
      setError(e.response?.data?.detail || "Could not start the connection — did you save the App ID?");
    }
  };

  const uris = settings.oauth_redirect_uris;

  const guideHeader = (id: string, icon: string, title: string, difficulty: string) => (
    <button
      onClick={() => setOpenGuide(openGuide === id ? null : id)}
      className="w-full flex items-center gap-3 px-4 py-3 text-left"
    >
      <span className="text-xl">{icon}</span>
      <span className="font-medium text-gray-800 flex-1">{title}</span>
      {channels.some((c) => (id === "meta" ? c.platform === "facebook" || c.platform === "instagram" : c.platform === id)) && (
        <span className="text-xs text-green-600 font-medium">✓ connected</span>
      )}
      <span className="text-xs text-gray-400">{difficulty}</span>
      <span className="text-gray-400">{openGuide === id ? "▾" : "▸"}</span>
    </button>
  );

  const credentialInput = (key: keyof AppSettings, label: string) => (
    <div>
      <label className="block text-xs font-medium text-gray-500 mb-1">{label}</label>
      <input
        type={key.includes("secret") ? "password" : "text"}
        value={(settings[key] as string) ?? ""}
        onChange={(e) => setSettings((prev) => ({ ...prev, [key]: e.target.value }))}
        className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
      />
    </div>
  );

  return (
    <div className="min-h-screen bg-gray-50 py-10 px-4">
      <div className="max-w-2xl mx-auto">
        {/* Progress */}
        <div className="flex items-center justify-center gap-3 mb-8">
          <StepDot n={1} active={step === 0} done={step > 0} />
          <div className={`w-16 h-0.5 ${step > 0 ? "bg-green-500" : "bg-gray-200"}`} />
          <StepDot n={2} active={step === 1} done={step > 1} />
          <div className={`w-16 h-0.5 ${step > 1 ? "bg-green-500" : "bg-gray-200"}`} />
          <StepDot n={3} active={step === 2} done={false} />
        </div>

        {error && (
          <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2 mb-4">{error}</p>
        )}

        {/* Step 1: create a profile */}
        {step === 0 && (
          <div className="bg-white rounded-2xl border border-gray-200 p-8">
            <h1 className="text-2xl font-bold text-gray-900 mb-2">Welcome to vibepost 👋</h1>
            <p className="text-sm text-gray-500 mb-6">
              First, create a <strong>profile</strong>. A profile groups the social accounts you
              post to together — most people start with one for themselves or their brand. You
              can add more later.
            </p>
            <label className="block text-xs font-medium text-gray-500 mb-1">Profile name</label>
            <input
              value={profileName}
              onChange={(e) => setProfileName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && createProfile()}
              placeholder="e.g. Personal, or your brand's name"
              className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm mb-4 focus:outline-none focus:ring-2 focus:ring-brand-500"
              autoFocus
            />
            <p className="text-xs font-medium text-gray-500 mb-2">Pick a colour</p>
            <div className="flex gap-2 mb-6">
              {AVATAR_COLORS.map((c) => (
                <button
                  key={c}
                  onClick={() => setProfileColor(c)}
                  style={{ background: c }}
                  className={`w-8 h-8 rounded-full transition-transform ${
                    profileColor === c ? "scale-125 ring-2 ring-offset-2 ring-gray-400" : ""
                  }`}
                />
              ))}
            </div>
            <button
              onClick={createProfile}
              disabled={busy || !profileName.trim()}
              className="w-full py-2.5 bg-brand-600 text-white rounded-lg text-sm font-semibold hover:bg-brand-700 disabled:opacity-50 transition-colors"
            >
              Continue
            </button>
          </div>
        )}

        {/* Step 2: connect platforms */}
        {step === 1 && (
          <div className="bg-white rounded-2xl border border-gray-200 p-8">
            <h1 className="text-2xl font-bold text-gray-900 mb-2">Connect your accounts</h1>
            <p className="text-sm text-gray-500 mb-6">
              Connect at least one platform to start posting. Each platform needs slightly
              different credentials — the guides below walk you through getting them. You can
              always do this later from Settings.
            </p>

            <div className="space-y-3">
              {/* Bluesky */}
              <div className="border border-gray-200 rounded-xl overflow-hidden">
                {guideHeader("bluesky", "🦋", "Bluesky", "2 minutes")}
                {openGuide === "bluesky" && (
                  <div className="px-4 pb-4 space-y-3 border-t border-gray-100 pt-3">
                    <ol className="text-sm text-gray-600 space-y-2 list-decimal pl-5">
                      <li>
                        Open{" "}
                        <a href="https://bsky.app/settings/app-passwords" target="_blank" rel="noreferrer" className="text-brand-600 underline">
                          bsky.app → Settings → App Passwords
                        </a>
                      </li>
                      <li>Click <strong>Add App Password</strong>, name it &ldquo;vibepost&rdquo;, and copy the generated password.</li>
                      <li>Enter your handle and that app password below. Never use your main account password.</li>
                    </ol>
                    <div className="flex gap-2 flex-wrap">
                      <input
                        value={bskyHandle}
                        onChange={(e) => setBskyHandle(e.target.value)}
                        placeholder="yourname.bsky.social"
                        className="border border-gray-200 rounded-lg px-3 py-2 text-sm flex-1 min-w-[180px] focus:outline-none focus:ring-2 focus:ring-brand-500"
                      />
                      <input
                        type="password"
                        value={bskyPassword}
                        onChange={(e) => setBskyPassword(e.target.value)}
                        placeholder="xxxx-xxxx-xxxx-xxxx"
                        className="border border-gray-200 rounded-lg px-3 py-2 text-sm flex-1 min-w-[180px] focus:outline-none focus:ring-2 focus:ring-brand-500"
                      />
                      <button
                        onClick={connectBluesky}
                        disabled={bskyBusy || !bskyHandle || !bskyPassword}
                        className="px-4 py-2 bg-sky-500 text-white rounded-lg text-sm font-medium hover:bg-sky-600 disabled:opacity-50 transition-colors"
                      >
                        {bskyBusy ? "Connecting…" : "Connect"}
                      </button>
                    </div>
                    {bskyMsg && (
                      <p className={`text-xs ${bskyMsg === "Connected!" ? "text-green-600" : "text-red-600"}`}>{bskyMsg}</p>
                    )}
                  </div>
                )}
              </div>

              {/* Meta: Facebook + Instagram */}
              <div className="border border-gray-200 rounded-xl overflow-hidden">
                {guideHeader("meta", "📘", "Facebook + Instagram", "~15 minutes")}
                {openGuide === "meta" && (
                  <div className="px-4 pb-4 space-y-3 border-t border-gray-100 pt-3 text-sm text-gray-600">
                    <p className="text-xs bg-amber-50 text-amber-800 rounded-lg px-3 py-2">
                      During the beta you bring your own (free) Meta developer app. This takes a
                      few minutes once, then connecting is one click.
                    </p>
                    <ol className="space-y-2 list-decimal pl-5">
                      <li>
                        Go to{" "}
                        <a href="https://developers.facebook.com/apps/" target="_blank" rel="noreferrer" className="text-brand-600 underline">
                          developers.facebook.com/apps
                        </a>{" "}
                        and click <strong>Create App</strong> (type: <em>Business</em>).
                      </li>
                      <li>
                        In the app dashboard, add the <strong>Facebook Login for Business</strong> product, and under its settings paste
                        this as a <strong>Valid OAuth Redirect URI</strong>:
                        {uris?.meta && <CopyField value={uris.meta} />}
                      </li>
                      <li>
                        Make sure your app has access to the permissions{" "}
                        <code className="text-xs bg-gray-100 px-1 rounded">pages_manage_posts</code>,{" "}
                        <code className="text-xs bg-gray-100 px-1 rounded">pages_read_engagement</code> and{" "}
                        <code className="text-xs bg-gray-100 px-1 rounded">instagram_content_publish</code>{" "}
                        (in Development mode they work for accounts listed as app roles — add yourself).
                      </li>
                      <li>
                        Copy the <strong>App ID</strong> and <strong>App Secret</strong> from App Settings → Basic into the fields below.
                      </li>
                      <li>
                        Instagram posting requires an <strong>Instagram professional account</strong> linked to a Facebook Page.
                      </li>
                    </ol>
                    <div className="grid grid-cols-2 gap-3">
                      {credentialInput("meta_app_id", "Meta App ID")}
                      {credentialInput("meta_app_secret", "Meta App Secret")}
                    </div>
                    <button
                      onClick={() => startOAuth("meta")}
                      disabled={!settings.meta_app_id}
                      className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
                    >
                      Save &amp; connect via Facebook
                    </button>
                  </div>
                )}
              </div>

              {/* Threads */}
              <div className="border border-gray-200 rounded-xl overflow-hidden">
                {guideHeader("threads", "🧵", "Threads", "~10 minutes")}
                {openGuide === "threads" && (
                  <div className="px-4 pb-4 space-y-3 border-t border-gray-100 pt-3 text-sm text-gray-600">
                    <ol className="space-y-2 list-decimal pl-5">
                      <li>
                        In your Meta developer app (or a separate one), add the <strong>Threads API</strong> product.
                      </li>
                      <li>
                        Add this redirect URI under the Threads API settings:
                        {uris?.threads && <CopyField value={uris.threads} />}
                      </li>
                      <li>
                        If you use a separate app for Threads, enter its ID and secret below;
                        otherwise leave these blank and your Meta credentials are used.
                      </li>
                    </ol>
                    <div className="grid grid-cols-2 gap-3">
                      {credentialInput("threads_app_id", "Threads App ID (optional)")}
                      {credentialInput("threads_app_secret", "Threads App Secret (optional)")}
                    </div>
                    <button
                      onClick={() => startOAuth("threads")}
                      disabled={!settings.meta_app_id && !settings.threads_app_id}
                      className="px-4 py-2 bg-gray-900 text-white rounded-lg text-sm font-medium hover:bg-black disabled:opacity-50 transition-colors"
                    >
                      Save &amp; connect Threads
                    </button>
                  </div>
                )}
              </div>

              {/* LinkedIn */}
              <div className="border border-gray-200 rounded-xl overflow-hidden">
                {guideHeader("linkedin", "💼", "LinkedIn", "~10 minutes")}
                {openGuide === "linkedin" && (
                  <div className="px-4 pb-4 space-y-3 border-t border-gray-100 pt-3 text-sm text-gray-600">
                    <ol className="space-y-2 list-decimal pl-5">
                      <li>
                        Go to{" "}
                        <a href="https://developer.linkedin.com/" target="_blank" rel="noreferrer" className="text-brand-600 underline">
                          developer.linkedin.com
                        </a>{" "}
                        and create an app (it must be linked to a LinkedIn Page you manage).
                      </li>
                      <li>
                        Under <strong>Products</strong>, request <em>Share on LinkedIn</em> and{" "}
                        <em>Sign In with LinkedIn using OpenID Connect</em>.
                      </li>
                      <li>
                        Under <strong>Auth</strong>, add this redirect URL:
                        {uris?.linkedin && <CopyField value={uris.linkedin} />}
                      </li>
                      <li>Copy the Client ID and Client Secret below.</li>
                    </ol>
                    <div className="grid grid-cols-2 gap-3">
                      {credentialInput("linkedin_client_id", "LinkedIn Client ID")}
                      {credentialInput("linkedin_client_secret", "LinkedIn Client Secret")}
                    </div>
                    <button
                      onClick={() => startOAuth("linkedin")}
                      disabled={!settings.linkedin_client_id}
                      className="px-4 py-2 bg-blue-700 text-white rounded-lg text-sm font-medium hover:bg-blue-800 disabled:opacity-50 transition-colors"
                    >
                      Save &amp; connect LinkedIn
                    </button>
                  </div>
                )}
              </div>
            </div>

            <div className="flex items-center justify-between mt-6">
              <button onClick={() => setStep(2)} className="text-sm text-gray-400 hover:text-gray-600">
                Skip for now
              </button>
              <button
                onClick={() => setStep(2)}
                disabled={channels.length === 0}
                className="px-5 py-2.5 bg-brand-600 text-white rounded-lg text-sm font-semibold hover:bg-brand-700 disabled:opacity-40 transition-colors"
              >
                Continue ({channels.length} connected)
              </button>
            </div>
          </div>
        )}

        {/* Step 3: done */}
        {step === 2 && (
          <div className="bg-white rounded-2xl border border-gray-200 p-8 text-center">
            <div className="text-5xl mb-4">🎉</div>
            <h1 className="text-2xl font-bold text-gray-900 mb-2">You're all set</h1>
            <p className="text-sm text-gray-500 mb-6 max-w-md mx-auto">
              {channels.length > 0
                ? `${channels.length} account${channels.length === 1 ? "" : "s"} connected. Write a post once, pick your channels, and schedule it — vibepost does the rest.`
                : "You can connect accounts any time from Settings. Until then, you can draft and schedule posts."}
            </p>
            <button
              onClick={onDone}
              className="px-6 py-2.5 bg-brand-600 text-white rounded-lg text-sm font-semibold hover:bg-brand-700 transition-colors"
            >
              Start composing →
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
