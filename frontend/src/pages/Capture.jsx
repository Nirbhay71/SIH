import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import CameraCapture from "../components/CameraCapture.jsx";
import { uploadDocument } from "../lib/api";

async function fetchAsFile(url, filename) {
  const res = await fetch(url);
  const blob = await res.blob();
  return new File([blob], filename, { type: blob.type });
}

export default function Capture() {
  const { sessionId } = useParams();
  const navigate = useNavigate();
  const [preview, setPreview] = useState(null);
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  const [mode, setMode] = useState("upload"); // upload | camera

  function onFileChosen(f) {
    setFile(f);
    setPreview(URL.createObjectURL(f));
  }

  async function useSample(name, displayLabel) {
    const f = await fetchAsFile(`/samples/${name}`, name);
    setFile(f);
    setPreview(URL.createObjectURL(f));
  }

  async function submit() {
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      await uploadDocument(sessionId, file);
      navigate(`/verify/pipeline/${sessionId}`);
    } catch (e) {
      setError(e.message);
      setUploading(false);
    }
  }

  return (
    <div className="card" style={{ maxWidth: 560, margin: "0 auto" }}>
      <h2>Document Capture</h2>
      <p className="subtitle">Upload a document image, or use your camera.</p>

      <div className="action-row" style={{ marginBottom: 16 }}>
        <button className={`btn ${mode === "upload" ? "btn-primary" : "btn-outline"}`} onClick={() => setMode("upload")}>
          Upload File
        </button>
        <button className={`btn ${mode === "camera" ? "btn-primary" : "btn-outline"}`} onClick={() => setMode("camera")}>
          Use Camera
        </button>
      </div>

      {mode === "upload" && !preview && (
        <label className="dropzone">
          <input
            type="file"
            accept="image/*,.pdf"
            style={{ display: "none" }}
            onChange={(e) => e.target.files[0] && onFileChosen(e.target.files[0])}
          />
          Click to choose a document image
        </label>
      )}

      {mode === "camera" && !preview && (
        <CameraCapture onCapture={(f, dataUrl) => { setFile(f); setPreview(dataUrl); }} label="Capture Document" />
      )}

      {preview && (
        <div>
          <img className="preview" src={preview} alt="document preview" />
          <button className="btn btn-outline" style={{ marginTop: 10 }} onClick={() => { setPreview(null); setFile(null); }}>
            Retake
          </button>
        </div>
      )}

      <div className="sample-buttons">
        <span className="mini" style={{ width: "100%" }}>Demo shortcuts:</span>
        <button className="btn btn-outline" onClick={() => useSample("sample_genuine.png")}>
          Use Genuine Sample
        </button>
        <button className="btn btn-outline" onClick={() => useSample("sample_tampered_document.png")}>
          Use Tampered Sample
        </button>
      </div>

      {error && <p style={{ color: "var(--red)" }}>{error}</p>}

      <div className="action-row">
        <button className="btn btn-primary btn-block" disabled={!file || uploading} onClick={submit}>
          {uploading ? "Uploading..." : "Run Verification →"}
        </button>
      </div>
    </div>
  );
}
