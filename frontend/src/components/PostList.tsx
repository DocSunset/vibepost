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
import { format } from "date-fns";
import type { Profile, Post } from "../types";
import { api } from "../api";

interface Props {
  profile: Profile;
  onError: (msg: string) => void;
  onSuccess: (msg: string) => void;
}

const STATUS_COLORS: Record<string, string> = {
  scheduled: "bg-blue-100 text-blue-700",
  published: "bg-green-100 text-green-700",
  failed: "bg-red-100 text-red-700",
  partial: "bg-yellow-100 text-yellow-700",
  draft: "bg-gray-100 text-gray-600",
};

const PLATFORM_ICONS: Record<string, string> = {
  instagram: "📷",
  facebook: "📘",
  bluesky: "🦋",
  threads: "🧵",
  linkedin: "💼",
};

const FILTERS = ["all", "draft", "scheduled", "published", "failed"] as const;
type Filter = (typeof FILTERS)[number];

export default function PostList({ profile, onError, onSuccess }: Props) {
  const [posts, setPosts] = useState<Post[]>([]);
  const [filter, setFilter] = useState<Filter>("all");
  const [loading, setLoading] = useState(false);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const list = await api.posts.list({
        profile_id: profile.id,
        status: filter === "all" ? undefined : filter,
      });
      setPosts(list);
    } catch {
      onError("Failed to load posts");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [profile.id, filter]);

  const handlePublish = async (post: Post) => {
    try {
      await api.posts.publish(post.id);
      onSuccess("Posted!");
      load();
    } catch (e: any) {
      onError(e.response?.data?.detail || "Publish failed");
    }
  };

  const handleDelete = async (post: Post) => {
    if (!confirm("Delete this post?")) return;
    try {
      await api.posts.delete(post.id);
      onSuccess("Deleted");
      load();
    } catch {
      onError("Delete failed");
    }
  };

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
        <h1 className="text-xl font-semibold text-gray-900">Posts</h1>
        <button onClick={load} className="text-sm text-brand-600 hover:underline">Refresh</button>
      </div>

      {/* Filter tabs */}
      <div className="flex gap-1 px-6 py-3 border-b border-gray-100">
        {FILTERS.map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-3 py-1 rounded-full text-xs font-medium capitalize transition-colors ${
              filter === f ? "bg-brand-600 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"
            }`}
          >
            {f}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-auto">
        {loading ? (
          <div className="flex items-center justify-center h-32 text-gray-400 text-sm">Loading…</div>
        ) : posts.length === 0 ? (
          <div className="flex items-center justify-center h-32 text-gray-400 text-sm">
            No {filter === "all" ? "" : filter} posts yet.
          </div>
        ) : (
          <div className="divide-y divide-gray-100">
            {posts.map((post) => {
              const expanded = expandedId === post.id;
              const dt = post.scheduled_at || post.published_at || post.created_at;

              return (
                <div key={post.id} className="px-6 py-4">
                  <div className="flex items-start gap-4">
                    {/* Media thumbnail */}
                    {post.media_paths.length > 0 ? (
                      <img
                        src={`/media/${post.media_paths[0]}`}
                        className="w-12 h-12 rounded-lg object-cover flex-shrink-0"
                        alt=""
                      />
                    ) : (
                      <div className="w-12 h-12 rounded-lg bg-gray-100 flex items-center justify-center text-xl flex-shrink-0">
                        📝
                      </div>
                    )}

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1 flex-wrap">
                        <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium capitalize ${STATUS_COLORS[post.status]}`}>
                          {post.status}
                        </span>
                        <span className="text-xs text-gray-400">
                          {dt ? format(new Date(dt), "MMM d, yyyy · h:mm a") : "No date"}
                        </span>
                        <div className="flex gap-1">
                          {post.post_channels.map((pc) => (
                            <span key={pc.id} title={pc.channel.display_name}>
                              {PLATFORM_ICONS[pc.channel.platform]}
                            </span>
                          ))}
                        </div>
                      </div>

                      <p
                        className={`text-sm text-gray-800 ${!expanded ? "line-clamp-2" : "whitespace-pre-wrap"}`}
                        onClick={() => setExpandedId(expanded ? null : post.id)}
                      >
                        {post.text || <span className="italic text-gray-400">(no caption)</span>}
                      </p>

                      {/* Channel statuses (expanded) */}
                      {expanded && (
                        <div className="mt-2 space-y-1">
                          {post.post_channels.map((pc) => (
                            <div key={pc.id} className="flex items-center gap-2 text-xs">
                              <span>{PLATFORM_ICONS[pc.channel.platform]}</span>
                              <span className="text-gray-600">{pc.channel.display_name}</span>
                              <span
                                className={`ml-auto ${
                                  pc.status === "published" ? "text-green-600" : pc.status === "failed" ? "text-red-600" : "text-gray-400"
                                }`}
                              >
                                {pc.status}
                              </span>
                            </div>
                          ))}
                          {post.post_channels.some((pc) => pc.error_message) && (
                            <div className="p-2 bg-red-50 rounded text-xs text-red-700 mt-1">
                              {post.post_channels.find((pc) => pc.error_message)?.error_message}
                            </div>
                          )}
                        </div>
                      )}
                    </div>

                    {/* Actions */}
                    <div className="flex gap-2 flex-shrink-0">
                      {(post.status === "draft" || post.status === "scheduled") && (
                        <button
                          onClick={() => handlePublish(post)}
                          className="text-xs px-2 py-1 bg-brand-600 text-white rounded hover:bg-brand-700 transition-colors"
                        >
                          Post now
                        </button>
                      )}
                      <button
                        onClick={() => handleDelete(post)}
                        className="text-xs px-2 py-1 bg-gray-100 text-gray-600 rounded hover:bg-red-100 hover:text-red-600 transition-colors"
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
