import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { getResult, submitDecision } from "../lib/api";
import FlowProgress from "../components/FlowProgress.jsx";
import { ThinkingLoader, Spinner } from "../components/Loader.jsx";

function riskBadgeClass(level) {
  if (level === "low") return "badge-low";
  if (level === "medium") return "badge-medium";
  return "badge-high";
}

export default function Result() {
  const { sessionId } = useParams();
  const [result, setResult] = useState(null);
  const [showHeatmap, setShowHeatmap] = useState(true);
  const [deciding, setDeciding] = useState(false);
  const [error, setError] = useState(null);

  async function load() {
    try {
      setResult(await getResult(sessionId));
    } catch (e) {
      setError(e.message);
    }
  }

  useEffect(() => {
    load();
  }, [sessionId]);

  async function decide(decision) {
    setDeciding(true);
    try {
      const updated = await submitDecision(sessionId, decision);
      setResult(updated);
    } catch (e) {
      setError(e.message);
    } finally {
      setDeciding(false);
    }
  }

  if (error) return <p style={{ color: "var(--red)" }}>{error}</p>;
  if (!result) return (
    <div>
      <FlowProgress current="result" />
      <div className="card">
        <ThinkingLoader label="Compiling verification result" />
      </div>
    </div>
  );

  const fields = result.ocr_raw_json?.fields || {};
  const validation = result.validation_result_json || { passed: true, failures: [] };

  return (
    <div>
      <FlowProgress current="result" />
      {result.analysis_source === "mock" && (
        <div className="card" style={{ background: "#fffbeb", border: "2px solid var(--yellow)" }}>
          <h2 style={{ color: "var(--yellow)" }}>⚠️ Demo Data — ML Service Unavailable</h2>
          <p>
            The real AI analysis service (OCR, face verification, tampering detection) could not be reached when this
            document was processed, so the system fell back to <strong>randomly generated placeholder data</strong> for
            demo continuity. None of the fields, scores, or the risk assessment below reflect the actual uploaded
            document — please re-run verification once the ML service is back online.
          </p>
          {result.ml_fallback_reason && (
            <p className="mini" style={{ marginTop: 10 }}>Technical reason: {result.ml_fallback_reason}</p>
          )}
        </div>
      )}
      {result.document_accepted === false && (
        <div className="card" style={{ background: "#fef2f2", border: "2px solid var(--red)" }}>
          <h2 style={{ color: "var(--red)" }}>🚫 Document Not Accepted</h2>
          <p>{result.document_acceptance_reason}</p>
        </div>
      )}

      <div className="card">
        <h2>
          Verification Result{" "}
          <span className={`badge ${riskBadgeClass(result.risk_level)}`} style={{ marginLeft: 10 }}>
            {result.risk_level?.toUpperCase()} RISK
          </span>
        </h2>

        <div className="result-grid">
          <div>
            <h2 style={{ fontSize: 15 }}>Document Image</h2>
            <div className="image-wrap">
              <img src={showHeatmap && result.tampering_heatmap_path ? result.tampering_heatmap_path : result.document_image_url} alt="document" />
            </div>
            {result.tampering_heatmap_path && (
              <div className="toggle-row">
                <input type="checkbox" id="heatmap" checked={showHeatmap} onChange={(e) => setShowHeatmap(e.target.checked)} />
                <label htmlFor="heatmap" style={{ margin: 0 }}>Show tampering heatmap overlay</label>
              </div>
            )}
          </div>

          <div>
            <h2 style={{ fontSize: 15 }}>Extracted Fields</h2>
            {(result.ocr_raw_json?.ml_detail?.quality_flags || []).length > 0 && (
              <p className="mini" style={{ color: "var(--yellow)", marginTop: -8, marginBottom: 10 }}>
                ⚠️ Image quality notes: {result.ocr_raw_json.ml_detail.quality_flags.join(", ")} — extraction was still
                attempted, but results below may be less reliable than a clean, well-lit photo.
              </p>
            )}
            <table className="field-table">
              <tbody>
                {Object.entries(fields).map(([key, val]) => (
                  <tr key={key}>
                    <td>{key.replace(/_/g, " ")}</td>
                    <td>{typeof val === "object" ? val.value : String(val)}</td>
                    <td className="mini">{typeof val === "object" ? `${Math.round(val.confidence * 100)}%` : ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>

            <h2 style={{ fontSize: 15, marginTop: 16 }}>Validation</h2>
            <p>{validation.passed ? "✅ All checks passed" : `❌ ${validation.failure_count} check(s) failed`}</p>
            {validation.failures?.map((f, i) => (
              <p key={i} className="mini">• {f.reason}</p>
            ))}

            <h2 style={{ fontSize: 15, marginTop: 16 }}>Face Verification</h2>
            <p>Match: {result.face_match_score != null ? `${(result.face_match_score * 100).toFixed(1)}%` : "—"}</p>
            <p>Liveness: {result.liveness_passed ? "Passed" : "Failed"}</p>
            <p>
              Watchlist:{" "}
              {result.watchlist_match ? (
                <strong style={{ color: "var(--red)" }}>⚠️ Match — {result.watchlist_match_ref}</strong>
              ) : (
                "No match"
              )}
            </p>
          </div>
        </div>
      </div>

      <div className="card">
        <h2>Risk Score</h2>
        <div className="risk-gauge">
          <div className="score" style={{ color: `var(--${result.risk_level === "low" ? "green" : result.risk_level === "medium" ? "yellow" : "red"})` }}>
            {result.risk_score}
          </div>
          <div className="mini">/ 100 — {result.risk_level?.toUpperCase()}</div>
        </div>
        <ul className="breakdown-list">
          {(result.risk_breakdown_json || []).map((b, i) => (
            <li key={i}>
              <span>{b.factor} <span className="mini">— {b.reason}</span></span>
              <strong>+{b.points}</strong>
            </li>
          ))}
          {(!result.risk_breakdown_json || result.risk_breakdown_json.length === 0) && (
            <li><span className="mini">No risk factors triggered.</span></li>
          )}
        </ul>
      </div>

      <div className="card">
        <h2>Travel History</h2>
        {result.duplicate_of_record_id ? (
          <>
            <p>⚠️ Duplicate scan found for this traveler within the last 2 hours.</p>
            <p>Travel direction check: <strong>{result.travel_direction_flag}</strong></p>
            {result.impossible_travel_detail_json && (
              <p className="mini">
                Distance: {result.impossible_travel_detail_json.distance_km} km · Time elapsed:{" "}
                {result.impossible_travel_detail_json.time_elapsed_minutes} min · Required speed:{" "}
                {result.impossible_travel_detail_json.required_speed_kmh} km/h
                {result.impossible_travel_flag ? " — ⚠️ EXCEEDS PLAUSIBLE TRAVEL SPEED" : ""}
              </p>
            )}
          </>
        ) : (
          <p>No prior record found — first scan for this traveler.</p>
        )}
      </div>

      <div className="card">
        <h2>Officer Decision</h2>
        {result.officer_decision ? (
          <p>
            Decision recorded: <strong>{result.officer_decision.toUpperCase()}</strong>{" "}
            <span className="mini">at {result.decided_at}</span>
          </p>
        ) : (
          <div className="action-row">
            <button className="btn btn-green" disabled={deciding} onClick={() => decide("approved")}>
              {deciding && <Spinner size={14} inline />}Approve
            </button>
            <button className="btn btn-red" disabled={deciding} onClick={() => decide("rejected")}>
              {deciding && <Spinner size={14} inline />}Reject
            </button>
            <button className="btn btn-yellow" disabled={deciding} onClick={() => decide("escalated")}>
              {deciding && <Spinner size={14} inline />}Escalate
            </button>
          </div>
        )}
        {result.record_hash && <p className="mini">Audit hash: {result.record_hash}</p>}
      </div>
    </div>
  );
}
