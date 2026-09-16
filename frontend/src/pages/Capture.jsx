import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import CameraCapture from "../components/CameraCapture.jsx";
import VerifyShell from "../components/VerifyShell.jsx";
import { Spinner } from "../components/Loader.jsx";
import { uploadDocument } from "../lib/api";

async function fetchAsFile(url, filename) {
  const res = await fetch(url);
  const blob = await res.blob();
  return new File([blob], filename, { type: blob.type });
}

// India-Nepal crossing document types (see backend/app/acceptance_policy.py
// for which of these are actually accepted proof of citizenship, and for
// which age brackets). Listed here so the traveler/officer tells the
// system what they're presenting up front, rather than the system trying
// to guess Voter ID vs. Aadhaar vs. PAN from OCR alone — the pipeline has
// no real classifier for that distinction.
const DOCUMENT_TYPES = [
  { value: "indian_passport", label: "Indian Passport" },
  { value: "foreign_passport", label: "Foreign Passport" },
  { value: "voter_id", label: "Voter ID Card (EPIC)" },
  { value: "emergency_certificate", label: "Emergency Certificate (Embassy)" },
  { value: "identity_certificate", label: "Identity Certificate (Embassy)" },
  { value: "school_identity_certificate", label: "School Identity Certificate (ages 15-18)" },
  { value: "aadhaar", label: "Aadhaar Card" },
  { value: "pan_card", label: "PAN Card" },
  { value: "driving_license", label: "Driving Licence" },
  { value: "ration_card", label: "Ration Card" },
  { value: "cghs_card", label: "CGHS Card" },
  { value: "indian_visa_sticker", label: "Visa (Sticker)" },
  { value: "indian_evisa", label: "e-Visa" },
  { value: "oci_card", label: "OCI Card" },
  { value: "border_permit_ilp", label: "Border Permit (ILP)" },
];

// Mirrors ml-service's preprocessing.min_dimension_px (config/thresholds.yaml)
// — checking it here too means the traveler/officer sees "this image is too
// small" immediately on selection, instead of only after the full pipeline
// runs and rejects it. The browser <img> tag stretches any image to fill
// its container, so a tiny 282x378px screenshot can look just as large on
// screen as a proper 1200x1600px photo — this makes the real pixel size
// visible so that visual illusion doesn't mask a genuinely low-res upload.
const MIN_DOCUMENT_DIMENSION_PX = 400;

export default function Capture() {
  const { sessionId } = useParams();
  const navigate = useNavigate();
  const [preview, setPreview] = useState(null);
  const [file, setFile] = useState(null);
  const [imgDims, setImgDims] = useState(null); // { width, height } | null (null = unknown, e.g. PDF)
  const [docType, setDocType] = useState("indian_passport");
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  const [mode, setMode] = useState("upload"); // upload | camera
  const [pendingOpen, setPendingOpen] = useState(false);
  const fileInputRef = useRef(null);

  function checkDimensions(previewUrl, filename) {
    if (/\.pdf$/i.test(filename || "")) {
      setImgDims(null); // can't read pixel dimensions of a PDF client-side
      return;
    }
    const img = new Image();
    img.onload = () => setImgDims({ width: img.naturalWidth, height: img.naturalHeight });
    img.onerror = () => setImgDims(null);
    img.src = previewUrl;
  }

  // If mode was "camera" (input not yet mounted) when "Upload File" was
  // clicked, wait for the switch to actually render the <input> before
  // opening the picker — clicking a ref synchronously in the same handler
  // that changes the mode would hit a still-null ref.
  useEffect(() => {
    if (pendingOpen && mode === "upload" && fileInputRef.current) {
      fileInputRef.current.click();
      setPendingOpen(false);
    }
  }, [pendingOpen, mode]);

  function onFileChosen(f) {
    setFile(f);
    const url = URL.createObjectURL(f);
    setPreview(url);
    checkDimensions(url, f.name);
  }

  async function useSample(name, displayLabel) {
    const f = await fetchAsFile(`/samples/${name}`, name);
    setFile(f);
    const url = URL.createObjectURL(f);
    setPreview(url);
    checkDimensions(url, f.name);
  }

  async function submit() {
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      await uploadDocument(sessionId, file, docType);
      navigate(`/verify/pipeline/${sessionId}`);
    } catch (e) {
      setError(e.message);
      setUploading(false);
    }
  }

  const status = uploading ? "Uploading your document…" : preview ? "Document ready — run verification when you're set." : "Upload a document image, or use your camera.";

  return (
    <VerifyShell current="capture" status={status}>
      <h2>Document Capture</h2>
      <p className="subtitle">Upload a document image, or use your camera.</p>

      <label>Document Type</label>
      <select value={docType} onChange={(e) => setDocType(e.target.value)} style={{ marginBottom: 16 }}>
        {DOCUMENT_TYPES.map((t) => (
          <option key={t.value} value={t.value}>{t.label}</option>
        ))}
      </select>

      <div className="action-row" style={{ marginBottom: 16 }}>
        <button
          className={`btn ${mode === "upload" ? "btn-primary" : "btn-outline"}`}
          onClick={() => {
            // Already the active tab by default, so a plain mode-switch is a
            // no-op the user can't see happen — open the file picker
            // directly so the button does what its label says on every click.
            setMode("upload");
            if (!preview) setPendingOpen(true);
          }}
        >
          Upload File
        </button>
        <button className={`btn ${mode === "camera" ? "btn-primary" : "btn-outline"}`} onClick={() => setMode("camera")}>
          Use Camera
        </button>
      </div>

      {mode === "upload" && !preview && (
        <label className="dropzone">
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*,.pdf"
            style={{ display: "none" }}
            onChange={(e) => e.target.files[0] && onFileChosen(e.target.files[0])}
          />
          Click to choose a document image
        </label>
      )}

      {mode === "camera" && !preview && (
        <CameraCapture
          onCapture={(f, dataUrl) => { setFile(f); setPreview(dataUrl); checkDimensions(dataUrl, f.name); }}
          label="Capture Document"
        />
      )}

      {preview && (
        <div>
          <img className="preview" src={preview} alt="document preview" />
          {imgDims && (
            <p className="mini" style={{ marginTop: 6 }}>
              Image size: {imgDims.width}×{imgDims.height}px
              {Math.min(imgDims.width, imgDims.height) < MIN_DOCUMENT_DIMENSION_PX && (
                <span style={{ color: "var(--red)", fontWeight: 700 }}> — too small, will likely be rejected. Use a higher-resolution photo or scan.</span>
              )}
            </p>
          )}
          <button className="btn btn-outline" style={{ marginTop: 10 }} onClick={() => { setPreview(null); setFile(null); setImgDims(null); }}>
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

      {error && <p className="verify-error">{error}</p>}

      <div className="action-row">
        <button className="btn btn-primary btn-block verify-cta" disabled={!file || uploading} onClick={submit}>
          {uploading && <Spinner size={14} inline />}
          {uploading ? "Uploading..." : "Run Verification →"}
        </button>
      </div>
    </VerifyShell>
  );
}
