import { Routes, Route, Link, NavLink } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { HomeIcon, IdCardIcon, ChainIcon, ShieldIcon } from "./components/Icons.jsx";
import LanguageSwitcher from "./components/LanguageSwitcher.jsx";
import Landing from "./pages/Landing.jsx";
import Setup from "./pages/Setup.jsx";
import Capture from "./pages/Capture.jsx";
import Pipeline from "./pages/Pipeline.jsx";
import FaceCapture from "./pages/FaceCapture.jsx";
import Result from "./pages/Result.jsx";
import Audit from "./pages/Audit.jsx";
import AdminWatchlist from "./pages/AdminWatchlist.jsx";

export default function App() {
  const { t } = useTranslation();
  return (
    <div className="app-shell">
      <aside className="side-rail">
        <span className="rail-logo" aria-hidden="true">🛂</span>
        <NavLink to="/" end title={t("nav.home")}><HomeIcon /></NavLink>
        <NavLink to="/verify/setup" title={t("nav.setup")}><IdCardIcon /></NavLink>
        <NavLink to="/audit" title={t("nav.audit")}><ChainIcon /></NavLink>
        <NavLink to="/admin/watchlist" title={t("nav.admin")}><ShieldIcon /></NavLink>
      </aside>
      <div className="app-main">
        <header className="topbar">
          <Link to="/" className="brand" style={{ textDecoration: "none" }}>
            <span className="brand-text">
              {t("appName")}
              <small>{t("appTagline")}</small>
            </span>
          </Link>
          <nav>
            <Link to="/audit">{t("nav.audit")}</Link>
            <Link to="/admin/watchlist">{t("nav.admin")}</Link>
            <LanguageSwitcher />
            <Link to="/verify/setup" className="btn-gradient">{t("nav.startVerification")}</Link>
          </nav>
        </header>
        <main className="page">
          <Routes>
            <Route path="/" element={<Landing />} />
            <Route path="/verify/setup" element={<Setup />} />
            <Route path="/verify/capture/:sessionId" element={<Capture />} />
            <Route path="/verify/pipeline/:sessionId" element={<Pipeline />} />
            <Route path="/verify/face/:sessionId" element={<FaceCapture />} />
            <Route path="/verify/result/:sessionId" element={<Result />} />
            <Route path="/audit" element={<Audit />} />
            <Route path="/admin/watchlist" element={<AdminWatchlist />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}
