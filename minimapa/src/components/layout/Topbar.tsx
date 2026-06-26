import { useEffect, useState } from "react";
import { Bell, Search } from "lucide-react";
import { api } from "@/lib/api";

export function Topbar() {
  const [username, setUsername] = useState("ادمین");

  useEffect(() => {
    api
      .me()
      .then((res) => {
        if (res.authenticated && res.username) setUsername(res.username);
      })
      .catch(() => {});
  }, []);

  return (
    <header className="sticky top-0 z-30 lg:mr-[268px] glass-strong border-b border-white/[0.06]">
      <div className="flex items-center justify-between px-6 md:px-8 py-4">
        <div className="hidden md:flex items-center gap-2 bg-white/[0.03] border border-white/10 rounded-2xl px-4 py-2.5 w-72 focus-within:border-gold/50 transition-colors">
          <Search size={16} className="text-muted" />
          <input
            placeholder="جستجو..."
            className="bg-transparent outline-none text-sm placeholder:text-muted/60 w-full"
          />
        </div>

        <div className="flex items-center gap-4">
          <button className="relative w-10 h-10 rounded-xl flex items-center justify-center text-muted hover:text-gold-light hover:bg-white/[0.05] transition-colors">
            <Bell size={18} />
            <span className="absolute top-2 right-2 w-1.5 h-1.5 rounded-full bg-gold animate-glowPulse" />
          </button>
          <div className="flex items-center gap-3 pl-1">
            <div className="text-right hidden sm:block">
              <div className="text-[13px] font-bold">{username}</div>
              <div className="text-[11px] text-muted">مدیر سیستم</div>
            </div>
            <div className="w-10 h-10 rounded-full bg-gradient-to-br from-gold to-gold-dark flex items-center justify-center font-extrabold text-black gold-ring">
              {username.charAt(0).toUpperCase()}
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}
