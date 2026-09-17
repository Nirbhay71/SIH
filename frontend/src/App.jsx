import { Routes, Route } from "react-router-dom";
import Navbar from "./components/Navbar.jsx";
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
      <Navbar />
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
