const STAGES = [
  { key: "setup", label: "Setup", desc: "Confirm checkpoint & location" },
  { key: "capture", label: "Document", desc: "Scan and verify your travel document" },
  { key: "pipeline", label: "Analysis", desc: "OCR, tampering and data checks running" },
  { key: "face", label: "Face", desc: "Matching your live face to the document photo" },
  { key: "result", label: "Result", desc: "Final explainable risk decision" },
];

export default function VerifyShell({ current, status, children }) {
  const currentIndex = STAGES.findIndex((s) => s.key === current);
  const activeStage = STAGES[currentIndex] || STAGES[0];

  return (
    <div className="verify-screen">
      <div className="verify-left">
        <h1 className="verify-left-title">Identity Verification</h1>
        <p className="verify-left-sub">
          Securely verify your identity using document and facial verification.
        </p>

        <div className="verify-timeline">
          {STAGES.map((s, i) => {
            const state = i < currentIndex ? "done" : i === currentIndex ? "active" : "upcoming";
            return (
              <div key={s.key} className={`verify-tl-item verify-tl-${state}`}>
                <div className="verify-tl-rail">
                  <span className="verify-tl-node">
                    {state === "done" ? "✓" : state === "active" ? <span className="verify-tl-pulse" /> : ""}
                  </span>
                  {i < STAGES.length - 1 && <span className="verify-tl-line" />}
                </div>
                <div className="verify-tl-body">
                  <strong>{s.label}</strong>
                  {state === "active" && <p>{s.desc}</p>}
                </div>
              </div>
            );
          })}
        </div>

        <div className="verify-current-card">
          <span className="verify-current-label">Currently</span>
          <strong>{activeStage.label}</strong>
          <p>{status}</p>
        </div>
      </div>

      <div className="verify-right">
        <div className="verify-right-inner">{children}</div>
      </div>
    </div>
  );
}
