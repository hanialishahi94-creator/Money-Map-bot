import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { UploadCloud, X, Coins, DollarSign, Bitcoin, Loader2, Check } from "lucide-react";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

const ASSETS = [
  { key: "gold", label: "طلا", icon: Coins, color: "text-gold-light" },
  { key: "dollar", label: "دلار", icon: DollarSign, color: "text-green" },
  { key: "bitcoin", label: "بیتکوین", icon: Bitcoin, color: "text-orange-400" },
];

interface AnalysisData {
  asset: string;
  analysis_date: string;
  text: string;
  image_path: string | null;
  updated_at: number;
}

export default function AnalysisPage() {
  const [active, setActive] = useState("gold");
  const asset = ASSETS.find((a) => a.key === active)!;

  const [data, setData] = useState<Record<string, AnalysisData>>({});
  const [date, setDate] = useState("");
  const [text, setText] = useState("");
  const [image, setImage] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  async function load() {
    setLoading(true);
    try {
      const res = await api.analyses();
      setData(res.analyses);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  useEffect(() => {
    const d = data[active];
    setDate(d?.analysis_date || "");
    setText(d?.text || "");
    setImage(null);
    setPreview(d?.image_path ? `/static/${d.image_path}` : null);
    setSaved(false);
  }, [active, data]);

  function handleFileSelect(file: File | null) {
    setImage(file);
    if (file) {
      setPreview(URL.createObjectURL(file));
    }
  }

  async function handleSave() {
    setSaving(true);
    setSaved(false);
    try {
      const res = await api.saveAnalysis(active, date, text, image);
      if (res.ok) {
        setSaved(true);
        await load();
      }
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-extrabold gold-text">تحلیل هفتگی بازار</h1>
        <p className="text-muted text-sm mt-1">متن و عکس تحلیل هر دارایی را به‌روزرسانی کن — فوراً داخل بات نمایش داده می‌شود.</p>
      </div>

      <div className="flex gap-2">
        {ASSETS.map((a) => (
          <button
            key={a.key}
            onClick={() => setActive(a.key)}
            className={`flex items-center gap-2 px-5 py-2.5 rounded-2xl text-sm font-bold transition-all duration-300 ${
              active === a.key
                ? "bg-gradient-to-l from-gold-dark to-gold text-black shadow-gold"
                : "bg-white/[0.03] border border-white/10 text-muted hover:text-gold-light hover:border-gold/30"
            }`}
          >
            <a.icon size={16} />
            {a.label}
          </button>
        ))}
      </div>

      <motion.div key={active} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>
        <Card>
          <CardHeader>
            <CardTitle>
              <asset.icon size={16} className={asset.color} /> تحلیل {asset.label}
            </CardTitle>
          </CardHeader>

          <div className="grid md:grid-cols-2 gap-6">
            <div className="flex flex-col gap-4">
              <div>
                <label className="text-xs font-bold text-white/70 block mb-2">تاریخ تحلیل</label>
                <Input value={date} onChange={(e) => setDate(e.target.value)} placeholder="مثلاً: ۱ تیر ۱۴۰۴" />
              </div>
              <div>
                <label className="text-xs font-bold text-white/70 block mb-2">متن تحلیل</label>
                <Textarea value={text} onChange={(e) => setText(e.target.value)} placeholder="متن تحلیل را بنویس..." />
              </div>
              <Button className="self-start" disabled={saving || loading} onClick={handleSave}>
                {saving ? <Loader2 size={15} className="animate-spin" /> : saved ? <Check size={15} /> : <UploadCloud size={15} />}{" "}
                {saved ? "ذخیره شد" : `ذخیره تحلیل ${asset.label}`}
              </Button>
            </div>

            <div>
              <label className="text-xs font-bold text-white/70 block mb-2">عکس تحلیل</label>
              <input
                ref={fileInputRef}
                type="file"
                accept="image/png,image/jpeg,image/webp"
                className="hidden"
                onChange={(e) => handleFileSelect(e.target.files?.[0] || null)}
              />
              <div
                onClick={() => fileInputRef.current?.click()}
                className="relative h-[260px] rounded-2xl border-2 border-dashed border-gold/25 bg-gold/[0.03] flex flex-col items-center justify-center gap-3 hover:border-gold/50 hover:bg-gold/[0.05] transition-all duration-300 cursor-pointer group overflow-hidden"
              >
                {preview ? (
                  <img src={preview} alt="پیش‌نمایش تحلیل" className="absolute inset-0 w-full h-full object-cover" />
                ) : (
                  <>
                    <div className="w-14 h-14 rounded-2xl bg-gold/10 flex items-center justify-center group-hover:scale-110 transition-transform">
                      <UploadCloud size={24} className="text-gold-light" />
                    </div>
                    <div className="text-center px-6">
                      <div className="text-sm font-bold text-text">عکس را بکش و رها کن</div>
                      <div className="text-xs text-muted mt-1">یا کلیک کن — PNG, JPG, WEBP</div>
                    </div>
                  </>
                )}
                {preview && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      setPreview(null);
                      setImage(null);
                      if (fileInputRef.current) fileInputRef.current.value = "";
                    }}
                    className="absolute top-3 left-3 w-7 h-7 rounded-lg bg-black/60 flex items-center justify-center text-white hover:text-red hover:bg-black/80 transition-colors z-10"
                  >
                    <X size={14} />
                  </button>
                )}
              </div>
            </div>
          </div>
        </Card>
      </motion.div>
    </div>
  );
}
