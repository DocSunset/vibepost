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

import { useState, useEffect } from "react";
import type { Profile, Channel, AppSettings } from "../types";
import { api } from "../api";

interface Props {
  profiles: Profile[];
  activeProfileId: number | null;
  channels: Channel[];
  onProfilesChanged: () => void;
  onChannelsChanged: () => void;
  onError: (msg: string) => void;
  onSuccess: (msg: string) => void;
}

const AVATAR_COLORS = [
  "#6366f1", "#8b5cf6", "#ec4899", "#ef4444",
  "#f59e0b", "#10b981", "#06b6d4", "#3b82f6",
];

const PLATFORM_ICONS: Record<string, string> = {
  instagram: "📷",
  facebook: "📘",
  bluesky: "🦋",
  threads: "🧵",
  linkedin: "💼",
};

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden mb-6">
      <div className="px-6 py-4 border-b border-gray-100">
        <h2 className="font-semibold text-gray-900">{title}</h2>
      </div>
      <div className="px-6 py-5">{children}</div>
    </div>
  );
}

export default function Settings({
  profiles,
  activeProfileId,
  channels,
  onProfilesChanged,
  onChannelsChanged,
  onError,
  onSuccess,
}: Props) {
  const [settingsProfileId, setSettingsProfileId] = useState(activeProfileId ?? profiles[0]?.id);
  const [settings, setSettings] = useState<Partial<AppSettings>>({});
  const [savingSettings, setSavingSettings] = useState(false);

  // Profile form
  const [newProfileName, setNewProfileName] = useState("");
  const [newProfileColor, setNewProfileColor] = useState(AVATAR_COLORS[0]);
  const [creatingProfile, setCreatingProfile] = useState(false);

  // Bluesky form
  const [bskyHandle, setBskyHandle] = useState("");
  const [bskyPassword, setBskyPassword] = useState("");
  const [connectingBsky, setConnectingBsky] = useState(false);

  const profileChannels = channels.filter((ch) => ch.profile_id === settingsProfileId);

  useEffect(() => {
    api.auth.getSettings().then(setSettings).catch(() => {});
  }, []);

  useEffect(() => {
    if (!settingsProfileId && profiles.length > 0) {
      setSettingsProfileId(profiles[0].id);
    }
  }, [profiles]);

  const handleSaveSettings = async () => {
    setSavingSettings(true);
    try {
      await api.auth.saveSettings(settings);
      onSuccess("Settings saved");
    } catch {
      onError("Failed to save settings");
    } finally {
      setSavingSettings(false);
    }
  };

  const handleCreateProfile = async () => {
    if (!newProfileName.trim()) return;
    setCreatingProfile(true);
    try {
      await api.profiles.create(newProfileName.trim(), newProfileColor);
      setNewProfileName("");
      onProfilesChanged();
      onSuccess("Profile created");
    } catch {
      onError("Failed to create profile");
    } finally {
      setCreatingProfile(false);
    }
  };

  const handleDeleteProfile = async (id: number) => {
    if (!confirm("Delete this profile and all its data?")) return;
    try {
      await api.profiles.delete(id);
      onProfilesChanged();
      onChannelsChanged();
      onSuccess("Profile deleted");
    } catch {
      onError("Failed to delete profile");
    }
  };

  const handleConnectBluesky = async () => {
    if (!settingsProfileId) return;
    setConnectingBsky(true);
    try {
      await api.auth.connectBluesky(settingsProfileId, bskyHandle, bskyPassword);
      setBskyHandle("");
      setBskyPassword("");
      onChannelsChanged();
      onSuccess("Bluesky connected!");
    } catch (e: any) {
      onError(e.response?.data?.detail || "Bluesky auth failed");
    } finally {
      setConnectingBsky(false);
    }
  };

  const handleOAuth = async (platform: "meta" | "threads" | "linkedin") => {
    if (!settingsProfileId) {
      onError("Select a profile first");
      return;
    }
    try {
      let data: { url: string };
      if (platform === "meta") data = await api.auth.metaOAuthUrl(settingsProfileId);
      else if (platform === "threads") data = await api.auth.threadsOAuthUrl(settingsProfileId);
      else data = await api.auth.linkedinOAuthUrl(settingsProfileId);
      window.location.href = data.url;
    } catch (e: any) {
      onError(e.response?.data?.detail || `${platform} OAuth error`);
    }
  };

  const handleDisconnect = async (channelId: number) => {
    if (!confirm("Disconnect this account?")) return;
    try {
      await api.channels.delete(channelId);
      onChannelsChanged();
      onSuccess("Disconnected");
    } catch {
      onError("Failed to disconnect");
    }
  };

  return (
    <div className="max-w-2xl mx-auto px-6 py-8">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Settings</h1>

      {/* Profiles */}
      <Section title="Profiles">
        <div className="space-y-3 mb-5">
          {profiles.length === 0 ? (
            <p className="text-sm text-gray-400 italic">No profiles yet.</p>
          ) : (
            profiles.map((p) => (
              <div key={p.id} className="flex items-center gap-3">
                <div
                  className="w-8 h-8 rounded-full flex items-center justify-center text-white font-bold text-sm"
                  style={{ background: p.avatar_color }}
                >
                  {p.name[0].toUpperCase()}
                </div>
                <span className="text-sm font-medium text-gray-800 flex-1">{p.name}</span>
                <button
                  onClick={() => setSettingsProfileId(p.id)}
                  className={`text-xs px-2 py-1 rounded transition-colors ${
                    settingsProfileId === p.id
                      ? "bg-brand-100 text-brand-700 font-medium"
                      : "text-gray-400 hover:text-gray-600"
                  }`}
                >
                  {settingsProfileId === p.id ? "Selected" : "Select"}
                </button>
                <button
                  onClick={() => handleDeleteProfile(p.id)}
                  className="text-xs text-gray-300 hover:text-red-500 transition-colors"
                >
                  Delete
                </button>
              </div>
            ))
          )}
        </div>

        <p className="text-xs font-medium text-gray-500 mb-2">New profile</p>
        <div className="flex gap-2 items-center flex-wrap">
          <input
            value={newProfileName}
            onChange={(e) => setNewProfileName(e.target.value)}
            placeholder="Profile name"
            className="border border-gray-200 rounded-lg px-3 py-2 text-sm flex-1 focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
          <div className="flex gap-1">
            {AVATAR_COLORS.map((c) => (
              <button
                key={c}
                onClick={() => setNewProfileColor(c)}
                style={{ background: c }}
                className={`w-6 h-6 rounded-full transition-transform ${newProfileColor === c ? "scale-125 ring-2 ring-offset-1 ring-gray-400" : ""}`}
              />
            ))}
          </div>
          <button
            onClick={handleCreateProfile}
            disabled={creatingProfile || !newProfileName.trim()}
            className="px-4 py-2 bg-brand-600 text-white rounded-lg text-sm font-medium hover:bg-brand-700 disabled:opacity-50 transition-colors"
          >
            Create
          </button>
        </div>
      </Section>

      {/* App credentials */}
      <Section title="App Credentials">
        <p className="text-xs text-gray-500 mb-4">
          Enter your developer app credentials. These are stored locally. You need to create developer apps at{" "}
          <span className="font-medium">developers.facebook.com</span> (for Meta platforms) and{" "}
          <span className="font-medium">developer.linkedin.com</span>.
        </p>
        <div className="space-y-3">
          {[
            { key: "meta_app_id", label: "Meta App ID", placeholder: "123456789" },
            { key: "meta_app_secret", label: "Meta App Secret", placeholder: "••••••••" },
            { key: "threads_app_id", label: "Threads App ID (if separate from Meta)", placeholder: "Leave blank to use Meta App ID" },
            { key: "threads_app_secret", label: "Threads App Secret", placeholder: "Leave blank to use Meta App Secret" },
            { key: "linkedin_client_id", label: "LinkedIn Client ID", placeholder: "86abc..." },
            { key: "linkedin_client_secret", label: "LinkedIn Client Secret", placeholder: "••••••••" },
            {
              key: "public_media_base_url",
              label: "Public Media Base URL",
              placeholder: "https://your-domain.com (for Instagram/Threads images)",
            },
          ].map(({ key, label, placeholder }) => (
            <div key={key}>
              <label className="block text-xs font-medium text-gray-500 mb-1">{label}</label>
              <input
                type={key.includes("secret") ? "password" : "text"}
                value={(settings as any)[key] ?? ""}
                onChange={(e) => setSettings((prev) => ({ ...prev, [key]: e.target.value }))}
                placeholder={placeholder}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
            </div>
          ))}
        </div>
        <button
          onClick={handleSaveSettings}
          disabled={savingSettings}
          className="mt-4 px-4 py-2 bg-brand-600 text-white rounded-lg text-sm font-medium hover:bg-brand-700 disabled:opacity-50 transition-colors"
        >
          {savingSettings ? "Saving…" : "Save credentials"}
        </button>
      </Section>

      {/* Connect accounts */}
      <Section title={`Connect Accounts${settingsProfileId ? ` — ${profiles.find((p) => p.id === settingsProfileId)?.name ?? ""}` : ""}`}>
        {!settingsProfileId ? (
          <p className="text-sm text-gray-400">Select or create a profile first.</p>
        ) : (
          <div className="space-y-6">
            {/* Connected channels */}
            {profileChannels.length > 0 && (
              <div>
                <p className="text-xs font-medium text-gray-500 mb-2">Connected</p>
                <div className="space-y-2">
                  {profileChannels.map((ch) => (
                    <div key={ch.id} className="flex items-center gap-3 p-2 bg-gray-50 rounded-lg">
                      <span className="text-lg">{PLATFORM_ICONS[ch.platform]}</span>
                      <div className="flex-1">
                        <p className="text-sm font-medium text-gray-800">{ch.display_name}</p>
                        <p className="text-xs text-gray-400 capitalize">{ch.platform}</p>
                      </div>
                      <div className="w-2 h-2 rounded-full bg-green-500" title="Connected" />
                      <button
                        onClick={() => handleDisconnect(ch.id)}
                        className="text-xs text-gray-400 hover:text-red-500 transition-colors"
                      >
                        Disconnect
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Bluesky */}
            <div>
              <p className="text-xs font-medium text-gray-500 mb-2">🦋 Bluesky</p>
              <p className="text-xs text-gray-400 mb-2">
                Use an App Password (not your main password) from{" "}
                <span className="font-medium">bsky.app → Settings → App Passwords</span>.
              </p>
              <div className="flex gap-2 flex-wrap">
                <input
                  value={bskyHandle}
                  onChange={(e) => setBskyHandle(e.target.value)}
                  placeholder="handle.bsky.social"
                  className="border border-gray-200 rounded-lg px-3 py-2 text-sm flex-1 focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
                <input
                  type="password"
                  value={bskyPassword}
                  onChange={(e) => setBskyPassword(e.target.value)}
                  placeholder="App password"
                  className="border border-gray-200 rounded-lg px-3 py-2 text-sm flex-1 focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
                <button
                  onClick={handleConnectBluesky}
                  disabled={connectingBsky || !bskyHandle || !bskyPassword}
                  className="px-4 py-2 bg-sky-500 text-white rounded-lg text-sm font-medium hover:bg-sky-600 disabled:opacity-50 transition-colors"
                >
                  {connectingBsky ? "Connecting…" : "Connect"}
                </button>
              </div>
            </div>

            {/* Meta */}
            <div>
              <p className="text-xs font-medium text-gray-500 mb-2">📘 Facebook + 📷 Instagram</p>
              <p className="text-xs text-gray-400 mb-2">
                Requires a Meta Developer App with <code>pages_manage_posts</code> and{" "}
                <code>instagram_content_publish</code> permissions. Set your OAuth redirect URI to{" "}
                <code>http://localhost:8000/api/auth/meta/callback</code>.
              </p>
              <button
                onClick={() => handleOAuth("meta")}
                disabled={!settings.meta_app_id}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
              >
                Connect via Facebook OAuth
              </button>
              {!settings.meta_app_id && (
                <p className="text-xs text-red-500 mt-1">Add Meta App ID above first</p>
              )}
            </div>

            {/* Threads */}
            <div>
              <p className="text-xs font-medium text-gray-500 mb-2">🧵 Threads</p>
              <p className="text-xs text-gray-400 mb-2">
                Requires a Threads API app (can be same as Meta app or separate). Set redirect URI to{" "}
                <code>http://localhost:8000/api/auth/threads/callback</code>.
              </p>
              <button
                onClick={() => handleOAuth("threads")}
                disabled={!settings.meta_app_id && !settings.threads_app_id}
                className="px-4 py-2 bg-gray-900 text-white rounded-lg text-sm font-medium hover:bg-black disabled:opacity-50 transition-colors"
              >
                Connect Threads
              </button>
            </div>

            {/* LinkedIn */}
            <div>
              <p className="text-xs font-medium text-gray-500 mb-2">💼 LinkedIn</p>
              <p className="text-xs text-gray-400 mb-2">
                Requires a LinkedIn Developer App with <code>w_member_social</code> scope. Set redirect URI to{" "}
                <code>http://localhost:8000/api/auth/linkedin/callback</code>.
              </p>
              <button
                onClick={() => handleOAuth("linkedin")}
                disabled={!settings.linkedin_client_id}
                className="px-4 py-2 bg-blue-700 text-white rounded-lg text-sm font-medium hover:bg-blue-800 disabled:opacity-50 transition-colors"
              >
                Connect LinkedIn
              </button>
              {!settings.linkedin_client_id && (
                <p className="text-xs text-red-500 mt-1">Add LinkedIn Client ID above first</p>
              )}
            </div>
          </div>
        )}
      </Section>
    </div>
  );
}
