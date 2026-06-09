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
import type { Platform } from "../types";

interface Props {
  text: string;
  mediaPreviews: string[];
  platforms: Platform[];
}

const LIMITS: Record<Platform, number> = {
  instagram: 2200,
  facebook: 63206,
  bluesky: 300,
  threads: 500,
  linkedin: 3000,
};

const LABELS: Record<Platform, string> = {
  instagram: "Instagram",
  facebook: "Facebook",
  bluesky: "Bluesky",
  threads: "Threads",
  linkedin: "LinkedIn",
};

function CharCounter({ text, platform }: { text: string; platform: Platform }) {
  const limit = LIMITS[platform];
  const count = text.length;
  const pct = count / limit;
  const color = pct > 0.9 ? "text-red-500" : pct > 0.7 ? "text-yellow-500" : "text-gray-400";
  return <span className={`text-xs ${color}`}>{count}/{limit}</span>;
}

function MediaGrid({ srcs }: { srcs: string[] }) {
  if (srcs.length === 0) return null;
  if (srcs.length === 1)
    return <img src={srcs[0]} className="w-full max-h-56 object-cover" alt="" />;
  return (
    <div className="grid grid-cols-2 gap-px">
      {srcs.slice(0, 4).map((s, i) => (
        <img key={i} src={s} className="w-full aspect-square object-cover" alt="" />
      ))}
    </div>
  );
}

function InstagramPreview({ text, mediaPreviews }: { text: string; mediaPreviews: string[] }) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden w-full max-w-sm">
      <div className="flex items-center gap-2 px-3 py-2 border-b border-gray-100">
        <div className="w-7 h-7 rounded-full bg-gradient-to-br from-purple-500 to-pink-500" />
        <span className="text-xs font-semibold">your_account</span>
      </div>
      {mediaPreviews.length > 0 ? (
        <img src={mediaPreviews[0]} className="w-full aspect-square object-cover" alt="" />
      ) : (
        <div className="aspect-square bg-gray-100 flex items-center justify-center text-gray-300 text-5xl">📷</div>
      )}
      <div className="px-3 py-2">
        {text ? (
          <p className="text-xs text-gray-800 line-clamp-3">
            <span className="font-semibold">your_account </span>{text}
          </p>
        ) : (
          <p className="text-xs text-gray-300 italic">Caption goes here…</p>
        )}
      </div>
    </div>
  );
}

function FacebookPreview({ text, mediaPreviews }: { text: string; mediaPreviews: string[] }) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden w-full max-w-sm">
      <div className="flex items-center gap-2 px-3 py-3">
        <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-white text-xs font-bold">P</div>
        <div>
          <p className="text-xs font-semibold text-gray-900">Your Page</p>
          <p className="text-xs text-gray-400">Just now · 🌐</p>
        </div>
      </div>
      <div className="px-3 pb-2">
        {text ? (
          <p className="text-sm text-gray-800 whitespace-pre-wrap line-clamp-5">{text}</p>
        ) : (
          <p className="text-sm text-gray-300 italic">What's on your mind?</p>
        )}
      </div>
      {mediaPreviews.length > 0 && <MediaGrid srcs={mediaPreviews} />}
      <div className="flex px-3 py-2 border-t border-gray-100 gap-4 mt-1">
        {["👍 Like", "💬 Comment", "↗️ Share"].map((l) => (
          <span key={l} className="text-xs text-gray-500">{l}</span>
        ))}
      </div>
    </div>
  );
}

function BlueskyPreview({ text, mediaPreviews }: { text: string; mediaPreviews: string[] }) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 w-full max-w-sm p-3">
      <div className="flex gap-2">
        <div className="w-8 h-8 rounded-full bg-sky-500 flex-shrink-0" />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1 mb-1">
            <span className="text-xs font-bold text-gray-900">Your Name</span>
            <span className="text-xs text-gray-400 truncate">@handle.bsky.social</span>
          </div>
          {text ? (
            <p className="text-sm text-gray-800 whitespace-pre-wrap break-words">{text}</p>
          ) : (
            <p className="text-sm text-gray-300 italic">What's happening?</p>
          )}
          {mediaPreviews.length > 0 && (
            <div className="mt-2 rounded-lg overflow-hidden">
              <img src={mediaPreviews[0]} className="w-full max-h-48 object-cover" alt="" />
            </div>
          )}
          <div className="flex gap-4 mt-2 text-xs text-gray-400">
            <span>💬</span><span>🔁</span><span>❤️</span>
          </div>
        </div>
      </div>
    </div>
  );
}

