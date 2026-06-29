import { Fragment, useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { Search, Trash2, Gem, Loader2, Bell, BellOff, MessageSquare, Send, X } from "lucide-react";
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
  const [messagingId, setMessagingId] = useState<number | null>(null);
  const [messageText, setMessageText] = useState("");
  const [sendingMsg, setSendingMsg] = useState(false);
  const [msgFeedback, setMsgFeedback] = useState<{ type: "ok" | "error"; text: string } | null>(null);

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

  function openMessageBox(userId: number) {
    if (messagingId === userId) {
      setMessagingId(null);
      return;
    }
    setMessagingId(userId);
    setMessageText("");
    setMsgFeedback(null);
  }

  async function handleSendMessage(userId: number) {
    if (!messageText.trim()) return;
    setSendingMsg(true);
    setMsgFeedback(null);
    try {
      const res = await api.sendMessageToUser(userId, messageText.trim());
      if (res.ok) {
        setMsgFeedback({ type: "ok", text: "پیام با موفقیت ارسال شد." });
        setMessageText("");
      } else {
        setMsgFeedback({ type: "error", text: res.error || "ارسال پیام ناموفق بود." });
      }
    } catch (e: any) {
      setMsgFeedback({ type: "error", text: e?.message || "ارسال پیام ناموفق بود." });
    } finally {
      setSendingMsg(false);
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
                <Fragment key={u.user_id}>
                <motion.tr
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
                        <Button size="sm" variant="outline" disabled={busyId === u.user_id} onClick={() => openMessageBox(u.user_id)}>
                          <MessageSquare size={13} /> پیام
                        </Button>
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
                {messagingId === u.user_id && (
                  <tr className="bg-gold/[0.04]">
                    <td colSpan={6} className="py-4 px-2">
                      <div className="flex flex-col gap-3">
                        <div className="text-xs text-muted">
                          ارسال پیام مستقیم به <span className="text-gold-light font-bold">{u.name || u.user_id}</span> از طریق بات
                        </div>
                        <div className="flex flex-wrap items-start gap-2">
                          <textarea
                            value={messageText}
                            onChange={(e) => setMessageText(e.target.value)}
                            placeholder="متن پیام را بنویس..."
                            className="flex-1 min-w-[220px] min-h-[70px] rounded-xl bg-white/[0.03] border border-white/10 p-3 text-sm text-text outline-none focus:border-gold/40"
                          />
                          <div className="flex flex-col gap-2">
                            <Button
                              size="sm"
                              disabled={sendingMsg || !messageText.trim()}
                              onClick={() => handleSendMessage(u.user_id)}
                            >
                              {sendingMsg ? <Loader2 size={13} className="animate-spin" /> : <Send size={13} />} ارسال
                            </Button>
                            <Button size="sm" variant="outline" onClick={() => setMessagingId(null)}>
                              <X size={13} /> بستن
                            </Button>
                          </div>
                        </div>
                        {msgFeedback && (
                          <div className={`text-xs font-bold ${msgFeedback.type === "ok" ? "text-green" : "text-red"}`}>
                            {msgFeedback.text}
                          </div>
                        )}
                      </div>
                    </td>
                  </tr>
                )}
                </Fragment>
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