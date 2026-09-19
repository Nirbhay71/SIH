import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { addFamilyMember, getFamily, getResult, submitDecision } from "../lib/api";
import VerifyShell from "../components/VerifyShell.jsx";
import { ThinkingLoader, Spinner } from "../components/Loader.jsx";

const RELATIONSHIPS = [
  ["spouse", "Spouse"], ["child", "Child"], ["parent", "Parent"], ["sibling", "Sibling"], ["other_relative", "Other relative"],
];

/* India-Nepal "families traveling together": one adult with an approved
   document can cover family members who carry lesser identity proof, if the
   relationship is declared and its proof presented. The officer attests the
   proof here; the server issues the group id, never the browser. */
function FamilyPanel({ sessionId, result }) {
  const navigate = useNavigate();
  const [family, setFamily] = useState({ group_id: null, members: [] });
  const [open, setOpen] = useState(false);
  const [relationship, setRelationship] = useState("child");
  const [proof, setProof] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);

  useEffect(() => {
    getFamily(sessionId).then(setFamily).catch(() => {});
  }, [sessionId, result.officer_decision]);

  async function start() {
    setBusy(true);
    setErr(null);
    try {
      const { session_id } = await addFamilyMember(sessionId, { relationship, relationship_proof_presented: proof });
      navigate(`/verify/capture/${session_id}`);
    } catch (e) {
      setErr(e.message);
      setBusy(false);
    }
  }

  return (
    <div className="card">
      <h2>Family / group travel</h2>
      {family.members.length > 0 && (
        <ul className="family-list">
          {family.members.map((m) => (
            <li key={m.session_id} className={m.is_current ? "is-current" : ""}>
              <span>
                <strong>{m.name || "Unnamed traveller"}</strong>{" "}
                <span className="mini">
                  {m.relationship ? m.relationship.replace("_", " ") : "group anchor"}
                  {m.doc_type ? ` · ${m.doc_type.replace(/_/g, " ")}` : ""}
                </span>
              </span>
              {m.is_current ? <span className="mini">this record</span> : <Link to={`/verify/result/${m.session_id}`}>view</Link>}
            </li>
          ))}
        </ul>
      )}
      {result.family_relationship && (
        <p className="mini">
          This traveller was added as a <strong>{result.family_relationship.replace("_", " ")}</strong> of the group's anchor.
        </p>
      )}
      {!open ? (
        <button className="btn btn-outline" onClick={() => setOpen(true)}>+ Add a family member to this group</button>
      ) : (
        <div className="family-form">
          <label>Relationship to the traveller above</label>
          <select value={relationship} onChange={(e) => setRelationship(e.target.value)}>
            {RELATIONSHIPS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
          <div className="toggle-row">
            <input type="checkbox" id="rel-proof" checked={proof} onChange={(e) => setProof(e.target.checked)} />
            <label htmlFor="rel-proof" style={{ margin: 0 }}>I have seen proof of this family relationship</label>
          </div>
          <p className="mini">
            The family provision only applies if the group's anchor carries an approved document (passport, original Voter ID,
            or embassy certificate) and this member has a recognised photo ID.
          </p>
          {err && <p className="verify-error">{err}</p>}
          <div className="action-row">
            <button className="btn btn-primary" disabled={busy} onClick={start}>{busy ? "Starting…" : "Continue to document capture"}</button>
            <button className="btn btn-outline" onClick={() => setOpen(false)}>Cancel</button>
          </div>
        </div>
      )}
    </div>
  );
}

/* The ML fusion model's own verdict, shown beside (never instead of) the
   authoritative weighted score. Two independently built scorers agreeing is
   reassurance; disagreeing by a full band is exactly the case an officer
   should look at manually, so it is called out rather than left to be
   noticed. */
