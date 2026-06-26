import { NavLink, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import {
  LayoutDashboard,
  Users,
  Gem,
  LineChart,
  Megaphone,
  Settings,
  LogOut,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";

const nav = [
  {
    label: "عمومی",
    items: [
      { to: "/", label: "داشبورد", icon: LayoutDashboard },
      { to: "/users", label: "کاربران", icon: Users },
      { to: "/vip", label: "اشتراک VIP", icon: Gem },
    ],
  },
  {
    label: "محتوا و ارتباط",
    items: [
      { to: "/analysis", label: "تحلیل هفتگی", icon: LineChart },
      { to: "/broadcast", label: "پیام گروهی", icon: Megaphone },
    ],
  },
  {
    label: "سیستم",
    items: [{ to: "/settings", label: "تنظیمات", icon: Settings }],
  },
];

export function Sidebar() {
  const navigate = useNavigate();

  async function handleLogout() {
    try {
      await api.logout();
    } finally {
      navigate("/login", { replace: true });
    }
  }

  return (
    <aside className="fixed top-0 right-0 bottom-0 w-[268px] z-40 hidden lg:flex flex-col p-5 gap-1 border-l border-white/[0.06]">
      <div className="absolute inset-0 -z-10 bg-gradient-to-b from-[#0c0c0e] to-[#040405]" />
      <div className="flex flex-col items-center gap-3 pb-6 mb-3 border-b border-white/[0.07]">
        <motion.div
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.6, ease: "easeOut" }}
          className="relative"
        >
          <div className="absolute inset-0 rounded-full bg-gold/30 blur-xl animate-glowPulse" />
          <img src="/logo.svg" alt="Money MAP" className="relative w-16 h-16" />
        </motion.div>
        <div className="text-center">
          <div className="gold-text font-extrabold text-[15px] tracking-wide">MONEY MAP MARKET</div>
          <div className="text-[10.5px] text-muted mt-0.5">پنل مدیریت Money MAP</div>
        </div>
      </div>

      <nav className="flex-1 flex flex-col gap-5 overflow-y-auto pr-1">
        {nav.map((group) => (
          <div key={group.label}>
            <div className="text-[10.5px] font-bold text-white/30 px-3 mb-2 tracking-wider">
              {group.label}
            </div>
            <div className="flex flex-col gap-1">
              {group.items.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === "/"}
                  className={({ isActive }) =>
                    cn(
                      "group relative flex items-center gap-3 px-3.5 py-2.5 rounded-2xl text-[13.5px] font-medium transition-all duration-300",
                      isActive
                        ? "text-black bg-gradient-to-l from-gold-dark to-gold shadow-gold"
                        : "text-white/55 hover:text-gold-light hover:bg-white/[0.04]"
                    )
                  }
                >
                  {({ isActive }) => (
                    <>
                      <item.icon
                        size={17}
                        strokeWidth={2.2}
                        className={cn("shrink-0", isActive ? "text-black" : "text-white/45 group-hover:text-gold-light")}
                      />
                      <span>{item.label}</span>
                    </>
                  )}
                </NavLink>
              ))}
            </div>
          </div>
        ))}
      </nav>

      <button
        onClick={handleLogout}
        className="flex items-center gap-3 px-3.5 py-2.5 rounded-2xl text-[13.5px] font-medium text-red/80 hover:bg-red/10 hover:text-red transition-all duration-300 mt-2"
      >
        <LogOut size={17} strokeWidth={2.2} />
        خروج از پنل
      </button>
    </aside>
  );
}
