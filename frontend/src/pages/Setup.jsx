import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { startVerification } from "../lib/api";
import FlowProgress from "../components/FlowProgress.jsx";

export default function Setup() {
  const navigate = useNavigate();
  const [direction, setDirection] = useState("entering_india");
  const [coords, setCoords] = useState(null);
  const [locStatus, setLocStatus] = useState("Requesting location...");
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!navigator.geolocation) {
      setLocStatus("Geolocation not supported — using fallback coordinates.");
      setCoords({ latitude: 26.4525, longitude: 87.2718 }); // Nepal border region fallback
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setCoords({ latitude: pos.coords.latitude, longitude: pos.coords.longitude });
        setLocStatus("Location captured ✓");
      },
      () => {
        setLocStatus("Location permission denied — using fallback coordinates.");
        setCoords({ latitude: 26.4525, longitude: 87.2718 });
      }
    );
  }, []);

  async function handleContinue() {
    setStarting(true);
    setError(null);
    try {
      const { session_id } = await startVerification({
        travel_direction: direction,
        latitude: coords?.latitude,
        longitude: coords?.longitude,
      });
      navigate(`/verify/capture/${session_id}`);
    } catch (e) {
      setError(e.message);
      setStarting(false);
    }
  }

  return (
    <div style={{ maxWidth: 480, margin: "0 auto" }}>
      <FlowProgress current="setup" />
      <div className="card">
        <h2>Checkpoint Setup</h2>

        <label>Travel Direction</label>
        <select value={direction} onChange={(e) => setDirection(e.target.value)}>
          <option value="entering_india">Entering India</option>
          <option value="entering_nepal">Entering Nepal</option>
        </select>

        <div className="status-pill">📍 {locStatus}</div>

        {error && <p style={{ color: "var(--red)" }}>{error}</p>}

        <div className="action-row">
          <button className="btn btn-primary btn-block" disabled={!coords || starting} onClick={handleContinue}>
            {starting ? "Starting..." : "Continue to Document Capture"}
          </button>
        </div>
      </div>
    </div>
  );
}
