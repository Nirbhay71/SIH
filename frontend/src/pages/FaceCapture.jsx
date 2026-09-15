import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import CameraCapture from "../components/CameraCapture.jsx";
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
    <div className="card" style={{ maxWidth: 480, margin: "0 auto" }}>
      <h2>Live Face Capture</h2>
      <p className="subtitle">Document scan complete. Now capture the traveler's live face for verification.</p>

      {!preview && (
        <CameraCapture
          onCapture={(f, dataUrl) => {
            setFile(f);
            setPreview(dataUrl);
          }}
          facingMode="user"
          label="Capture Face"
        />
      )}

      {!preview && (
        <label className="dropzone" style={{ marginTop: 12 }}>
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
          <img className="preview" src={preview} alt="face preview" />
          <button className="btn btn-outline" style={{ marginTop: 10 }} onClick={() => { setPreview(null); setFile(null); }}>
            Retake
          </button>
        </div>
      )}

      <div className="toggle-row">
        <input type="checkbox" id="mismatch" checked={simulateMismatch} onChange={(e) => setSimulateMismatch(e.target.checked)} />
        <label htmlFor="mismatch" style={{ margin: 0 }}>Simulate a face mismatch (demo)</label>
      </div>

      {error && <p style={{ color: "var(--red)" }}>{error}</p>}

      <div className="action-row">
        <button className="btn btn-primary btn-block" disabled={!file || uploading} onClick={submit}>
          {uploading ? "Verifying..." : "Verify Face →"}
        </button>
      </div>
    </div>
  );
}
