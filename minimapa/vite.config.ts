import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    proxy: {
      // در حالت dev، درخواست‌های /api به سرور Flask (admin_panel.py) فوروارد می‌شوند.
      // فلسک را با: cd moneymap_bot && python admin_panel.py  (پورت پیش‌فرض 8000) بالا بیار.
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
