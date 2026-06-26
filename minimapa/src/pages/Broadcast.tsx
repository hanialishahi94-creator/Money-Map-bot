import { useState } from "react";
import { Send, Users, Gem, UserX, Loader2 } from "lucide-react";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

const TARGETS = [
  { key: "all", label: "همه کاربران", icon: Users },
  { key: "vip", label: "فقط VIP", icon: Gem },
  { key: "novip", label: "فقط بدون VIP", icon: UserX },
];

export default function BroadcastPage() {
  const [target, setTarget] = useState<"all" | "vip" | "novip">("all");
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState<{ total: number; sent: number; failed: number } | null>(null);

  async function handleSend() {
    if (!text.trim()) return;
    setSending(true);
    setResult(null);
    try {
      const res = await api.broadcast(target, text.trim());
      if (res.ok) {
        setResult({ total: res.total, sent: res.sent, failed: res.failed });
      }
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-extrabold gold-text">ارسال پیام گروهی</h1>
        <p className="text-muted text-sm mt-1">پیام موردنظر را بنویس و گروه مخاطبین هدف را انتخاب کن</p>
      </div>

      <div className="grid md:grid-cols-3 gap-5">
        <Card className="md:col-span-2">
          <CardHeader>
            <CardTitle>متن پیام</CardTitle>
          </CardHeader>
          <div className="flex flex-col gap-2 mb-5">
            <label className="text-xs font-bold text-white/70">گروه مخاطبین</label>
            <div className="flex gap-2 flex-wrap">
              {TARGETS.map((t) => (
                <button
                  key={t.key}
                  onClick={() => setTarget(t.key as any)}
                  className={`flex items-center gap-2 px-4 py-2.5 rounded-2xl text-xs font-bold transition-all duration-300 ${
                    target === t.key
                      ? "bg-gradient-to-l from-gold-dark to-gold text-black shadow-gold"
                      : "bg-white/[0.03] border border-white/10 text-muted hover:text-gold-light hover:border-gold/30"
                  }`}
                >
                  <t.icon size={14} />
                  {t.label}
                </button>
              ))}
            </div>
          </div>
          <Textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="متن پیام را اینجا بنویس..."
            className="min-h-[180px]"
          />
          <Button className="mt-4" disabled={sending || !text.trim()} onClick={handleSend}>
            {sending ? <Loader2 size={15} className="animate-spin" /> : <Send size={15} />} ارسال پیام
          </Button>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>پیش‌نمایش پیام</CardTitle>
          </CardHeader>
          <div className="glass-strong rounded-2xl p-4 min-h-[180px]">
            <div className="flex items-center gap-2 mb-3">
              <div className="w-8 h-8 rounded-full bg-gradient-to-br from-gold to-gold-dark flex items-center justify-center text-black text-xs font-extrabold">
                M
              </div>
              <span className="text-xs font-bold text-gold-light">Money MAP</span>
            </div>
            <p className="text-sm text-text/90 whitespace-pre-wrap leading-relaxed">
              {text || "متن پیام شما اینجا نمایش داده می‌شود..."}
            </p>
          </div>
          <div className="mt-5 grid grid-cols-3 gap-2 text-center">
            <div className="bg-white/[0.03] rounded-xl p-3">
              <div className="text-lg font-extrabold gold-text">{result ? result.total : "—"}</div>
              <div className="text-[10px] text-muted mt-1">مخاطب</div>
            </div>
            <div className="bg-white/[0.03] rounded-xl p-3">
              <div className="text-lg font-extrabold text-green">{result ? result.sent : "—"}</div>
              <div className="text-[10px] text-muted mt-1">موفق</div>
            </div>
            <div className="bg-white/[0.03] rounded-xl p-3">
              <div className="text-lg font-extrabold text-red">{result ? result.failed : "—"}</div>
              <div className="text-[10px] text-muted mt-1">ناموفق</div>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}