function ThreadsPreview({ text, mediaPreviews }: { text: string; mediaPreviews: string[] }) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 w-full max-w-sm p-3">
      <div className="flex gap-2">
        <div className="w-8 h-8 rounded-full bg-gray-900 flex-shrink-0" />
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs font-bold text-gray-900">yourhandle</span>
            <span className="text-xs text-gray-400">now</span>
          </div>
          {text ? (
            <p className="text-sm text-gray-800 whitespace-pre-wrap break-words">{text}</p>
          ) : (
            <p className="text-sm text-gray-300 italic">Start a thread…</p>
          )}
          {mediaPreviews.length > 0 && (
            <div className="mt-2 rounded-lg overflow-hidden">
              <img src={mediaPreviews[0]} className="w-full max-h-48 object-cover" alt="" />
            </div>
          )}
          <div className="flex gap-3 mt-2 text-gray-400">
            <span>♡</span><span>↩</span><span>↗</span>
          </div>
        </div>
      </div>
    </div>
  );
}

function LinkedInPreview({ text, mediaPreviews }: { text: string; mediaPreviews: string[] }) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden w-full max-w-sm">
      <div className="flex items-center gap-2 px-3 py-3">
        <div className="w-10 h-10 rounded-full bg-blue-700 flex items-center justify-center text-white font-bold">Y</div>
        <div>
          <p className="text-xs font-semibold text-gray-900">Your Name</p>
          <p className="text-xs text-gray-400">Your Title · Just now</p>
        </div>
      </div>
      <div className="px-3 pb-2">
        {text ? (
          <p className="text-sm text-gray-800 whitespace-pre-wrap line-clamp-5">{text}</p>
        ) : (
          <p className="text-sm text-gray-300 italic">Share an article, photo or idea…</p>
        )}
      </div>
      {mediaPreviews.length > 0 && (
        <img src={mediaPreviews[0]} className="w-full max-h-56 object-cover" alt="" />
      )}
      <div className="flex px-3 py-2 border-t border-gray-100 gap-4">
        {["👍 Like", "💬 Comment", "🔁 Repost"].map((l) => (
          <span key={l} className="text-xs text-gray-500">{l}</span>
        ))}
      </div>
    </div>
  );
}

export function PostPreview({ text, mediaPreviews, platforms }: Props) {
  const [active, setActive] = useState<Platform>(platforms[0] ?? "bluesky");
  const ap = platforms.includes(active) ? active : platforms[0];

  if (platforms.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-gray-400 text-sm">
        Select a channel to preview
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      <div className="flex gap-1 p-2 border-b border-gray-100 flex-wrap items-center">
        {platforms.map((p) => (
          <button
            key={p}
            onClick={() => setActive(p)}
            className={`px-2 py-1 rounded text-xs font-medium transition-colors ${
              ap === p ? "bg-brand-600 text-white" : "text-gray-500 hover:bg-gray-100"
            }`}
          >
            {LABELS[p]}
          </button>
        ))}
        <div className="ml-auto">
          <CharCounter text={text} platform={ap} />
        </div>
      </div>
      <div className="flex-1 overflow-auto p-4 flex justify-center">
        {ap === "instagram" && <InstagramPreview text={text} mediaPreviews={mediaPreviews} />}
        {ap === "facebook" && <FacebookPreview text={text} mediaPreviews={mediaPreviews} />}
        {ap === "bluesky" && <BlueskyPreview text={text} mediaPreviews={mediaPreviews} />}
        {ap === "threads" && <ThreadsPreview text={text} mediaPreviews={mediaPreviews} />}
        {ap === "linkedin" && <LinkedInPreview text={text} mediaPreviews={mediaPreviews} />}
      </div>
    </div>
  );
}
