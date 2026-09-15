import { Routes, Route, Link } from "react-router-dom";
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
      <header className="topbar">
        <Link to="/" className="brand" style={{ textDecoration: "none" }}>
          Border Screening System
          <small>SSB · AI-Based Fake Identity &amp; Document Screening (PS 26188)</small>
        </Link>
        <nav>
          <Link to="/audit">Audit Trail</Link>
          <Link to="/admin/watchlist">Admin</Link>
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
  );
}
