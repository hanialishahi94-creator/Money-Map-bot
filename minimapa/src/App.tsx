import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AppShell } from "@/components/layout/AppShell";
import { RequireAuth } from "@/components/RequireAuth";
import Dashboard from "@/pages/Dashboard";
import UsersPage from "@/pages/Users";
import VipPage from "@/pages/Vip";
import AnalysisPage from "@/pages/Analysis";
import BroadcastPage from "@/pages/Broadcast";
import SettingsPage from "@/pages/Settings";
import LoginPage from "@/pages/Login";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<RequireAuth />}>
          <Route element={<AppShell />}>
            <Route path="/" element={<Dashboard />} />
            <Route path="/users" element={<UsersPage />} />
            <Route path="/vip" element={<VipPage />} />
            <Route path="/analysis" element={<AnalysisPage />} />
            <Route path="/broadcast" element={<BroadcastPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Route>
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
