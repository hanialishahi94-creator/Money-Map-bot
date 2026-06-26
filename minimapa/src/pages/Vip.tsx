import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Gem, Plus, RefreshCcw, Trash2, Loader2 } from "lucide-react";
import { Card, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { api, ApiError } from "@/lib/api";

interface VipRow {
  user_id: number;
  name: string;
  phone: string;
  username: string;
  expire_at: number;
  is_active: boolean;
  days: number;
  hours: number;
  expire_str: string;
}

export default function VipPage() {
  const [vip, setVip] = useState<VipRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<number | null>(null);

  const [phone, setPhone] = useState("");
  const [days, setDays] = useState("");
  const [quickError, setQuickError] = useState("");
  const [quickLoading, setQuickLoading] = useState(false);

  const [extendDays, setExtendDays] = useState<Record<number, string>>({});

  async function load() {
    setLoading(true);
    try {
      const res = await api.vipList();
      setVip(res.vip);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleQuickActivate() {
    setQuickError("");
    if (!phone.trim()) {
      setQuickError("شماره موبایل را وارد کن.");
      return;
    }
    setQuickLoading(true);
    try {
      const res = await api.vipQuickActivate(phone.trim(), days ? parseInt(days, 10) : 0);
      if (res.ok) {
        setPhone("");
        setDays("");
        await load();
      } else {
        setQuickError(res.error || "خطایی رخ داد.");
      }
    } catch (err) {
      setQuickError(err instanceof ApiError ? err.message : "خطا در ارتباط با سرور.");
    } finally {
      setQuickLoading(false);
    }
  }

  async function handleExtend(userId: number) {
    setBusyId(userId);
    try {
      const d = extendDays[userId] ? parseInt(extendDays[userId], 10) : 30;
      await api.vipExtend(userId, d);
      await load();
    } finally {
      setBusyId(null);
    }
  }

  async function handleRemove(userId: number) {
    setBusyId(userId);
    try {
      await api.vipRemove(userId);
      await load();
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-extrabold gold-text">مدیریت اشتراک VIP</h1>
        <p className="text-muted text-sm mt-1">فعال‌سازی، تمدید و مدیریت اعضای ویژه کانال</p>
      </div>

      <Card className="gold-ring">
        <CardHeader>
          <CardTitle><Plus size={16} /> فعال‌سازی / تمدید سریع</CardTitle>
        </CardHeader>
        <CardDescription className="mb-4">شماره موبایل کاربر را وارد کن. اگر روز را خالی بگذاری، مقدار پیش‌فرض استفاده می‌شود.</CardDescription>
        <div className="flex flex-wrap gap-3 items-end">
          <div className="flex-1 min-w-[200px]">
            <label className="text-xs font-bold text-white/70 block mb-2">شماره موبایل کاربر</label>
            <Input value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="مثلاً 0912xxxxxxx" />
          </div>
          <div className="w-32">
            <label className="text-xs font-bold text-white/70 block mb-2">تعداد روز</label>
            <Input value={days} onChange={(e) => setDays(e.target.value)} placeholder="30" />
          </div>
          <Button onClick={handleQuickActivate} disabled={quickLoading}>
            {quickLoading ? <Loader2 size={15} className="animate-spin" /> : <Gem size={15} />} فعال‌سازی / تمدید
          </Button>
        </div>
        {quickError && <div className="text-red text-xs mt-3">{quickError}</div>}
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>اعضای اشتراک VIP ({vip.length} نفر)</CardTitle>
        </CardHeader>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-white/[0.07] text-[11px] text-muted uppercase tracking-wider">
                <th className="text-right py-3 font-bold">اسم</th>
                <th className="text-right py-3 font-bold">شماره</th>
                <th className="text-right py-3 font-bold">وضعیت</th>
                <th className="text-right py-3 font-bold">باقی‌مانده</th>
                <th className="text-right py-3 font-bold">تاریخ انقضا</th>
                <th className="text-right py-3 font-bold">عملیات</th>
              </tr>
            </thead>
            <tbody>
              {vip.map((v, i) => (
                <motion.tr
                  key={v.user_id}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: i * 0.05 }}
                  className="border-b border-white/[0.04] hover:bg-gold/[0.03] transition-colors"
                >
                  <td className="py-3.5 font-medium">{v.name || "—"}</td>
                  <td className="py-3.5 text-muted">{v.phone || "—"}</td>
                  <td className="py-3.5">
                    {v.is_active ? (
                      v.days <= 3 ? <Badge variant="gold" dot>رو به اتمام</Badge> : <Badge variant="green" dot>فعال</Badge>
                    ) : (
                      <Badge variant="red">منقضی شده</Badge>
                    )}
                  </td>
                  <td className="py-3.5 text-muted">{v.is_active ? `${v.days} روز و ${v.hours} ساعت` : "—"}</td>
                  <td className="py-3.5 text-muted">{v.expire_str}</td>
                  <td className="py-3.5">
                    <div className="flex gap-2">
                      <Input
                        value={extendDays[v.user_id] ?? ""}
                        onChange={(e) => setExtendDays((s) => ({ ...s, [v.user_id]: e.target.value }))}
                        placeholder="30"
                        className="w-16 h-9 px-2 text-center"
                      />
                      <Button size="sm" disabled={busyId === v.user_id} onClick={() => handleExtend(v.user_id)}>
                        {busyId === v.user_id ? <Loader2 size={13} className="animate-spin" /> : <RefreshCcw size={13} />} تمدید
                      </Button>
                      <Button size="sm" variant="danger" disabled={busyId === v.user_id} onClick={() => handleRemove(v.user_id)}>
                        <Trash2 size={13} />
                      </Button>
                    </div>
                  </td>
                </motion.tr>
              ))}
              {!loading && vip.length === 0 && (
                <tr>
                  <td colSpan={6} className="text-center py-10 text-muted">هیچ عضو VIP پیدا نشد.</td>
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
