import { useState } from "react";
import { useTranslation } from "react-i18next";
import { verifyChain } from "../lib/api";

export default function Audit() {
  const { t } = useTranslation();
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
      <h2>{t("audit.title")}</h2>
      <p className="subtitle">{t("audit.subtitle")}</p>
      <button className="btn btn-primary" onClick={check} disabled={checking}>
        {checking ? t("audit.verifying") : t("audit.verifyButton")}
      </button>

      {result && (
        <div className="card" style={{ marginTop: 20, background: result.valid ? "#f0fdf4" : "#fef2f2" }}>
          <h2 style={{ color: result.valid ? "var(--green)" : "var(--red)" }}>
            {result.valid ? t("audit.chainIntact") : t("audit.chainBroken")}
          </h2>
          <p>{t("audit.recordsChecked")} {result.checked}</p>
          {!result.valid && <p>{t("audit.firstBroken")} {result.first_broken_record_id}</p>}
        </div>
      )}
    </div>
  );
}
