import { useNavigate } from "react-router-dom";

const FEATURES = [
  { icon: "🔍", title: "Real OCR Extraction", desc: "MRZ + field-level OCR pulls name, document number, nationality, DOB and expiry in seconds." },
  { icon: "🛡️", title: "Tampering Detection", desc: "Photo splices, text edits, stamp forgery and metadata analysis — the PS's core AI innovation." },
  { icon: "🧑‍🤝‍🧑", title: "Face Verification", desc: "Live liveness check plus document-vs-holder face match, with watchlist screening." },
  { icon: "⛓️", title: "Tamper-Evident Audit", desc: "Every officer decision is hash-chained — alter one record and the whole chain visibly breaks." },
];

export default function Landing() {
  const navigate = useNavigate();
  return (
    <div className="landing-page">
      <div className="landing-hero">
        <div>
          <div className="eyebrow">Digital Border Screening</div>
          <h1>AI-Based Fake Identity &amp; Document Screening</h1>
          <p className="subtitle">
            SSB Border Checkpoint Demo — India-Nepal / India-Bhutan crossings. Verifies documents in
            seconds instead of minutes, with an explainable risk score and a tamper-evident audit trail.
          </p>
          <button className="btn btn-gradient" style={{ fontSize: 15, padding: "12px 26px" }} onClick={() => navigate("/verify/setup")}>
            Verify Document →
          </button>
        </div>

        <div className="hero-card">
          <div className="hero-card-icon">🪪</div>
          <h3>Live Risk Assessment</h3>
          <p>
            OCR, validation, tampering detection, and face verification run in a single pipeline,
            producing a composite, explainable risk score an officer can act on immediately.
          </p>
          <div className="hero-stats">
            <div>
              <div className="stat-num">4</div>
              <div className="stat-label">AI Modules</div>
            </div>
            <div>
              <div className="stat-num">&lt;10s</div>
              <div className="stat-label">Per Document</div>
            </div>
            <div>
              <div className="stat-num">100%</div>
              <div className="stat-label">Audit Trail</div>
            </div>
          </div>
        </div>
      </div>

      <div className="promo-banner">
        <span>🇮🇳 Now supporting India-Nepal crossing document-acceptance rules for Indian citizens</span>
        <button className="btn btn-outline" style={{ padding: "6px 14px", fontSize: 13 }} onClick={() => navigate("/verify/setup")}>
          Try It
        </button>
      </div>

      <div className="feature-grid">
        {FEATURES.map((f) => (
          <div className="feature" key={f.title}>
            <div className="feature-icon">{f.icon}</div>
            <h4>{f.title}</h4>
            <p>{f.desc}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
