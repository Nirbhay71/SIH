import { Routes, Route, Link, NavLink } from "react-router-dom";
import { HomeIcon, IdCardIcon, ChainIcon, ShieldIcon } from "./components/Icons.jsx";
import Landing from "./pages/Landing.jsx";
import Setup from "./pages/Setup.jsx";
import Capture from "./pages/Capture.jsx";
import Pipeline from "./pages/Pipeline.jsx";
import FaceCapture from "./pages/FaceCapture.jsx";
import Result from "./pages/Result.jsx";
import Audit from "./pages/Audit.jsx";
import AdminWatchlist from "./pages/AdminWatchlist.jsx";

export default function App() {
  return (
    <div className="app-shell">
      <aside className="side-rail">
        <span className="rail-logo" aria-hidden="true">🛂</span>
        <NavLink to="/" end title="Home"><HomeIcon /></NavLink>
        <NavLink to="/verify/setup" title="Start Verification"><IdCardIcon /></NavLink>
        <NavLink to="/audit" title="Audit Trail"><ChainIcon /></NavLink>
        <NavLink to="/admin/watchlist" title="Admin"><ShieldIcon /></NavLink>
      </aside>
      <div className="app-main">
        <header className="topbar">
          <Link to="/" className="brand" style={{ textDecoration: "none" }}>
            <span className="brand-text">
              Border Screening System
              <small>SSB · AI-Based Fake Identity &amp; Document Screening (PS 26188)</small>
            </span>
          </Link>
          <nav>
            <Link to="/audit">Audit Trail</Link>
            <Link to="/admin/watchlist">Admin</Link>
            <Link to="/verify/setup" className="btn-gradient">Start Verification →</Link>
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
