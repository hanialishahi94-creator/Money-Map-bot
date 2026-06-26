import { Outlet } from "react-router-dom";
import { motion } from "framer-motion";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";

export function AppShell() {
  return (
    <div className="min-h-screen noise-bg">
      <Sidebar />
      <div className="lg:mr-[268px]">
        <Topbar />
        <motion.main
          key={location.pathname}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, ease: "easeOut" }}
          className="max-w-[1200px] mx-auto px-6 md:px-8 py-8 md:py-10"
        >
          <Outlet />
        </motion.main>
      </div>
    </div>
  );
}
