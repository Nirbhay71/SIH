import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";

const FEATURE_KEYS = [
  { icon: "🔍", key: "ocr" },
  { icon: "🛡️", key: "tampering" },
  { icon: "🧑‍🤝‍🧑", key: "face" },
  { icon: "⛓️", key: "audit" },
];

export default function Landing() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  return (
    <div className="landing-page">
      <div className="landing-hero">
        <div>
          <div className="eyebrow">{t("landing.eyebrow")}</div>
          <h1>{t("landing.title")}</h1>
          <p className="subtitle">{t("landing.subtitle")}</p>
          <button className="btn btn-gradient" style={{ fontSize: 15, padding: "12px 26px" }} onClick={() => navigate("/verify/setup")}>
            {t("landing.verifyDocument")}
          </button>
        </div>

        <div className="hero-card">
          <div className="hero-card-icon">🪪</div>
          <h3>{t("landing.heroCardTitle")}</h3>
          <p>{t("landing.heroCardDesc")}</p>
          <div className="hero-stats">
            <div>
              <div className="stat-num">4</div>
              <div className="stat-label">{t("landing.aiModules")}</div>
            </div>
            <div>
              <div className="stat-num">&lt;10s</div>
              <div className="stat-label">{t("landing.perDocument")}</div>
            </div>
            <div>
              <div className="stat-num">100%</div>
              <div className="stat-label">{t("landing.auditTrail")}</div>
            </div>
          </div>
        </div>
      </div>

      <div className="promo-banner">
        <span>{t("landing.promoBanner")}</span>
        <button className="btn btn-outline" style={{ padding: "6px 14px", fontSize: 13 }} onClick={() => navigate("/verify/setup")}>
          {t("landing.tryIt")}
        </button>
      </div>

      <div className="feature-grid">
        {FEATURE_KEYS.map((f) => (
          <div className="feature" key={f.key}>
            <div className="feature-icon">{f.icon}</div>
            <h4>{t(`landing.features.${f.key}.title`)}</h4>
            <p>{t(`landing.features.${f.key}.desc`)}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
