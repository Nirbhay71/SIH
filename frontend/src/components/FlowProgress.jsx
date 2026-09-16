const STEPS = [
  { key: "setup", label: "Setup" },
  { key: "capture", label: "Document" },
  { key: "pipeline", label: "Analysis" },
  { key: "face", label: "Face" },
  { key: "result", label: "Result" },
];

export default function FlowProgress({ current }) {
  const currentIndex = STEPS.findIndex((s) => s.key === current);
  return (
    <div className="flow-progress">
      {STEPS.map((s, i) => (
        <span key={s.key} style={{ display: "flex", alignItems: "center" }}>
          {i > 0 && <span className="flow-sep" />}
          <span className={`flow-step ${i < currentIndex ? "done" : i === currentIndex ? "current" : ""}`}>
            <span className="flow-dot">{i < currentIndex ? "✓" : i + 1}</span>
            {s.label}
          </span>
        </span>
      ))}
    </div>
  );
}
