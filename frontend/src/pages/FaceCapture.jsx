import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import CameraCapture from "../components/CameraCapture.jsx";
import FlowProgress from "../components/FlowProgress.jsx";
import { ThinkingLoader } from "../components/Loader.jsx";
import { uploadFace } from "../lib/api";

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

  return (
    <div style={{ maxWidth: 900, margin: "0 auto" }}>
      <FlowProgress current="face" />
      <div className="face-id-layout">
        <div className="card face-id-side">
          <div className="face-id-brand">🛂 Border Screening</div>
          <div className="face-id-steps">
            <div className="face-id-step done">
              <span className="face-id-step-icon">✓</span>
              <div>
                <strong>Document Scan</strong>
                <p>Verifies your travel document via OCR + tampering checks.</p>
              </div>
            </div>
            <div className="face-id-step active">
              <span className="face-id-step-icon">🧑</span>
              <div>
                <strong>Face ID Verification</strong>
                <p>Verifies your identity by matching your live face to the document photo.</p>
              </div>
            </div>
            <div className="face-id-step">
              <span className="face-id-step-icon">📊</span>
              <div>
                <strong>Risk Assessment</strong>
                <p>Combines every module's output into one explainable risk score.</p>
              </div>
            </div>
          </div>
          <div className="face-id-note">
            <strong>Your data is protected.</strong>
            <p>Live capture is only used for this verification session and matched against your uploaded document — never stored for any other purpose.</p>
          </div>
        </div>

        <div className="card face-id-main">
          <h2>Face ID Verification</h2>
          <p className="subtitle">{uploading ? "Hold still — verifying your face." : "Position your face in the frame and capture."}</p>

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
                <div>
                  <div className="face-scan-wrap">
                    <div className="face-scan-circle">
                      <img src={preview} alt="face preview" />
                    </div>
                    <span className="corner tl" />
                    <span className="corner tr" />
                    <span className="corner bl" />
                    <span className="corner br" />
                  </div>
                  <div className="face-scan-label">Captured ✓</div>
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

              {error && <p style={{ color: "var(--red)", textAlign: "center" }}>{error}</p>}

              <div className="action-row" style={{ justifyContent: "center" }}>
                <button className="btn btn-primary" style={{ minWidth: 220 }} disabled={!file || uploading} onClick={submit}>
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
