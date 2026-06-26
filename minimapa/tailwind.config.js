/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0A0A0A",
        panel: "#111113",
        panel2: "#151517",
        card: "#131315",
        border: "rgba(255,255,255,0.08)",
        gold: {
          DEFAULT: "#D4AF37",
          light: "#F3DD86",
          dark: "#9C7A1F",
          glow: "rgba(212,175,55,0.35)",
        },
        muted: "#8C8A82",
        text: "#ECE9E2",
        green: "#2BBF7A",
        red: "#E5564F",
      },
      fontFamily: {
        sans: ["Vazirmatn", "Tahoma", "sans-serif"],
      },
      borderRadius: {
        xl2: "20px",
        xl3: "24px",
      },
      boxShadow: {
        gold: "0 8px 30px rgba(212,175,55,0.15)",
        "gold-lg": "0 20px 60px rgba(212,175,55,0.2)",
        glass: "0 8px 32px rgba(0,0,0,0.55)",
      },
      backdropBlur: {
        xs: "2px",
      },
      keyframes: {
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        glowPulse: {
          "0%, 100%": { opacity: 0.5 },
          "50%": { opacity: 1 },
        },
      },
      animation: {
        shimmer: "shimmer 3s linear infinite",
        glowPulse: "glowPulse 2.4s ease-in-out infinite",
      },
    },
  },
  plugins: [require("tailwindcss-rtl")],
};
