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

export interface Profile {
  id: number;
  name: string;
  avatar_color: string;
  created_at: string;
}

export interface Channel {
  id: number;
  profile_id: number;
  platform: Platform;
  display_name: string;
  platform_user_id: string | null;
  is_connected: boolean;
}

export type Platform = "instagram" | "facebook" | "bluesky" | "threads" | "linkedin";

export interface PostChannel {
  id: number;
  channel_id: number;
  status: "pending" | "published" | "failed";
  error_message: string | null;
  platform_post_id: string | null;
  published_at: string | null;
  channel: Channel;
}

export interface Post {
  id: number;
  profile_id: number;
  text: string;
  media_paths: string[];
  scheduled_at: string | null;
  published_at: string | null;
  status: "draft" | "scheduled" | "published" | "failed" | "partial";
  created_at: string;
  post_channels: PostChannel[];
}

export interface AppSettings {
  meta_app_id: string;
  meta_app_secret: string;
  threads_app_id: string;
  threads_app_secret: string;
  linkedin_client_id: string;
  linkedin_client_secret: string;
  public_media_base_url: string;
  oauth_redirect_uris?: {
    meta: string;
    threads: string;
    linkedin: string;
  };
}

export interface User {
  id: number;
  email: string;
  is_admin: boolean;
  created_at: string;
}

export interface Passkey {
  id: number;
  label: string;
  created_at: string;
  last_used_at: string | null;
}

export interface Invite {
  id: number;
  note: string;
  created_at: string;
  expires_at: string | null;
  used_at: string | null;
  revoked: boolean;
}

export type View = "compose" | "calendar" | "posts" | "settings";
