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
import {
  format,
  startOfMonth,
  endOfMonth,
  startOfWeek,
  endOfWeek,
  addDays,
  addMonths,
  subMonths,
  isSameMonth,
  isSameDay,
  isToday,
} from "date-fns";
import type { Profile, Post } from "../types";
import { api } from "../api";

interface Props {
  profile: Profile;
  onSelectDate: (date: Date) => void;
}

const STATUS_COLORS: Record<string, string> = {
  scheduled: "bg-blue-500",
  published: "bg-green-500",
  failed: "bg-red-500",
  partial: "bg-yellow-500",
  draft: "bg-gray-400",
};

const PLATFORM_ICONS: Record<string, string> = {
  instagram: "📷",
  facebook: "📘",
  bluesky: "🦋",
  threads: "🧵",
  linkedin: "💼",
};

export default function CalendarView({ profile, onSelectDate }: Props) {
  const [currentDate, setCurrentDate] = useState(new Date());
  const [posts, setPosts] = useState<Post[]>([]);
  const [selected, setSelected] = useState<Post | null>(null);

  useEffect(() => {
    const start = startOfMonth(currentDate);
    const end = endOfMonth(currentDate);
    api.posts
      .list({
        profile_id: profile.id,
        start: start.toISOString(),
        end: end.toISOString(),
      })
      .then(setPosts)
      .catch(() => {});
  }, [profile.id, currentDate]);

  const monthStart = startOfMonth(currentDate);
  const calStart = startOfWeek(monthStart, { weekStartsOn: 0 });
  const calEnd = endOfWeek(endOfMonth(currentDate), { weekStartsOn: 0 });

  const days: Date[] = [];
  let d = calStart;
  while (d <= calEnd) {
    days.push(d);
    d = addDays(d, 1);
  }

  const postsByDay = (day: Date) =>
    posts.filter((p) => {
      const dt = p.scheduled_at || p.published_at || p.created_at;
      return dt && isSameDay(new Date(dt), day);
    });

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
        <h1 className="text-xl font-semibold text-gray-900">Calendar</h1>
        <div className="flex items-center gap-4">
          <button
            onClick={() => setCurrentDate((d) => subMonths(d, 1))}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
          >
            ‹
          </button>
          <span className="font-semibold text-gray-800 w-36 text-center">
            {format(currentDate, "MMMM yyyy")}
          </span>
          <button
            onClick={() => setCurrentDate((d) => addMonths(d, 1))}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
          >
            ›
          </button>
          <button
            onClick={() => setCurrentDate(new Date())}
            className="text-sm text-brand-600 hover:underline"
          >
            Today
          </button>
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* Grid */}
        <div className="flex-1 overflow-auto p-4">
          {/* Weekday headers */}
          <div className="grid grid-cols-7 mb-1">
            {["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((w) => (
              <div key={w} className="text-xs font-semibold text-gray-400 text-center py-1">
                {w}
              </div>
            ))}
          </div>

          {/* Days */}
          <div className="grid grid-cols-7 gap-px bg-gray-200 rounded-xl overflow-hidden">
            {days.map((day, i) => {
              const dayPosts = postsByDay(day);
              const inMonth = isSameMonth(day, currentDate);
              const today = isToday(day);

              return (
                <div
                  key={i}
                  onClick={() => onSelectDate(day)}
                  className={`bg-white min-h-24 p-2 cursor-pointer hover:bg-gray-50 transition-colors ${
                    !inMonth ? "opacity-40" : ""
                  }`}
                >
                  <div
                    className={`text-xs font-semibold mb-1 w-6 h-6 flex items-center justify-center rounded-full ${
                      today
                        ? "bg-brand-600 text-white"
                        : inMonth
                        ? "text-gray-800"
                        : "text-gray-400"
                    }`}
                  >
                    {format(day, "d")}
                  </div>
                  <div className="space-y-0.5">
                    {dayPosts.slice(0, 3).map((post) => {
                      const platforms = post.post_channels.map((pc) => pc.channel.platform);
                      return (
                        <button
                          key={post.id}
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelected(post);
                          }}
                          className={`w-full text-left px-1 py-0.5 rounded text-xs text-white truncate ${STATUS_COLORS[post.status]}`}
                        >
                          {platforms.slice(0, 2).map((p) => PLATFORM_ICONS[p]).join("")}{" "}
                          {post.text || "(media)"}
                        </button>
                      );
                    })}
                    {dayPosts.length > 3 && (
                      <p className="text-xs text-gray-400 px-1">+{dayPosts.length - 3} more</p>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Legend */}
          <div className="flex gap-4 mt-4 flex-wrap">
            {Object.entries(STATUS_COLORS).map(([s, c]) => (
              <div key={s} className="flex items-center gap-1">
                <div className={`w-2 h-2 rounded-full ${c}`} />
                <span className="text-xs text-gray-500 capitalize">{s}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Post detail panel */}
        {selected && (
          <div className="w-72 border-l border-gray-200 p-4 overflow-auto flex-shrink-0">
            <div className="flex items-center justify-between mb-3">
              <h2 className="font-semibold text-gray-800 text-sm">Post detail</h2>
              <button onClick={() => setSelected(null)} className="text-gray-400 hover:text-gray-600">✕</button>
            </div>

            <span
              className={`inline-block px-2 py-0.5 rounded text-xs text-white mb-3 ${STATUS_COLORS[selected.status]}`}
            >
              {selected.status}
            </span>

            {selected.scheduled_at && (
              <p className="text-xs text-gray-500 mb-2">
                📅 {format(new Date(selected.scheduled_at), "MMM d, yyyy · h:mm a")}
              </p>
            )}
            {selected.published_at && (
              <p className="text-xs text-gray-500 mb-2">
                ✅ Published {format(new Date(selected.published_at), "MMM d, yyyy · h:mm a")}
              </p>
            )}

            <p className="text-sm text-gray-800 whitespace-pre-wrap mb-3">
              {selected.text || <span className="italic text-gray-400">(no caption)</span>}
            </p>

            {selected.media_paths.length > 0 && (
              <div className="flex gap-1 mb-3 flex-wrap">
                {selected.media_paths.map((f, i) => (
                  <img
                    key={i}
                    src={`/media/${f}`}
                    className="w-12 h-12 object-cover rounded"
                    alt=""
                  />
                ))}
              </div>
            )}

            <div className="space-y-1">
              {selected.post_channels.map((pc) => (
                <div key={pc.id} className="flex items-center gap-2 text-xs">
                  <span>{PLATFORM_ICONS[pc.channel.platform]}</span>
                  <span className="text-gray-600">{pc.channel.display_name}</span>
                  <span
                    className={`ml-auto font-medium ${
                      pc.status === "published"
                        ? "text-green-600"
                        : pc.status === "failed"
                        ? "text-red-600"
                        : "text-gray-400"
                    }`}
                  >
                    {pc.status}
                  </span>
                </div>
              ))}
            </div>

            {selected.post_channels.some((pc) => pc.error_message) && (
              <div className="mt-3 p-2 bg-red-50 rounded text-xs text-red-700">
                {selected.post_channels.find((pc) => pc.error_message)?.error_message}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
