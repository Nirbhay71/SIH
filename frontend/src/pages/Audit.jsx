import { useState } from "react";
import { verifyChain } from "../lib/api";

export default function Audit() {
  const [result, setResult] = useState(null);
  const [checking, setChecking] = useState(false);

  async function check() {
    setChecking(true);
    try {
      setResult(await verifyChain());
    } finally {
      setChecking(false);
    }
  }

  return (
    <div className="card" style={{ maxWidth: 560, margin: "0 auto" }}>
      <h2>Hash-Chain Audit Trail</h2>
      <p className="subtitle">
        Every officer decision is chained to the previous one with SHA-256 (previous_hash + record data). If any
        past record is altered, the chain breaks and is detectable — this is the tamper-evidence property at the
        core of blockchain technology, without a multi-node consensus layer SSB (a single authority) doesn't need.
      </p>
      <button className="btn btn-primary" onClick={check} disabled={checking}>
        {checking ? "Verifying..." : "Verify Audit Trail"}
      </button>

      {result && (
        <div className="card" style={{ marginTop: 20, background: result.valid ? "#f0fdf4" : "#fef2f2" }}>
          <h2 style={{ color: result.valid ? "var(--green)" : "var(--red)" }}>
            {result.valid ? "✅ Chain Intact" : "❌ Chain Broken"}
          </h2>
          <p>Records checked: {result.checked}</p>
          {!result.valid && <p>First broken record: {result.first_broken_record_id}</p>}
        </div>
      )}
    </div>
  );
}
