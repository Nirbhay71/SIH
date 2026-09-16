import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import CameraCapture from "../components/CameraCapture.jsx";
import { ThinkingLoader } from "../components/Loader.jsx";
import { uploadFace } from "../lib/api";

const STAGES = [
  { key: "setup", label: "Setup", desc: "Session initialized" },
  { key: "capture", label: "Document", desc: "Travel document scanned & verified" },
  { key: "pipeline", label: "Analysis", desc: "OCR, tamper & data checks" },
  { key: "face", label: "Face", desc: "Matching your live face to the document photo" },
  { key: "result", label: "Result", desc: "Final explainable risk decision" },
];
const CURRENT_STAGE = "face";

export default function FaceCapture() {
  const { sessionId } = useParams();
  const navigate = useNavigate();
  const [preview, setPreview] = useState(null);
  const [file, setFile] = useState(null);
  const [simulateMismatch, setSimulateMismatch] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);

  async function submit() {
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      await uploadFace(sessionId, file, simulateMismatch);
      navigate(`/verify/pipeline/${sessionId}?after=face`);
    } catch (e) {
      setError(e.message);
      setUploading(false);
    }
  }

  const currentIndex = STAGES.findIndex((s) => s.key === CURRENT_STAGE);
  const activeStage = STAGES[currentIndex];

  let statusHeadline = "Position your face in the frame and capture";
  if (uploading) statusHeadline = "Matching your live face with the document identity…";
  else if (error) statusHeadline = "Face verification failed — please try again";
  else if (preview) statusHeadline = "Face captured — ready for verification";

  return (
    <div className="faceid-screen">
      <div className="faceid-left">
        <div className="faceid-brand">
          <span className="faceid-brand-mark">🛂</span>
          <div>
            <strong>Border Screening System</strong>
            <span>AI-powered identity &amp; document verification</span>
          </div>
        </div>

        <h1 className="faceid-left-title">Identity Verification</h1>
        <p className="faceid-left-sub">
          Securely verify your identity using document and facial verification.
        </p>

        <div className="faceid-timeline">
          {STAGES.map((s, i) => {
            const state = i < currentIndex ? "done" : i === currentIndex ? "active" : "upcoming";
            return (
              <div key={s.key} className={`faceid-tl-item faceid-tl-${state}`}>
                <div className="faceid-tl-rail">
                  <span className="faceid-tl-node">
                    {state === "done" ? "✓" : state === "active" ? <span className="faceid-tl-pulse" /> : ""}
                  </span>
                  {i < STAGES.length - 1 && <span className="faceid-tl-line" />}
                </div>
                <div className="faceid-tl-body">
                  <strong>{s.label}</strong>
                  {state === "active" && <p>{s.desc}</p>}
                </div>
              </div>
            );
          })}
        </div>

        <div className="faceid-current-card">
          <span className="faceid-current-label">Currently</span>
          <strong>{activeStage.label} Verification</strong>
          <p>{statusHeadline}</p>
        </div>

        <div className="faceid-note">
          <strong>Your data is protected.</strong>
          <p>Live capture is only used for this verification session and matched against your uploaded document — never stored for any other purpose.</p>
        </div>
      </div>

      <div className="faceid-right">
        <div className="faceid-right-inner">
          <h2>Face ID Verification</h2>
          <p className="subtitle">{statusHeadline}</p>

          {uploading ? (
            <ThinkingLoader label="Verifying face match" />
          ) : (
            <>
              {!preview && (
                <CameraCapture
                  onCapture={(f, dataUrl) => {
                    setFile(f);
                    setPreview(dataUrl);
                  }}
                  facingMode="user"
                  label="Capture Face"
                  circleFrame
                />
              )}

              {!preview && (
                <label className="dropzone" style={{ marginTop: 16 }}>
                  <input
                    type="file"
                    accept="image/*"
                    style={{ display: "none" }}
                    onChange={(e) => {
                      const f = e.target.files[0];
                      if (f) {
                        setFile(f);
                        setPreview(URL.createObjectURL(f));
                      }
                    }}
                  />
                  or click to upload a face photo
                </label>
              )}

              {preview && (
                <div className="faceid-camera">
                  <div className="faceid-viewport is-captured">
                    <img src={preview} alt="face preview" />
                    <span className="corner tl" />
                    <span className="corner tr" />
                    <span className="corner bl" />
                    <span className="corner br" />
                    <div className="faceid-viewport-status">
                      <span className="faceid-status-dot ok" />
                      Face captured
                    </div>
                  </div>
                  <p className="faceid-viewport-hint">Ready for verification</p>
                  <div style={{ textAlign: "center" }}>
                    <button className="btn btn-outline" style={{ marginTop: 10 }} onClick={() => { setPreview(null); setFile(null); }}>
                      Retake
                    </button>
                  </div>
                </div>
              )}

              <div className="toggle-row" style={{ justifyContent: "center" }}>
                <input type="checkbox" id="mismatch" checked={simulateMismatch} onChange={(e) => setSimulateMismatch(e.target.checked)} />
                <label htmlFor="mismatch" style={{ margin: 0 }}>Simulate a face mismatch (demo)</label>
              </div>

              {error && <p className="faceid-error" style={{ textAlign: "center" }}>{error}</p>}

              <div className="action-row" style={{ justifyContent: "center" }}>
                <button className="btn btn-primary faceid-verify-btn" disabled={!file || uploading} onClick={submit}>
                  Verify Face →
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
