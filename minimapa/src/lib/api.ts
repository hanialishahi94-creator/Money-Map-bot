/**
 * کلاینت ساده برای صحبت با Flask API (admin_panel.py).
 * در حالت توسعه، vite.config.ts درخواست‌های /api را به پورت Flask پروکسی می‌کند،
 * بنابراین همیشه می‌توان مسیر نسبی "/api/..." را صدا زد — هم در dev و هم در production.
 */

const BASE = "/api";

class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    credentials: "include",
    headers:
      options.body instanceof FormData
        ? undefined
        : { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });

  let data: any = null;
  try {
    data = await res.json();
  } catch {
    // ممکنه بدنه‌ی پاسخ خالی باشه
  }

  if (!res.ok) {
    throw new ApiError(data?.error || "خطایی رخ داد", res.status);
  }
  return data as T;
}

export const api = {
  login: (username: string, password: string) =>
    request<{ ok: boolean; username?: string; error?: string }>("/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),

  logout: () => request<{ ok: boolean }>("/logout", { method: "POST" }),

  me: () => request<{ authenticated: boolean; username?: string }>("/me"),

  dashboard: () =>
    request<{
      users_count: number;
      vip_count: number;
      vip_price_usdt: number;
      vip_days: number;
      growth: { date: string; count: number }[];
    }>("/dashboard"),

  users: () =>
    request<{
      users: {
        user_id: number;
        name: string;
        phone: string;
        username: string;
        joined_at: number;
        is_vip: boolean;
      }[];
    }>("/users"),

  deleteUser: (userId: number) =>
    request<{ ok: boolean }>(`/users/${userId}`, { method: "DELETE" }),

  activateVipForUser: (userId: number, days?: number) =>
    request<{ ok: boolean; expire_at: number }>(
      `/users/${userId}/activate-vip`,
      { method: "POST", body: JSON.stringify({ days }) }
    ),

  removeVipForUser: (userId: number) =>
    request<{ ok: boolean }>(`/users/${userId}/remove-vip`, {
      method: "POST",
    }),

  vipList: () =>
    request<{
      vip: {
        user_id: number;
        name: string;
        phone: string;
        username: string;
        expire_at: number;
        is_active: boolean;
        days: number;
        hours: number;
        expire_str: string;
      }[];
    }>("/vip"),

  vipQuickActivate: (phone: string, days: number) =>
    request<{ ok: boolean; user_id?: number; expire_at?: number; error?: string }>(
      "/vip/activate",
      { method: "POST", body: JSON.stringify({ phone, days }) }
    ),

  vipExtend: (userId: number, days: number) =>
    request<{ ok: boolean; expire_at: number }>(`/vip/${userId}/extend`, {
      method: "POST",
      body: JSON.stringify({ days }),
    }),

  vipRemove: (userId: number) =>
    request<{ ok: boolean }>(`/vip/${userId}/remove`, { method: "POST" }),

  analyses: () =>
    request<{
      analyses: Record<
        string,
        { asset: string; analysis_date: string; text: string; image_path: string | null; updated_at: number }
      >;
      labels: Record<string, string>;
    }>("/analysis"),

  saveAnalysis: (
    asset: string,
    analysisDate: string,
    text: string,
    image?: File | null
  ) => {
    const form = new FormData();
    form.append("asset", asset);
    form.append("analysis_date", analysisDate);
    form.append("text", text);
    if (image) form.append("image", image);
    return request<{ ok: boolean; error?: string }>("/analysis", {
      method: "POST",
      body: form,
    });
  },

  broadcast: (target: "all" | "vip" | "novip", text: string) =>
    request<{ ok: boolean; total: number; sent: number; failed: number }>(
      "/broadcast",
      { method: "POST", body: JSON.stringify({ target, text }) }
    ),

  settings: () =>
    request<{
      vip_price_usdt: number;
      vip_days: number;
      referral_enabled: boolean;
      referral_required_count: number;
    }>("/settings"),

  saveSettings: (vipPriceUsdt: number, vipDays: number) =>
    request<{ ok: boolean }>("/settings", {
      method: "POST",
      body: JSON.stringify({ vip_price_usdt: vipPriceUsdt, vip_days: vipDays }),
    }),

  saveReferralSettings: (referralEnabled: boolean, requiredCount: number) =>
    request<{ ok: boolean }>("/settings", {
      method: "POST",
      body: JSON.stringify({
        referral_enabled: referralEnabled,
        referral_required_count: requiredCount,
      }),
    }),
};

export { ApiError };
