import { useState, type FormEvent } from "react";
import { motion } from "framer-motion";
import { Eye, EyeOff, LogIn, AlertCircle } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { api, ApiError } from "@/lib/api";

export default function LoginPage() {
  const [show, setShow] = useState(false);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    if (!username || !password) {
      setError("نام کاربری و رمز عبور را وارد کن.");
      return;
    }
    setLoading(true);
    try {
      const res = await api.login(username, password);
      if (res.ok) {
        navigate("/", { replace: true });
      } else {
        setError(res.error || "نام کاربری یا رمز عبور اشتباه است.");
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "خطا در ارتباط با سرور.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center relative overflow-hidden px-6">
      <div className="absolute inset-0 -z-10 bg-[#0A0A0A]" />
      <div className="absolute top-[-10%] right-[-10%] w-[500px] h-[500px] rounded-full bg-gold/10 blur-[120px] -z-10" />
      <div className="absolute bottom-[-10%] left-[-10%] w-[500px] h-[500px] rounded-full bg-gold/[0.06] blur-[120px] -z-10" />
      <div className="absolute inset-0 -z-10 opacity-[0.03] bg-[repeating-linear-gradient(90deg,#D4AF37_0_1.5px,transparent_1.5px_42px)]" />

      <motion.div
        initial={{ opacity: 0, y: 24, scale: 0.97 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.6, ease: "easeOut" }}
        className="glass-strong w-full max-w-[400px] rounded-xl3 shadow-gold-lg p-9 text-center"
      >
        <motion.div
          initial={{ scale: 0.7, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ delay: 0.15, duration: 0.5 }}
          className="relative w-20 h-20 mx-auto mb-5"
        >
          <div className="absolute inset-0 rounded-full bg-gold/30 blur-2xl animate-glowPulse" />
          <img src="/logo.svg" alt="Money MAP" className="relative w-20 h-20" />
        </motion.div>

        <h1 className="text-xl font-extrabold gold-text mb-1">ورود به پنل مدیریت</h1>
        <p className="text-muted text-xs mb-8">برای مدیریت بات Money MAP وارد شو</p>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4 text-right">
          <div>
            <label className="text-xs font-bold text-white/70 block mb-2">نام کاربری</label>
            <Input
              autoFocus
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="نام کاربری ادمین"
            />
          </div>
          <div>
            <label className="text-xs font-bold text-white/70 block mb-2">رمز عبور</label>
            <div className="relative">
              <Input
                type={show ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="pl-11"
              />
              <button
                type="button"
                onClick={() => setShow((s) => !s)}
                className="absolute left-3.5 top-1/2 -translate-y-1/2 text-muted hover:text-gold-light transition-colors"
              >
                {show ? <EyeOff size={17} /> : <Eye size={17} />}
              </button>
            </div>
          </div>

          {error && (
            <div className="flex items-center gap-2 text-red text-xs bg-red/10 border border-red/20 rounded-xl px-3 py-2.5 text-right">
              <AlertCircle size={14} className="flex-shrink-0" />
              {error}
            </div>
          )}

          <Button type="submit" size="lg" className="w-full mt-2" disabled={loading}>
            <LogIn size={16} /> {loading ? "در حال ورود..." : "ورود به پنل"}
          </Button>
        </form>
      </motion.div>
    </div>
  );
}
