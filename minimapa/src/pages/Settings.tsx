import { useEffect, useState } from "react";
import { Save, Wallet, Hourglass, Loader2, Check, Users } from "lucide-react";
import { Card, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

export default function SettingsPage() {
  const [price, setPrice] = useState("20");
  const [days, setDays] = useState("30");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const [referralEnabled, setReferralEnabled] = useState(false);
  const [referralCount, setReferralCount] = useState("5");
  const [referralSaving, setReferralSaving] = useState(false);
  const [referralSaved, setReferralSaved] = useState(false);

  useEffect(() => {
    api
      .settings()
      .then((res) => {
        setPrice(String(res.vip_price_usdt));
        setDays(String(res.vip_days));
        setReferralEnabled(Boolean(res.referral_enabled));
        setReferralCount(String(res.referral_required_count ?? 5));
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  async function handleSave() {
    setSaving(true);
    setSaved(false);
    try {
      const res = await api.saveSettings(parseFloat(price) || 0, parseInt(days, 10) || 0);
      if (res.ok) setSaved(true);
    } finally {
      setSaving(false);
    }
  }

  async function handleToggleReferral(next: boolean) {
    setReferralEnabled(next);
    setReferralSaved(false);
    setReferralSaving(true);
    try {
      const res = await api.saveReferralSettings(next, parseInt(referralCount, 10) || 5);
      if (res.ok) setReferralSaved(true);
    } finally {
      setReferralSaving(false);
    }
  }

  async function handleSaveReferralCount() {
    setReferralSaving(true);
    setReferralSaved(false);
    try {
      const res = await api.saveReferralSettings(referralEnabled, parseInt(referralCount, 10) || 5);
      if (res.ok) setReferralSaved(true);
    } finally {
      setReferralSaving(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-extrabold gold-text">تنظیمات کانال</h1>
        <p className="text-muted text-sm mt-1">قیمت و مدت زمان اشتراک VIP را از همینجا تغییر بده</p>
      </div>

      <Card className="max-w-xl">
        <CardHeader>
          <CardTitle><Wallet size={16} /> قیمت و مدت اشتراک</CardTitle>
        </CardHeader>
        <CardDescription className="mb-5">
          هر تغییری که اینجا ذخیره کنی، از همین الان روی قیمت و مدت نمایش‌داده‌شده در بات (برای کاربران جدید) اعمال می‌شود.
        </CardDescription>
        <div className="flex flex-col gap-5">
          <div>
            <label className="text-xs font-bold text-white/70 flex items-center gap-1.5 mb-2">
              <Wallet size={13} /> قیمت اشتراک VIP (تتر / USDT)
            </label>
            <Input type="number" value={price} onChange={(e) => { setPrice(e.target.value); setSaved(false); }} disabled={loading} />
          </div>
          <div>
            <label className="text-xs font-bold text-white/70 flex items-center gap-1.5 mb-2">
              <Hourglass size={13} /> مدت اشتراک (روز)
            </label>
            <Input type="number" value={days} onChange={(e) => { setDays(e.target.value); setSaved(false); }} disabled={loading} />
          </div>
          <Button className="self-start" disabled={saving || loading} onClick={handleSave}>
            {saving ? <Loader2 size={15} className="animate-spin" /> : saved ? <Check size={15} /> : <Save size={15} />}{" "}
            {saved ? "ذخیره شد" : "ذخیره تنظیمات"}
          </Button>
        </div>
      </Card>

      <Card className="max-w-xl">
        <CardHeader>
          <CardTitle><Users size={16} /> کمپین معرفی دوستان (رفرال)</CardTitle>
        </CardHeader>
        <CardDescription className="mb-5">
          وقتی این کمپین فعال باشه، کاربرها می‌تونن با معرفی تعداد مشخصی دوست (که شماره موبایلشون رو هم ثبت کرده باشن)،
          عضویت کانال سیگنال رو به‌صورت رایگان دریافت کنن. غیرفعال کردنش، قیمت و مدت اشتراک پولی بالا رو دست نمی‌زنه و همونطور باقی می‌مونه.
        </CardDescription>
        <div className="flex flex-col gap-5">
          <div className="flex items-center justify-between">
            <label className="text-xs font-bold text-white/70 flex items-center gap-1.5">
              <Users size={13} /> وضعیت کمپین معرفی دوستان
            </label>
            <button
              type="button"
              role="switch"
              aria-checked={referralEnabled}
              disabled={loading || referralSaving}
              onClick={() => handleToggleReferral(!referralEnabled)}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors disabled:opacity-50 ${
                referralEnabled ? "bg-amber-500" : "bg-white/15"
              }`}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                  referralEnabled ? "translate-x-6" : "translate-x-1"
                }`}
              />
            </button>
          </div>
          <div>
            <label className="text-xs font-bold text-white/70 flex items-center gap-1.5 mb-2">
              <Users size={13} /> تعداد معرفی لازم برای دریافت جایزه
            </label>
            <Input
              type="number"
              value={referralCount}
              onChange={(e) => { setReferralCount(e.target.value); setReferralSaved(false); }}
              disabled={loading}
            />
          </div>
          <Button className="self-start" disabled={referralSaving || loading} onClick={handleSaveReferralCount}>
            {referralSaving ? <Loader2 size={15} className="animate-spin" /> : referralSaved ? <Check size={15} /> : <Save size={15} />}{" "}
            {referralSaved ? "ذخیره شد" : "ذخیره تعداد"}
          </Button>
        </div>
      </Card>
    </div>
  );
}
