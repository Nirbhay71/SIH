export function Spinner({ size = 18, inline = false }) {
  return (
    <span
      className={`spinner ${inline ? "spinner-inline" : ""}`}
      style={{ width: size, height: size, borderWidth: Math.max(2, size / 7) }}
    />
  );
}

export function ThinkingLoader({ label = "Thinking..." }) {
  return (
    <div className="thinking-loader">
      <span className="spinner spinner-lg" />
      <span className="thinking-text">
        {label}
        <span className="dots">
          <span>.</span><span>.</span><span>.</span>
        </span>
      </span>
    </div>
  );
}
