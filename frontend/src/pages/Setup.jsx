import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { startVerification } from "../lib/api";
import VerifyShell from "../components/VerifyShell.jsx";

export default function Setup() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [direction, setDirection] = useState("entering_india");
  const [coords, setCoords] = useState(null);
  const [locStatusKey, setLocStatusKey] = useState("requestingLocation");
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!navigator.geolocation) {
      setLocStatusKey("geoUnsupported");
      setCoords({ latitude: 26.4525, longitude: 87.2718 }); // Nepal border region fallback
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setCoords({ latitude: pos.coords.latitude, longitude: pos.coords.longitude });
        setLocStatusKey("locationCaptured");
      },
      () => {
        setLocStatusKey("geoDenied");
        setCoords({ latitude: 26.4525, longitude: 87.2718 });
      }
    );
  }, []);

  const locStatus = t(`setup.${locStatusKey}`);

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
    <VerifyShell current="setup" status={locStatus}>
      <h2>{t("setup.title")}</h2>
      <p className="subtitle">{t("setup.subtitle")}</p>

      <label>{t("setup.travelDirection")}</label>
      <select value={direction} onChange={(e) => setDirection(e.target.value)}>
        <option value="entering_india">{t("setup.enteringIndia")}</option>
        <option value="entering_nepal">{t("setup.enteringNepal")}</option>
      </select>

      <div className="status-pill">📍 {locStatus}</div>

      {error && <p className="verify-error">{error}</p>}

      <div className="action-row">
        <button className="btn btn-primary btn-block verify-cta" disabled={!coords || starting} onClick={handleContinue}>
          {starting ? t("setup.starting") : t("setup.continue")}
        </button>
      </div>
    </VerifyShell>
  );
}
