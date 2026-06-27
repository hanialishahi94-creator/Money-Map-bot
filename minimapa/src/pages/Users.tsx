import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { Search, Trash2, Gem, Loader2, Bell, BellOff } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";

interface UserRow {
  user_id: number;
  name: string;
  phone: string;
  username: string;
  joined_at: number;
  is_vip: boolean;
}

export default function UsersPage() {
  const [q, setQ] = useState("");
  const [filter, setFilter] = useState<"all" | "vip" | "novip">("all");
  const [users, setUsers] = useState<UserRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [notify, setNotify] = useState<Record<number, boolean>>({});

  async function load() {
    setLoading(true);
    try {
      const res = await api.users();
      setUsers(res.users);
    } catch {
      // ignore — could show a toast in the future
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleActivate(userId: number) {
    setBusyId(userId);
    try {
      await api.activateVipForUser(userId, undefined, notify[userId] ?? true);
      await load();
    } finally {
      setBusyId(null);
    }
  }

  async function handleRemoveVip(userId: number) {
    setBusyId(userId);
    try {
      await api.removeVipForUser(userId, notify[userId] ?? true);
      await load();
    } finally {
      setBusyId(null);
    }
  }

  async function handleDelete(userId: number) {
    setBusyId(userId);
    try {
      await api.deleteUser(userId);
      await load();
    } finally {
      setBusyId(null);
    }
  }

  const rows = useMemo(() => {
    return users.filter((u) => {
      if (filter === "vip" && !u.is_vip) return false;
      if (filter === "novip" && u.is_vip) return false;
      if (q && !`${u.name}${u.phone}${u.username}${u.user_id}`.toLowerCase().includes(q.toLowerCase())) return false;
      return true;
    });
  }, [q, filter, users]);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-extrabold gold-text">کاربران بات</h1>
        <p className="text-muted text-sm mt-1">مدیریت و جستجوی همه‌ی کاربران ثبت‌نام‌شده</p>
      </div>

      <Card>
        <div className="flex flex-wrap gap-3 items-center mb-6">
          <div className="relative flex-1 min-w-[220px]">
            <Search size={16} className="absolute right-4 top-1/2 -translate-y-1/2 text-muted" />
            <Input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="جستجو بر اساس اسم، شماره، یوزرنیم یا آیدی..."
              className="pr-11"
            />
          </div>
          <div className="flex gap-2">
            {[
              { key: "all", label: "همه" },
              { key: "vip", label: "فقط VIP" },
              { key: "novip", label: "بدون VIP" },
            ].map((f) => (
              <button
                key={f.key}
                onClick={() => setFilter(f.key as any)}
                className={`px-4 py-2 rounded-2xl text-xs font-bold transition-all duration-300 ${
                  filter === f.key
                    ? "bg-gradient-to-l from-gold-dark to-gold text-black shadow-gold"
                    : "bg-white/[0.03] text-muted border border-white/10 hover:text-gold-light hover:border-gold/30"
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>

        <div className="text-xs text-muted mb-3">{rows.length} نتیجه از {users.length} کاربر</div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-white/[0.07] text-[11px] text-muted uppercase tracking-wider">
                <th className="text-right py-3 font-bold">اسم</th>
                <th className="text-right py-3 font-bold">شماره موبایل</th>
                <th className="text-right py-3 font-bold">یوزرنیم</th>
                <th className="text-right py-3 font-bold">آیدی</th>
                <th className="text-right py-3 font-bold">وضعیت</th>
                <th className="text-right py-3 font-bold">عملیات</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((u, i) => (
                <motion.tr
                  key={u.user_id}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: i * 0.04 }}
                  className="border-b border-white/[0.04] hover:bg-gold/[0.03] transition-colors group"
                >
                  <td className="py-3.5 font-medium">{u.name || "—"}</td>
                  <td className="py-3.5 text-muted">{u.phone || "—"}</td>
                  <td className="py-3.5 text-muted">{u.username ? `@${u.username}` : "—"}</td>
                  <td className="py-3.5 text-muted font-mono text-xs">{u.user_id}</td>
                  <td className="py-3.5">
                    {u.is_vip ? <Badge variant="green" dot>VIP فعال</Badge> : <Badge variant="gray">عادی</Badge>}
                  </td>
                  <td className="py-3.5">
                    <div className="flex flex-col gap-2">
                      <div className="flex gap-2">
                        {u.is_vip ? (
                          <Button size="sm" variant="danger" disabled={busyId === u.user_id} onClick={() => handleRemoveVip(u.user_id)}>
                            {busyId === u.user_id ? <Loader2 size={13} className="animate-spin" /> : <Trash2 size={13} />} حذف VIP
                          </Button>
                        ) : (
                          <Button size="sm" disabled={busyId === u.user_id} onClick={() => handleActivate(u.user_id)}>
                            {busyId === u.user_id ? <Loader2 size={13} className="animate-spin" /> : <Gem size={13} />} فعال‌سازی
                          </Button>
                        )}
                        <Button size="sm" variant="outline" disabled={busyId === u.user_id} onClick={() => handleDelete(u.user_id)}>
                          <Trash2 size={13} />
                        </Button>
                      </div>
                      <label className="flex items-center gap-1.5 text-[11px] text-white/60 cursor-pointer select-none">
                        <input
                          type="checkbox"
                          checked={notify[u.user_id] ?? true}
                          onChange={(e) => setNotify((s) => ({ ...s, [u.user_id]: e.target.checked }))}
                          className="accent-amber-500"
                        />
                        {(notify[u.user_id] ?? true) ? <Bell size={11} /> : <BellOff size={11} />} اطلاع به کاربر
                      </label>
                    </div>
                  </td>
                </motion.tr>
              ))}
              {!loading && rows.length === 0 && (
                <tr>
                  <td colSpan={6} className="text-center py-10 text-muted">هیچ کاربری با این فیلتر پیدا نشد.</td>
                </tr>
              )}
              {loading && (
                <tr>
                  <td colSpan={6} className="text-center py-10 text-muted">
                    <Loader2 size={18} className="animate-spin inline-block" />
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
