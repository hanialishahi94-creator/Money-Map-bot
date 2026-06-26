import { useEffect, useState } from "react";
import { Save, Wallet, Hourglass, Loader2, Check } from "lucide-react";
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

  useEffect(() => {
    api
      .settings()
      .then((res) => {
        setPrice(String(res.vip_price_usdt));
        setDays(String(res.vip_days));
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
    </div>
  );
}
