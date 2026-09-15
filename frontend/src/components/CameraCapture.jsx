import { useEffect, useRef, useState } from "react";

export default function CameraCapture({ onCapture, facingMode = "environment", label = "Capture" }) {
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const [active, setActive] = useState(false);
  const [error, setError] = useState(null);

  async function start() {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode } });
      streamRef.current = stream;
      if (videoRef.current) videoRef.current.srcObject = stream;
      setActive(true);
    } catch (e) {
      setError("Camera unavailable: " + e.message);
    }
  }

  function stop() {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    setActive(false);
  }

  useEffect(() => () => stop(), []);

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

  return (
    <div>
      {!active && (
        <button className="btn btn-outline btn-block" onClick={start}>
          📷 Open Camera
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
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
