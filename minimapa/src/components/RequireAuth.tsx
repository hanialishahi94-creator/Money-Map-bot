import { useEffect, useState } from "react";
import { Navigate, Outlet } from "react-router-dom";
import { api } from "@/lib/api";

export function RequireAuth() {
  const [status, setStatus] = useState<"checking" | "ok" | "fail">("checking");

  useEffect(() => {
    api
      .me()
      .then((res) => setStatus(res.authenticated ? "ok" : "fail"))
      .catch(() => setStatus("fail"));
  }, []);

  if (status === "checking") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#0A0A0A]">
        <div className="w-10 h-10 rounded-full border-2 border-gold/30 border-t-gold animate-spin" />
      </div>
    );
  }

  if (status === "fail") {
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
}
