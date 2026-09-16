import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { openPipelineSocket } from "../lib/api";
import VerifyShell from "../components/VerifyShell.jsx";
import { ThinkingLoader } from "../components/Loader.jsx";

const VISIBLE_STEP_KEYS = ["ocr", "validation", "tampering", "face", "risk_score"];

const FOLDED_INTO_RISK = ["watchlist", "duplicate_check", "risk_score"];

export default function Pipeline() {
  const { sessionId } = useParams();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [searchParams] = useSearchParams();
  const skipToFace = searchParams.get("after") === "face";
  const [stepStatus, setStepStatus] = useState({});
  const [logs, setLogs] = useState([]);
  const logRef = useRef(null);
  const wsRef = useRef(null);
  const navigatedRef = useRef(false);

  useEffect(() => {
    const ws = openPipelineSocket(sessionId);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      const visibleKey = FOLDED_INTO_RISK.includes(msg.stage) ? "risk_score" : msg.stage;

      setStepStatus((prev) => {
        const next = { ...prev };
        if (msg.status === "started" || msg.status === "progress") {
          if (next[visibleKey] !== "flagged") next[visibleKey] = "active";
        } else if (msg.status === "done") {
          next[visibleKey] = prev[visibleKey] === "flagged" ? "flagged" : "passed";
        } else if (msg.status === "error") {
          next[visibleKey] = "flagged";
        }
        return next;
      });

      setLogs((prev) => [...prev, msg]);

      if (msg.stage === "tampering" && msg.status === "done" && !navigatedRef.current && !skipToFace) {
        navigatedRef.current = true;
        setTimeout(() => navigate(`/verify/face/${sessionId}`), 900);
      }
      if (msg.stage === "risk_score" && msg.status === "done") {
        setTimeout(() => navigate(`/verify/result/${sessionId}`), 1200);
      }
    };

    return () => ws.close();
  }, [sessionId, navigate]);

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [logs]);

  const activeKey = VISIBLE_STEP_KEYS.find((k) => stepStatus[k] === "active");
  const status = activeKey ? t("pipeline.running", { stage: t(`pipeline.steps.${activeKey}`) }) : t("pipeline.runningGeneric");

  return (
    <VerifyShell current="pipeline" status={status}>
      <h2>{t("pipeline.title")}</h2>
      <div className="stepper">
        {VISIBLE_STEP_KEYS.map((key) => {
          const s = stepStatus[key] || "pending";
          return (
            <div key={key} className={`step ${s}`}>
              <div className="dot">
                {s === "passed" ? "✓" : s === "flagged" ? "!" : ""}
              </div>
              <div className="label">{t(`pipeline.steps.${key}`)}</div>
            </div>
          );
        })}
      </div>

      {stepStatus.risk_score === "active" && <ThinkingLoader label={t("pipeline.computingRisk")} />}

      <div className="log-panel" ref={logRef}>
        {logs.map((msg, i) => (
          <div key={i} className={`log-line ${msg.status === "error" ? "error" : ""}`} style={{ animationDelay: `${i * 0.02}s` }}>
            [{msg.stage}] {msg.log}
          </div>
        ))}
      </div>
    </VerifyShell>
  );
}
