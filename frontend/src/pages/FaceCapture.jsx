import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import CameraCapture from "../components/CameraCapture.jsx";
import VerifyShell from "../components/VerifyShell.jsx";
import { ThinkingLoader } from "../components/Loader.jsx";
import { uploadFace } from "../lib/api";

export default function FaceCapture() {
  const { sessionId } = useParams();
  const navigate = useNavigate();
  const { t } = useTranslation();
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

  let statusHeadline = t("face.positionFace");
  if (uploading) statusHeadline = t("face.matching");
  else if (error) statusHeadline = t("face.failed");
  else if (preview) statusHeadline = t("face.captured");

  return (
    <VerifyShell current="face" status={statusHeadline}>
      <div className="verify-center">
        <h2>{t("face.title")}</h2>
        <p className="subtitle">{statusHeadline}</p>

        {uploading ? (
          <ThinkingLoader label={t("face.verifyingMatch")} />
        ) : (
          <>
            {!preview && (
              <CameraCapture
                onCapture={(f, dataUrl) => {
                  setFile(f);
                  setPreview(dataUrl);
                }}
                facingMode="user"
                label={t("face.captureFaceLabel")}
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
                {t("face.orUpload")}
              </label>
            )}

            {preview && (
              <div className="verify-camera">
                <div className="verify-viewport is-captured">
                  <img src={preview} alt="face preview" />
                  <span className="corner tl" />
                  <span className="corner tr" />
                  <span className="corner bl" />
                  <span className="corner br" />
                  <div className="verify-viewport-status">
                    <span className="verify-status-dot ok" />
                    {t("face.faceCapturedBadge")}
                  </div>
                </div>
                <p className="verify-viewport-hint">{t("face.readyForVerification")}</p>
                <div style={{ textAlign: "center" }}>
                  <button className="btn btn-outline" style={{ marginTop: 10 }} onClick={() => { setPreview(null); setFile(null); }}>
                    {t("capture.retake")}
                  </button>
                </div>
              </div>
            )}

            <div className="toggle-row" style={{ justifyContent: "center" }}>
              <input type="checkbox" id="mismatch" checked={simulateMismatch} onChange={(e) => setSimulateMismatch(e.target.checked)} />
              <label htmlFor="mismatch" style={{ margin: 0 }}>{t("face.simulateMismatch")}</label>
            </div>

            {error && <p className="verify-error" style={{ textAlign: "center" }}>{error}</p>}

            <div className="action-row" style={{ justifyContent: "center" }}>
              <button className="btn btn-primary verify-cta" disabled={!file || uploading} onClick={submit}>
                {t("face.verifyFace")}
              </button>
            </div>
          </>
        )}
      </div>
    </VerifyShell>
  );
}
