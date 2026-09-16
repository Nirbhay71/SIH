import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

export default function CameraCapture({ onCapture, facingMode = "environment", label = "Capture", circleFrame = false }) {
  const { t } = useTranslation();
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const [active, setActive] = useState(false);
  const [error, setError] = useState(null);

  async function start() {
    setError(null);
    if (!navigator.mediaDevices?.getUserMedia) {
      setError("Camera unavailable: this browser (or non-HTTPS/non-localhost context) doesn't support camera access.");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode } });
      streamRef.current = stream;
      setActive(true);
    } catch (e) {
      setError("Camera unavailable: " + e.message);
    }
  }

  function stop() {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    setActive(false);
  }

  useEffect(() => () => stop(), []);

  // The <video> element only mounts once `active` is true, so the stream
  // can't be attached inside start() — videoRef.current is still null at
  // that point (React hasn't re-rendered yet). Attach it here instead,
  // once the element actually exists.
  useEffect(() => {
    if (active && videoRef.current && streamRef.current) {
      videoRef.current.srcObject = streamRef.current;
    }
  }, [active]);

  function capture() {
    const video = videoRef.current;
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext("2d").drawImage(video, 0, 0);
    canvas.toBlob((blob) => {
      const file = new File([blob], `capture_${Date.now()}.png`, { type: "image/png" });
      onCapture(file, canvas.toDataURL("image/png"));
      stop();
    }, "image/png");
  }

  if (circleFrame) {
    return (
      <div className="verify-camera">
        <div className={`verify-viewport ${active ? "is-active" : ""}`}>
          {active ? (
            <video ref={videoRef} autoPlay playsInline />
          ) : (
            <div className="verify-viewport-placeholder">
              <span>🧑</span>
            </div>
          )}
          {active && <span className="scan-line" />}
          <span className="corner tl" />
          <span className="corner tr" />
          <span className="corner bl" />
          <span className="corner br" />
          <div className="verify-viewport-status">
            <span className={`verify-status-dot ${active ? "live" : ""}`} />
            {active ? t("camera.scanningFace") : t("camera.cameraReady")}
          </div>
        </div>

        <p className="verify-viewport-hint">
          {active ? t("camera.alignHold") : t("camera.positionFace")}
        </p>

        {error && <p className="verify-error">{error}</p>}

        <div className="action-row" style={{ justifyContent: "center" }}>
          {!active ? (
            <button className="btn btn-primary btn-block" onClick={start}>
              {t("camera.startFaceScan")}
            </button>
          ) : (
            <>
              <button className="btn btn-primary" onClick={capture}>
                {label}
              </button>
              <button className="btn btn-outline" onClick={stop}>
                {t("camera.cancel")}
              </button>
            </>
          )}
        </div>
      </div>
    );
  }

  return (
    <div>
      {!active && (
        <button className="btn btn-outline btn-block" onClick={start}>
          {t("camera.openCamera")}
        </button>
      )}
      {error && <p style={{ color: "var(--red)" }}>{error}</p>}
      {active && (
        <div>
          <video ref={videoRef} autoPlay playsInline />
          <div className="action-row">
            <button className="btn btn-primary" onClick={capture}>
              {label}
            </button>
            <button className="btn btn-outline" onClick={stop}>
              {t("camera.cancel")}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
