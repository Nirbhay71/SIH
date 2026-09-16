import { useTranslation } from "react-i18next";

const STAGE_KEYS = ["setup", "capture", "pipeline", "face", "result"];

export default function VerifyShell({ current, status, children }) {
  const { t } = useTranslation();
  const currentIndex = STAGE_KEYS.indexOf(current);
  const activeLabel = t(`verifyShell.stages.${STAGE_KEYS[currentIndex] || STAGE_KEYS[0]}.label`);

  return (
    <div className="verify-screen">
      <div className="verify-left">
        <h1 className="verify-left-title">{t("verifyShell.title")}</h1>
        <p className="verify-left-sub">{t("verifyShell.subtitle")}</p>

        <div className="verify-timeline">
          {STAGE_KEYS.map((key, i) => {
            const state = i < currentIndex ? "done" : i === currentIndex ? "active" : "upcoming";
            return (
              <div key={key} className={`verify-tl-item verify-tl-${state}`}>
                <div className="verify-tl-rail">
                  <span className="verify-tl-node">
                    {state === "done" ? "✓" : state === "active" ? <span className="verify-tl-pulse" /> : ""}
                  </span>
                  {i < STAGE_KEYS.length - 1 && <span className="verify-tl-line" />}
                </div>
                <div className="verify-tl-body">
                  <strong>{t(`verifyShell.stages.${key}.label`)}</strong>
                  {state === "active" && <p>{t(`verifyShell.stages.${key}.desc`)}</p>}
                </div>
              </div>
            );
          })}
        </div>

        <div className="verify-current-card">
          <span className="verify-current-label">{t("verifyShell.currently")}</span>
          <strong>{activeLabel}</strong>
          <p>{status}</p>
        </div>
      </div>

      <div className="verify-right">
        <div className="verify-right-inner">{children}</div>
      </div>
    </div>
  );
}
