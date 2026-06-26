import { motion } from "framer-motion";
import { type LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface StatCardProps {
  icon: LucideIcon;
  label: string;
  value: string;
  trend?: string;
  trendUp?: boolean;
  delay?: number;
}

export function StatCard({ icon: Icon, label, value, trend, trendUp, delay = 0 }: StatCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay, ease: "easeOut" }}
      className="glass gold-glow-hover rounded-xl3 p-6 relative overflow-hidden group"
    >
      <div className="absolute top-0 right-0 w-1 h-full bg-gradient-to-b from-gold to-gold-dark" />
      <div className="flex items-center justify-between mb-4">
        <div className="w-11 h-11 rounded-2xl bg-gold/10 flex items-center justify-center ring-1 ring-gold/20 group-hover:bg-gold/15 transition-colors">
          <Icon size={20} className="text-gold-light" strokeWidth={2} />
        </div>
        {trend && (
          <span className={cn("text-[11px] font-bold px-2 py-1 rounded-full", trendUp ? "text-green bg-green/10" : "text-red bg-red/10")}>
            {trend}
          </span>
        )}
      </div>
      <div className="text-[28px] font-extrabold gold-text leading-none">{value}</div>
      <div className="text-[12.5px] text-muted mt-2">{label}</div>
    </motion.div>
  );
}
