import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Link } from "react-router-dom";
import { Users, Gem, Wallet, Hourglass, ArrowUpRight, Megaphone, LineChart, Settings as SettingsIcon } from "lucide-react";
import { AreaChart, Area, ResponsiveContainer, Tooltip, XAxis } from "recharts";
import { StatCard } from "@/components/StatCard";
import { Card, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

const quickLinks = [
  { to: "/users", label: "لیست کاربران", icon: Users, primary: true },
  { to: "/vip", label: "مدیریت VIP", icon: Gem, primary: true },
  { to: "/analysis", label: "تحلیل هفتگی", icon: LineChart },
  { to: "/broadcast", label: "پیام گروهی", icon: Megaphone },
  { to: "/settings", label: "تنظیمات", icon: SettingsIcon },
];

const WEEKDAY_FA = ["شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه"];

function toFaWeekday(dateStr: string) {
  // dateStr is "YYYY-MM-DD"; JS getDay(): 0=Sunday..6=Saturday → map to Persian week starting Saturday
  const d = new Date(dateStr);
  const jsDay = d.getDay(); // 0=Sun
  const map = [1, 2, 3, 4, 5, 6, 0]; // Sun->idx1 ... Sat->idx0
  return WEEKDAY_FA[map[jsDay]];
}

function toFaDigits(n: number | string) {
  const map: Record<string, string> = { "0": "۰", "1": "۱", "2": "۲", "3": "۳", "4": "۴", "5": "۵", "6": "۶", "7": "۷", "8": "۸", "9": "۹" };
  return String(n).replace(/[0-9]/g, (d) => map[d]);
}

export default function Dashboard() {
  const [stats, setStats] = useState({
    users_count: 0,
    vip_count: 0,
    vip_price_usdt: 0,
    vip_days: 0,
  });
  const [growthData, setGrowthData] = useState<{ name: string; users: number }[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .dashboard()
      .then((res) => {
        setStats({
          users_count: res.users_count,
          vip_count: res.vip_count,
          vip_price_usdt: res.vip_price_usdt,
          vip_days: res.vip_days,
        });
        setGrowthData(res.growth.map((g) => ({ name: toFaWeekday(g.date), users: g.count })));
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="flex flex-col gap-7">
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-extrabold gold-text">داشبورد مدیریت</h1>
          <p className="text-muted text-sm mt-1">نگاهی کلی به وضعیت بات و اشتراک‌های Money MAP</p>
        </div>
      </motion.div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        <StatCard icon={Users} label="کل کاربران ثبت‌نام شده" value={toFaDigits(stats.users_count)} delay={0} />
        <StatCard icon={Gem} label="اعضای فعال VIP" value={toFaDigits(stats.vip_count)} delay={0.05} />
        <StatCard icon={Wallet} label="قیمت فعلی اشتراک" value={`${toFaDigits(stats.vip_price_usdt)}$`} delay={0.1} />
        <StatCard icon={Hourglass} label="مدت اشتراک (روز)" value={toFaDigits(stats.vip_days)} delay={0.15} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>
              <ArrowUpRight size={16} /> رشد کاربران هفته اخیر
            </CardTitle>
            <span className="text-[11px] text-green bg-green/10 px-2.5 py-1 rounded-full font-bold">۷ روز گذشته</span>
          </CardHeader>
          <div className="h-[230px] -mr-2">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={growthData}>
                <defs>
                  <linearGradient id="goldFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#D4AF37" stopOpacity={0.45} />
                    <stop offset="100%" stopColor="#D4AF37" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="name" tick={{ fill: "#8C8A82", fontSize: 11 }} axisLine={false} tickLine={false} />
                <Tooltip
                  contentStyle={{
                    background: "#151517",
                    border: "1px solid rgba(212,175,55,0.25)",
                    borderRadius: 14,
                    fontSize: 12,
                    color: "#ECE9E2",
                  }}
                  labelStyle={{ color: "#F3DD86" }}
                />
                <Area type="monotone" dataKey="users" stroke="#D4AF37" strokeWidth={2.5} fill="url(#goldFill)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>دسترسی سریع</CardTitle>
          </CardHeader>
          <div className="flex flex-col gap-2.5">
            {quickLinks.map((q) => (
              <Link key={q.to} to={q.to}>
                <Button variant={q.primary ? "default" : "ghost"} className="justify-start w-full">
                  <q.icon size={16} />
                  {q.label}
                </Button>
              </Link>
            ))}
          </div>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>راهنمای سریع پنل</CardTitle>
        </CardHeader>
        <CardDescription className="leading-8 text-[13px]">
          از بخش <b className="text-gold-light">کاربران</b> می‌توانی با جستجو و فیلتر، هر کاربری را پیدا کنی. از بخش{" "}
          <b className="text-gold-light">اشتراک VIP</b> اشتراک‌ها را تمدید یا حذف کن. از بخش{" "}
          <b className="text-gold-light">تحلیل هفتگی</b> متن و عکس تحلیل هر دارایی را به‌روزرسانی کن. از بخش{" "}
          <b className="text-gold-light">پیام گروهی</b> برای کاربران VIP یا غیر VIP پیام ارسال کن.
        </CardDescription>
      </Card>
    </div>
  );
}
