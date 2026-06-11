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

import axios from "axios";
import type { Profile, Channel, Post, AppSettings, User, Invite } from "./types";

const http = axios.create({ baseURL: "/api" });

// Called when any request comes back 401 — the app swaps to the auth screen.
let onUnauthorized: (() => void) | null = null;
export function setUnauthorizedHandler(fn: () => void) {
  onUnauthorized = fn;
}

http.interceptors.response.use(
  (r) => r,
  (error) => {
    const status = error.response?.status;
    const url: string = error.config?.url ?? "";
    // Auth endpoints handle their own 401s (wrong password etc.)
    if (status === 401 && !url.startsWith("/account/")) {
      onUnauthorized?.();
    }
    return Promise.reject(error);
  }
);

export const api = {
  account: {
    me: () => http.get<User>("/account/me").then((r) => r.data),
    signup: (invite_code: string, email: string, password: string) =>
      http.post<User>("/account/signup", { invite_code, email, password }).then((r) => r.data),
    login: (email: string, password: string) =>
      http.post<User>("/account/login", { email, password }).then((r) => r.data),
    logout: () => http.post("/account/logout"),
    changePassword: (current_password: string, new_password: string) =>
      http.post("/account/change-password", { current_password, new_password }),
    exportData: () => http.get("/account/export").then((r) => r.data),
    deleteAccount: () => http.delete("/account"),
    invites: {
      list: () => http.get<Invite[]>("/account/invites").then((r) => r.data),
      create: (note: string) =>
        http.post<{ token: string; expires_in_days: number }>("/account/invites", { note }).then((r) => r.data),
      revoke: (id: number) => http.post(`/account/invites/${id}/revoke`),
    },
  },

  profiles: {
    list: () => http.get<Profile[]>("/profiles/").then((r) => r.data),
    create: (name: string, avatar_color: string) =>
      http.post<Profile>("/profiles/", { name, avatar_color }).then((r) => r.data),
    update: (id: number, name: string, avatar_color: string) =>
      http.put<Profile>(`/profiles/${id}`, { name, avatar_color }).then((r) => r.data),
    delete: (id: number) => http.delete(`/profiles/${id}`),
  },

  channels: {
    list: (profile_id?: number) =>
      http.get<Channel[]>("/channels/", { params: { profile_id } }).then((r) => r.data),
    delete: (id: number) => http.delete(`/channels/${id}`),
  },

  auth: {
    getSettings: () => http.get<AppSettings>("/auth/settings").then((r) => r.data),
    saveSettings: (data: Partial<AppSettings>) => http.post("/auth/settings", data),
    connectBluesky: (profile_id: number, handle: string, app_password: string) =>
      http.post("/auth/bluesky", { profile_id, handle, app_password }).then((r) => r.data),
    metaOAuthUrl: (profile_id: number) =>
      http.get<{ url: string }>(`/auth/meta/url`, { params: { profile_id } }).then((r) => r.data),
    threadsOAuthUrl: (profile_id: number) =>
      http.get<{ url: string }>(`/auth/threads/url`, { params: { profile_id } }).then((r) => r.data),
    linkedinOAuthUrl: (profile_id: number) =>
      http.get<{ url: string }>(`/auth/linkedin/url`, { params: { profile_id } }).then((r) => r.data),
  },

  posts: {
    list: (params?: { profile_id?: number; status?: string; start?: string; end?: string }) =>
      http.get<Post[]>("/posts/", { params }).then((r) => r.data),
    get: (id: number) => http.get<Post>(`/posts/${id}`).then((r) => r.data),
    create: (data: {
      profile_id: number;
      text: string;
      media_paths: string[];
      channel_ids: number[];
      scheduled_at?: string | null;
    }) => http.post<Post>("/posts/", data).then((r) => r.data),
    update: (id: number, data: Partial<{
      text: string;
      media_paths: string[];
      channel_ids: number[];
      scheduled_at: string | null;
      status: string;
    }>) => http.put<Post>(`/posts/${id}`, data).then((r) => r.data),
    publish: (id: number) => http.post<Post>(`/posts/${id}/publish`).then((r) => r.data),
    delete: (id: number) => http.delete(`/posts/${id}`),
    upload: (file: File) => {
      const form = new FormData();
      form.append("file", file);
      return http.post<{ filename: string }>("/posts/upload", form).then((r) => r.data);
    },
  },
};