function ModelCrosscheck({ data }) {
  if (!data) return null;
  const factors = (data.top_factors || []).slice(0, 4);
  const disagree = data.agrees_with_displayed_score === false;
  return (
    <div className={`crosscheck ${disagree ? "is-disagree" : ""} ${data.informational_only ? "is-informational" : ""}`}>
      <div className="crosscheck-head">
        <strong>Independent model cross-check</strong>
        <span className={`badge ${data.tier === "LOW" ? "badge-low" : data.tier === "MEDIUM" ? "badge-medium" : "badge-high"}`}>
          {data.tier}
        </span>
      </div>
      <p className="mini">
        A separately trained gradient-boosted model scored this case {data.score}/100
        {data.probability != null ? ` (p=${Number(data.probability).toFixed(2)})` : ""}
        {data.gate_triggered ? `, hard gate: ${data.gate_triggered}` : ""}.{" "}
        {data.informational_only
          ? data.note
          : disagree
            ? "It disagrees materially with the score above — review this case manually."
            : "It is consistent with the score above."}
      </p>
      {factors.length > 0 && (
        <ul className="crosscheck-factors">
          {factors.map((f, i) => (
            <li key={i}>
              <span>{f.display_name}</span>
              <span className="mini">{f.contribution >= 0 ? "+" : ""}{Number(f.contribution).toFixed(2)}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function riskBadgeClass(level) {
  if (level === "low") return "badge-low";
  if (level === "medium") return "badge-medium";
  return "badge-high";
}

/* Shows how the score was actually arrived at, rather than just asserting a
   number: every weighted factor (including the ones that contributed zero,
   so the officer can see what was checked and cleared), its weight, how
   severely it fired, and the running total. A hard gate renders differently
   because it isn't part of the weighted sum at all — it overrides it. */
function RiskCalculation({ breakdown, score, t }) {
  const rows = breakdown || [];
  if (rows.length === 0) {
    return <p className="mini">{t("result.noRiskFactors")}</p>;
  }

  const hardGate = rows.find((r) => r.hard_gate);
  if (hardGate) {
    return (
      <div className="risk-hardgate">
        <div className="risk-hardgate-title">⛔ {hardGate.factor}</div>
        <p>{hardGate.reason}</p>
        <div className="risk-hardgate-score">Risk forced to {score} / 100</div>
      </div>
    );
  }

  const totalWeight = rows.reduce((sum, r) => sum + (r.weight || 0), 0);
  const totalPoints = rows.reduce((sum, r) => sum + (r.points || 0), 0);

  return (
    <div className="risk-calc">
      <div className="risk-calc-head">
        <span>Factor</span>
        <span>Severity</span>
        <span>Points</span>
      </div>

      {rows.map((r, i) => (
        <div className={`risk-calc-row ${r.points > 0 ? "" : "is-clear"}`} key={i}>
          <div className="risk-calc-factor">
            <strong>{r.factor}</strong>
            <span className="mini">{r.reason}</span>
          </div>
          <div className="risk-calc-bar-cell">
            <div className="risk-calc-bar">
              <span style={{ width: `${Math.round((r.severity || 0) * 100)}%` }} />
            </div>
            <span className="mini">{Math.round((r.severity || 0) * 100)}% of {r.weight}</span>
          </div>
          <div className="risk-calc-points">
            {r.points > 0 ? `+${r.points}` : "0"}
          </div>
        </div>
      ))}

      <div className="risk-calc-total">
        <span>Weighted total (weights sum to {totalWeight})</span>
        <strong>{totalPoints.toFixed(1)} → {score} / 100</strong>
      </div>
    </div>
  );
}

export default function Result() {
  const { sessionId } = useParams();
  const { t } = useTranslation();
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

  if (error) {
    return (
      <VerifyShell current="result" status={t("result.compilingError")}>
        <p className="verify-error">{error}</p>
      </VerifyShell>
    );
  }
  if (!result) {
    return (
      <VerifyShell current="result" status={t("result.compiling")}>
        <ThinkingLoader label={t("result.compiling")} />
      </VerifyShell>
    );
  }

  const fields = result.ocr_raw_json?.fields || {};
  const validation = result.validation_result_json || { passed: true, failures: [] };
  const status = result.officer_decision
    ? t("result.decisionRecorded", { decision: result.officer_decision.toUpperCase() })
    : t("result.awaitingDecision", { level: result.risk_level?.toUpperCase() });

  return (
    <VerifyShell current="result" status={status}>
      {result.face_check_incomplete && (
        <div className="card" style={{ background: "#fffbeb", border: "2px solid var(--yellow)" }}>
          <h2 style={{ color: "var(--yellow)" }}>⚠️ Face verification not completed</h2>
          <p>
            The ML service could not finish the face step, so <strong>no face match, liveness result or watchlist check was
            produced</strong> for this traveller — nothing has been substituted or estimated. Risk is held at MEDIUM or above until
            an officer verifies the face manually. Retry the face capture once the ML service is ready.
          </p>
          {result.face_unavailable_reason && <p className="mini">Technical reason: {result.face_unavailable_reason}</p>}
          <div className="action-row">
            <Link className="btn btn-primary" to={`/verify/face/${sessionId}`}>Retry face verification</Link>
          </div>
        </div>
      )}
      {result.analysis_source === "mock" && (
        <div className="card" style={{ background: "#fffbeb", border: "2px solid var(--yellow)" }}>
          <h2 style={{ color: "var(--yellow)" }}>{t("result.mockTitle")}</h2>
          <p>{t("result.mockBody")}</p>
          {result.ml_fallback_reason && (
            <p className="mini" style={{ marginTop: 10 }}>{t("result.technicalReason")} {result.ml_fallback_reason}</p>
          )}
        </div>
      )}
      {result.document_accepted === false && (
        <div className="card" style={{ background: "#fef2f2", border: "2px solid var(--red)" }}>
          <h2 style={{ color: "var(--red)" }}>{t("result.notAcceptedTitle")}</h2>
          <p>{result.document_acceptance_reason}</p>
        </div>
      )}

      <div className="card">
        <h2>
          {t("result.verificationResult")}{" "}
          <span className={`badge ${riskBadgeClass(result.risk_level)}`} style={{ marginLeft: 10 }}>
            {result.risk_level?.toUpperCase()} {t("result.risk")}
          </span>
        </h2>

        <div className="result-grid">
          <div>
            <h2 style={{ fontSize: 15 }}>{t("result.documentImage")}</h2>
            <div className="image-wrap">
              <img src={showHeatmap && result.tampering_heatmap_path ? result.tampering_heatmap_path : result.document_image_url} alt="document" />
            </div>
            {result.tampering_heatmap_path && (
              <div className="toggle-row">
                <input type="checkbox" id="heatmap" checked={showHeatmap} onChange={(e) => setShowHeatmap(e.target.checked)} />
                <label htmlFor="heatmap" style={{ margin: 0 }}>{t("result.showHeatmap")}</label>
              </div>
            )}
          </div>

          <div>
            <h2 style={{ fontSize: 15 }}>{t("result.extractedFields")}</h2>
            {(result.ocr_raw_json?.ml_detail?.quality_flags || []).length > 0 && (
              <p className="mini" style={{ color: "var(--yellow)", marginTop: -8, marginBottom: 10 }}>
                {t("result.qualityNotes")} {result.ocr_raw_json.ml_detail.quality_flags.join(", ")}{t("result.qualityNotesSuffix")}
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

            <h2 style={{ fontSize: 15, marginTop: 16 }}>{t("result.validation")}</h2>
            <p>{validation.passed ? t("result.validationPassed") : t("result.validationFailed", { count: validation.failure_count })}</p>
            {validation.failures?.map((f, i) => (
              <p key={i} className="mini">• {f.reason}</p>
            ))}

            <h2 style={{ fontSize: 15, marginTop: 16 }}>{t("result.faceVerification")}</h2>
            <p>{t("result.match")}: {result.face_match_score != null ? `${(result.face_match_score * 100).toFixed(1)}%` : "—"}</p>
            <p>{t("result.liveness")}: {result.liveness_passed === true ? t("result.passed") : result.liveness_passed === false ? t("result.failed") : "Not assessed"}</p>
            <p>
              {t("result.watchlist")}:{" "}
              {result.watchlist_checked === false ? (
                <span className="mini">Not checked — face verification was not completed</span>
              ) : result.watchlist_match ? (
                <strong style={{ color: "var(--red)" }}>
                  {t("result.watchlistMatch")} {result.watchlist_match_ref}
                  {result.watchlist_match_source && (
                    <span className="mini" style={{ fontWeight: 400, color: "var(--red)" }}>
                      {" "}(matched via {result.watchlist_match_source === "live_face" ? "live camera face" : "document photo"})
                    </span>
                  )}
                </strong>
              ) : (
                t("result.noMatch")
              )}
            </p>
          </div>
        </div>
      </div>

      <div className="card">
        <h2>{t("result.riskScore")}</h2>
        <div className="risk-gauge">
          <div className="score" style={{ color: `var(--${result.risk_level === "low" ? "green" : result.risk_level === "medium" ? "yellow" : "red"})` }}>
            {result.risk_score}
          </div>
          <div className="mini">/ 100 — {result.risk_level?.toUpperCase()}</div>
        </div>
        <RiskCalculation breakdown={result.risk_breakdown_json} score={result.risk_score} t={t} />
        <ModelCrosscheck data={result.model_crosscheck} />
      </div>

      <div className="card">
        <h2>{t("result.travelHistory")}</h2>
        {result.duplicate_of_record_id ? (
          <>
            <p>{t("result.duplicateFound")}</p>
            <p>{t("result.travelDirectionCheck")} <strong>{result.travel_direction_flag}</strong></p>
            {result.impossible_travel_detail_json && (
              <p className="mini">
                {t("result.distance")} {result.impossible_travel_detail_json.distance_km} km · {t("result.timeElapsed")}{" "}
                {result.impossible_travel_detail_json.time_elapsed_minutes} min · {t("result.requiredSpeed")}{" "}
                {result.impossible_travel_detail_json.required_speed_kmh} km/h
                {result.impossible_travel_flag ? t("result.exceedsSpeed") : ""}
              </p>
            )}
          </>
        ) : (
          <p>{t("result.noPriorRecord")}</p>
        )}
      </div>

      <FamilyPanel sessionId={sessionId} result={result} />

      <div className="card">
        <h2>{t("result.officerDecision")}</h2>
        {result.officer_decision ? (
          <p>
            {t("result.decisionRecorded", { decision: result.officer_decision.toUpperCase() })}{" "}
            <span className="mini">{t("result.at")} {result.decided_at}</span>
          </p>
        ) : (
          <div className="action-row">
            <button className="btn btn-green" disabled={deciding} onClick={() => decide("approved")}>
              {deciding && <Spinner size={14} inline />}{t("result.approve")}
            </button>
            <button className="btn btn-red" disabled={deciding} onClick={() => decide("rejected")}>
              {deciding && <Spinner size={14} inline />}{t("result.reject")}
            </button>
            <button className="btn btn-yellow" disabled={deciding} onClick={() => decide("escalated")}>
              {deciding && <Spinner size={14} inline />}{t("result.escalate")}
            </button>
          </div>
        )}
        {result.record_hash && <p className="mini">{t("result.auditHash")} {result.record_hash}</p>}
      </div>
    </VerifyShell>
  );
}
