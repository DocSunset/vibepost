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

import { useState, useCallback } from "react";
import { useDropzone } from "react-dropzone";
import type { Profile, Channel, Platform } from "../types";
import { api } from "../api";
import { PostPreview } from "./Preview";

interface Props {
  profile: Profile;
  channels: Channel[];
  onPosted: () => void;
  onScheduled: () => void;
  onError: (msg: string) => void;
}

const PLATFORM_ICONS: Record<Platform, string> = {
  instagram: "📷",
  facebook: "📘",
  bluesky: "🦋",
  threads: "🧵",
  linkedin: "💼",
};

export default function Composer({ profile, channels, onPosted, onScheduled, onError }: Props) {
  const [text, setText] = useState("");
  const [selectedChannels, setSelectedChannels] = useState<Set<number>>(new Set());
  const [mediaFiles, setMediaFiles] = useState<{ filename: string; preview: string }[]>([]);
  const [scheduleMode, setScheduleMode] = useState<"now" | "later">("now");
  const [scheduledAt, setScheduledAt] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [uploadingCount, setUploadingCount] = useState(0);

  const onDrop = useCallback(
    async (accepted: File[]) => {
      setUploadingCount((n) => n + accepted.length);
      for (const file of accepted) {
        try {
          const { filename } = await api.posts.upload(file);
          const preview = URL.createObjectURL(file);
          setMediaFiles((prev) => [...prev, { filename, preview }]);
        } catch (e: any) {
          onError(`Upload failed: ${e.message}`);
        } finally {
          setUploadingCount((n) => n - 1);
        }
      }
    },
    [onError]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "image/*": [], "video/*": [] },
    maxFiles: 10,
  });

  const toggleChannel = (id: number) => {
    setSelectedChannels((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const handleSubmit = async () => {
    if (selectedChannels.size === 0) {
      onError("Select at least one channel");
      return;
    }
    if (!text.trim() && mediaFiles.length === 0) {
      onError("Add text or media");
      return;
    }

    setSubmitting(true);
    try {
      const post = await api.posts.create({
        profile_id: profile.id,
        text,
        media_paths: mediaFiles.map((f) => f.filename),
        channel_ids: Array.from(selectedChannels),
        // datetime-local gives naive local time; send unambiguous UTC to the server
        scheduled_at: scheduleMode === "later" && scheduledAt ? new Date(scheduledAt).toISOString() : null,
      });

      if (scheduleMode === "now") {
        await api.posts.publish(post.id);
        onPosted();
      } else {
        onScheduled();
      }

      setText("");
      setMediaFiles([]);
      setSelectedChannels(new Set());
      setScheduledAt("");
    } catch (e: any) {
      onError(e.response?.data?.detail || e.message || "Failed");
    } finally {
      setSubmitting(false);
    }
  };

  const selectedPlatforms = channels
    .filter((ch) => selectedChannels.has(ch.id))
    .map((ch) => ch.platform);

  const mediaPreviews = mediaFiles.map((f) => f.preview);

  return (
    <div className="h-full flex">
      {/* Left: composer */}
      <div className="flex-1 flex flex-col border-r border-gray-200 overflow-auto">
        <div className="p-6 border-b border-gray-100">
          <h1 className="text-xl font-semibold text-gray-900">Compose</h1>
          <p className="text-sm text-gray-500 mt-0.5">Posting as <span className="font-medium">{profile.name}</span></p>
        </div>

        <div className="flex-1 p-6 space-y-5">
          {/* Text */}
          <div>
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="What's on your mind?"
              rows={6}
              className="w-full border border-gray-200 rounded-xl p-3 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent"
            />
          </div>

          {/* Media */}
          <div>
            <p className="text-xs font-medium text-gray-500 mb-2">Media</p>
            {mediaFiles.length > 0 && (
              <div className="flex gap-2 mb-2 flex-wrap">
                {mediaFiles.map((f, i) => (
                  <div key={i} className="relative w-16 h-16 rounded-lg overflow-hidden bg-gray-100 group">
                    <img src={f.preview} className="w-full h-full object-cover" alt="" />
                    <button
                      onClick={() => setMediaFiles((prev) => prev.filter((_, j) => j !== i))}
                      className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 flex items-center justify-center text-white text-lg transition-opacity"
                    >
                      ✕
                    </button>
                  </div>
                ))}
                {uploadingCount > 0 && (
                  <div className="w-16 h-16 rounded-lg bg-gray-100 flex items-center justify-center text-gray-400 text-xs animate-pulse">
                    {uploadingCount} uploading
                  </div>
                )}
              </div>
            )}
            <div
              {...getRootProps()}
              className={`border-2 border-dashed rounded-xl p-4 text-center cursor-pointer transition-colors ${
                isDragActive
                  ? "border-brand-500 bg-brand-50"
                  : "border-gray-200 hover:border-brand-300"
              }`}
            >
              <input {...getInputProps()} />
              <p className="text-sm text-gray-400">
                {isDragActive ? "Drop files here" : "Drag & drop images/videos, or click to browse"}
              </p>
            </div>
          </div>

          {/* Channels */}
          <div>
            <p className="text-xs font-medium text-gray-500 mb-2">Post to</p>
            {channels.length === 0 ? (
              <p className="text-sm text-gray-400 italic">No channels connected — add them in Settings</p>
            ) : (
              <div className="space-y-2">
                {channels.map((ch) => (
                  <label
                    key={ch.id}
                    className="flex items-center gap-3 cursor-pointer group"
                  >
                    <input
                      type="checkbox"
                      checked={selectedChannels.has(ch.id)}
                      onChange={() => toggleChannel(ch.id)}
                      className="w-4 h-4 rounded text-brand-600 border-gray-300 focus:ring-brand-500"
                    />
                    <span className="text-base">{PLATFORM_ICONS[ch.platform]}</span>
                    <span className="text-sm text-gray-700">{ch.display_name}</span>
                    <span className="text-xs text-gray-400 capitalize">({ch.platform})</span>
                  </label>
                ))}
              </div>
            )}
          </div>

          {/* Schedule */}
          <div>
            <p className="text-xs font-medium text-gray-500 mb-2">When</p>
            <div className="flex gap-2 mb-2">
              {(["now", "later"] as const).map((m) => (
                <button
                  key={m}
                  onClick={() => setScheduleMode(m)}
                  className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                    scheduleMode === m
                      ? "bg-brand-600 text-white"
                      : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                  }`}
                >
                  {m === "now" ? "Post now" : "Schedule"}
                </button>
              ))}
            </div>
            {scheduleMode === "later" && (
              <input
                type="datetime-local"
                value={scheduledAt}
                onChange={(e) => setScheduledAt(e.target.value)}
                min={new Date().toISOString().slice(0, 16)}
                className="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
            )}
          </div>
        </div>

        {/* Submit */}
        <div className="p-6 border-t border-gray-100">
          <button
            onClick={handleSubmit}
            disabled={submitting || uploadingCount > 0}
            className="w-full bg-brand-600 hover:bg-brand-700 disabled:opacity-50 text-white font-semibold py-3 rounded-xl transition-colors"
          >
            {submitting
              ? "Posting…"
              : scheduleMode === "now"
              ? "Post now"
              : "Schedule post"}
          </button>
        </div>
      </div>

      {/* Right: preview */}
      <div className="w-80 flex-shrink-0 hidden lg:flex flex-col">
        <div className="p-4 border-b border-gray-100">
          <p className="text-sm font-semibold text-gray-700">Preview</p>
        </div>
        <div className="flex-1 overflow-hidden">
          <PostPreview text={text} mediaPreviews={mediaPreviews} platforms={selectedPlatforms} />
        </div>
      </div>
    </div>
  );
}
