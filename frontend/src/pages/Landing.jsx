import { useNavigate } from "react-router-dom";

export default function Landing() {
  const navigate = useNavigate();
  return (
    <div className="landing-hero">
      <h1>AI-Based Fake Identity &amp; Document Screening</h1>
      <p className="subtitle">
        SSB Border Checkpoint Demo — India-Nepal / India-Bhutan crossings. Verifies documents in
        seconds instead of minutes, with an explainable risk score and a tamper-evident audit trail.
      </p>
      <button className="btn btn-primary" onClick={() => navigate("/verify/setup")}>
        Verify Document →
      </button>
    </div>
  );
}
