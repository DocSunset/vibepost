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

import { useEffect, useState, useCallback } from "react";
import { api, setUnauthorizedHandler } from "./api";
import type { Profile, Channel, User, View } from "./types";
import Composer from "./components/Composer";
import CalendarView from "./components/Calendar";
import PostList from "./components/PostList";
import Settings from "./components/Settings";
import AuthScreen from "./components/AuthScreen";
import PasskeyNudge from "./components/PasskeyNudge";
import Onboarding from "./components/Onboarding";
import PrivacyPolicy from "./components/PrivacyPolicy";

const PLATFORM_ICONS: Record<string, string> = {
  instagram: "📷",
  facebook: "📘",
  bluesky: "🦋",
  threads: "🧵",
  linkedin: "💼",
};

const NAV: { id: View; label: string; icon: string }[] = [
  { id: "compose", label: "Compose", icon: "✏️" },
  { id: "calendar", label: "Calendar", icon: "📅" },
  { id: "posts", label: "Posts", icon: "📋" },
  { id: "settings", label: "Settings", icon: "⚙️" },
];

export default function App() {
  const [user, setUser] = useState<User | null>(null);
  const [authChecked, setAuthChecked] = useState(false);
  const [onboarding, setOnboarding] = useState(false);
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [activeProfileId, setActiveProfileId] = useState<number | null>(null);
  const [channels, setChannels] = useState<Channel[]>([]);
  const [view, setView] = useState<View>("compose");
  const [toast, setToast] = useState<{ msg: string; kind: "ok" | "err" } | null>(null);

  const activeProfile = profiles.find((p) => p.id === activeProfileId) ?? null;

  const showToast = useCallback((msg: string, kind: "ok" | "err" = "ok") => {
    setToast({ msg, kind });
    setTimeout(() => setToast(null), 3500);
  }, []);

  const loadProfiles = useCallback(async () => {
    const list = await api.profiles.list();
    setProfiles(list);
    if (list.length > 0 && activeProfileId === null) {
      setActiveProfileId(list[0].id);
    }
    return list;
  }, [activeProfileId]);

  const loadChannels = useCallback(async () => {
    if (activeProfileId === null) return;
    const list = await api.channels.list(activeProfileId);
    setChannels(list);
  }, [activeProfileId]);

  // Session check on load; any later 401 drops back to the auth screen
  useEffect(() => {
    setUnauthorizedHandler(() => {
      setUser(null);
      setProfiles([]);
      setChannels([]);
      setActiveProfileId(null);
    });
    api.account
      .me()
      .then((u) => {
        setUser(u);
        // Already signed in: a leftover ?login_token= (e.g. opening the
        // emailed link in a signed-in browser) is just noise — drop it.
        if (new URLSearchParams(window.location.search).get("login_token")) {
          window.history.replaceState({}, "", "/");
        }
      })
      .catch(() => setUser(null))
      .finally(() => setAuthChecked(true));
  }, []);

  useEffect(() => {
    if (!user) return;
    loadProfiles().then((list) => {
      // A brand-new account (or one that never finished setup) gets the wizard
      if (list.length === 0) setOnboarding(true);
    });
  }, [user]);

  useEffect(() => {
    loadChannels();
  }, [activeProfileId]);

  // Handle OAuth callback success/error
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const success = params.get("success");
    const error = params.get("error");
    if (success) {
      showToast(`Connected ${success} successfully!`);
      window.history.replaceState({}, "", "/");
      setView("settings");
      loadChannels();
    }
    if (error) {
      showToast(`Connection failed: ${error.split("_").join(" ")}`, "err");
      window.history.replaceState({}, "", "/");
      setView("settings");
    }
  }, []);

  if (window.location.pathname === "/privacy") {
    return <PrivacyPolicy />;
  }

  if (!authChecked) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 text-gray-400 text-sm">
        Loading…
      </div>
    );
  }

  if (!user) {
    return (
      <AuthScreen
        onAuthed={(u, isNew) => {
          setUser(u);
          if (isNew) setOnboarding(true);
        }}
      />
    );
  }

  if (onboarding) {
    return (
      <>
        <PasskeyNudge />
        <Onboarding
          onDone={() => {
            setOnboarding(false);
            loadProfiles();
          }}
        />
      </>
    );
  }

  return (
    <div className="flex h-screen overflow-hidden bg-gray-50">
      <PasskeyNudge />
      {/* Sidebar */}
      <aside className="w-56 flex-shrink-0 bg-gray-900 flex flex-col">
        <div className="px-5 py-5 border-b border-gray-700">
          <span className="text-white text-xl font-bold tracking-tight">vibepost</span>
        </div>

        {/* Profile switcher */}
        <div className="px-3 py-3 border-b border-gray-700">
          {profiles.length === 0 ? (
            <button
              onClick={() => setView("settings")}
              className="text-xs text-gray-400 hover:text-white w-full text-left px-2"
            >
              + Create a profile
            </button>
          ) : (
            <div className="space-y-1">
              {profiles.map((p) => (
                <button
                  key={p.id}
                  onClick={() => setActiveProfileId(p.id)}
                  className={`w-full flex items-center gap-2 px-2 py-1.5 rounded-md text-sm transition-colors ${
                    p.id === activeProfileId
                      ? "bg-gray-700 text-white"
                      : "text-gray-400 hover:text-white hover:bg-gray-800"
                  }`}
                >
                  <span
                    className="w-5 h-5 rounded-full flex-shrink-0 flex items-center justify-center text-xs font-bold text-white"
                    style={{ background: p.avatar_color }}
                  >
                    {p.name[0].toUpperCase()}
                  </span>
                  <span className="truncate">{p.name}</span>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 py-4 space-y-1">
          {NAV.map((item) => (
            <button
              key={item.id}
              onClick={() => setView(item.id)}
              className={`w-full flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                view === item.id
                  ? "bg-brand-600 text-white"
                  : "text-gray-400 hover:text-white hover:bg-gray-800"
              }`}
            >
              <span>{item.icon}</span>
              {item.label}
            </button>
          ))}
        </nav>

        {/* Connected channels summary */}
        {channels.length > 0 && (
          <div className="px-4 py-4 border-t border-gray-700">
            <p className="text-xs text-gray-500 mb-2">Connected</p>
            <div className="flex flex-wrap gap-1">
              {channels.map((ch) => (
                <span key={ch.id} title={ch.display_name} className="text-base">
                  {PLATFORM_ICONS[ch.platform]}
                </span>
              ))}
            </div>
          </div>
        )}

        <div className="px-4 py-3 border-t border-gray-700">
          <a href="/privacy" className="text-[11px] text-gray-500 hover:text-gray-300">
            Privacy
          </a>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-auto">
        {activeProfile === null && view !== "settings" ? (
          <div className="flex items-center justify-center h-full text-gray-500">
            <div className="text-center">
              <p className="text-lg mb-2">No profile yet.</p>
              <button
                onClick={() => setView("settings")}
                className="text-brand-600 hover:underline"
              >
                Create one in Settings →
              </button>
            </div>
          </div>
        ) : (
          <>
            {view === "compose" && activeProfile && (
              <Composer
                profile={activeProfile}
                channels={channels}
                onPosted={() => showToast("Posted!")}
                onScheduled={() => showToast("Scheduled!")}
                onError={(e) => showToast(e, "err")}
              />
            )}
            {view === "calendar" && activeProfile && (
              <CalendarView
                profile={activeProfile}
                onSelectDate={(date) => {
                  setView("compose");
                }}
              />
            )}
            {view === "posts" && activeProfile && (
              <PostList
                profile={activeProfile}
                onError={(e) => showToast(e, "err")}
                onSuccess={(m) => showToast(m)}
              />
            )}
            {view === "settings" && (
              <Settings
                user={user}
                profiles={profiles}
                activeProfileId={activeProfileId}
                channels={channels}
                onProfilesChanged={loadProfiles}
                onChannelsChanged={loadChannels}
                onLoggedOut={() => {
                  setUser(null);
                  setProfiles([]);
                  setChannels([]);
                  setActiveProfileId(null);
                  setView("compose");
                }}
                onError={(e) => showToast(e, "err")}
                onSuccess={(m) => showToast(m)}
              />
            )}
          </>
        )}
      </main>

      {/* Toast */}
      {toast && (
        <div
          className={`fixed bottom-6 right-6 px-4 py-3 rounded-lg shadow-lg text-white text-sm font-medium transition-all ${
            toast.kind === "ok" ? "bg-green-600" : "bg-red-600"
          }`}
        >
          {toast.msg}
        </div>
      )}
    </div>
  );
}
