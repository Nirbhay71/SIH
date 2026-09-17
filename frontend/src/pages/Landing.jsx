import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { motion } from "framer-motion";

const FEATURE_KEYS = [
  { num: "01", key: "ocr", img: "/images/document-passport.jpg" },
  { num: "02", key: "tampering", img: "/images/surveillance-camera.jpg" },
  { num: "03", key: "face", img: "/images/biometric-face.jpg" },
  { num: "04", key: "audit", img: "/images/airport-terminal.jpg" },
];

const EASE = [0.22, 1, 0.36, 1];

const heroContainer = {
  hidden: {},
  show: { transition: { staggerChildren: 0.12, delayChildren: 0.35 } },
};
const heroItem = {
  hidden: { opacity: 0, y: 28 },
  show: { opacity: 1, y: 0, transition: { duration: 0.8, ease: EASE } },
};

const panelsContainer = {
  hidden: {},
  show: { transition: { staggerChildren: 0.15, delayChildren: 0.9 } },
};
const panelItem = {
  hidden: { opacity: 0, x: 36 },
  show: { opacity: 1, x: 0, transition: { duration: 0.7, ease: EASE } },
};

const gridContainer = {
  hidden: {},
  show: { transition: { staggerChildren: 0.1 } },
};
const gridItem = {
  hidden: { opacity: 0, y: 30 },
  show: { opacity: 1, y: 0, transition: { duration: 0.6, ease: EASE } },
};

export default function Landing() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const goVerify = () => navigate("/verify/setup");

  return (
    <div className="landing-page">
      <section className="hero-cine">
        <motion.div
          className="hero-cine-bg"
          style={{ backgroundImage: "url(/images/hero-airport.jpg)" }}
          aria-hidden="true"
          initial={{ scale: 1.18, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ duration: 1.8, ease: EASE }}
        />
        <motion.div
          className="hero-cine-scrim"
          aria-hidden="true"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 1.2, ease: EASE }}
        />
        <div className="hero-cine-grid" aria-hidden="true" />

        <motion.div className="hero-cine-content" variants={heroContainer} initial="hidden" animate="show">
          <motion.div className="eyebrow" variants={heroItem}>{t("landing.eyebrow")} · PS 26188</motion.div>
          <motion.h1 className="hero-cine-title" variants={heroItem}>{t("landing.title")}</motion.h1>
          <motion.p className="subtitle" variants={heroItem}>{t("landing.subtitle")}</motion.p>
          <motion.div className="hero-cine-actions" variants={heroItem}>
            <button className="btn btn-gradient" onClick={goVerify}>{t("nav.startVerification")}</button>
            <a href="#modules" className="btn btn-ghost">{t("landing.exploreSystem")}</a>
          </motion.div>
        </motion.div>

        <motion.div className="hero-cine-panels" variants={panelsContainer} initial="hidden" animate="show">
          <motion.div
            className="cine-panel"
            style={{ "--panel-img": "url(/images/document-passport.jpg)" }}
            variants={panelItem}
          >
            <span className="cine-panel-num">01</span>
            <h3>{t("landing.moduleDocIntel.title")}</h3>
            <p>{t("landing.moduleDocIntel.desc")}</p>
          </motion.div>

          <motion.div
            className="cine-panel cine-panel-accent"
            style={{ "--panel-img": "url(/images/biometric-face.jpg)" }}
            variants={panelItem}
          >
            <span className="cine-panel-num">02</span>
            <h3>{t("landing.moduleBiometric.title")}</h3>
            <p>{t("landing.moduleBiometric.desc")}</p>
            <div className="scan-strip"><span className="scan-strip-line" /></div>
            <div className="cine-live"><span className="live-dot" />{t("landing.liveLabel")}</div>
          </motion.div>

          <motion.div className="cine-stats" variants={panelItem}>
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
          </motion.div>
        </motion.div>
      </section>

      <motion.div
        className="promo-banner"
        initial={{ opacity: 0, y: 16 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, amount: 0.6 }}
        transition={{ duration: 0.6, ease: EASE }}
      >
        <span>{t("landing.promoBanner")}</span>
        <button className="btn btn-outline" style={{ padding: "6px 14px", fontSize: 13 }} onClick={goVerify}>
          {t("landing.tryIt")}
        </button>
      </motion.div>

      <motion.div
        className="section-header"
        initial={{ opacity: 0, y: 16 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, amount: 0.6 }}
        transition={{ duration: 0.6, ease: EASE }}
      >
        <div className="eyebrow">{t("landing.modulesEyebrow")}</div>
        <h2>{t("landing.modulesTitle")}</h2>
        <p>{t("landing.modulesSubtitle")}</p>
      </motion.div>

      <motion.section
        id="modules"
        className="module-grid"
        variants={gridContainer}
        initial="hidden"
        whileInView="show"
        viewport={{ once: true, amount: 0.2 }}
      >
        {FEATURE_KEYS.map((f) => (
          <motion.div
            className="module-card"
            key={f.key}
            style={{ "--card-img": `url(${f.img})` }}
            variants={gridItem}
          >
            <span className="module-num">{f.num}</span>
            <h4>{t(`landing.features.${f.key}.title`)}</h4>
            <p>{t(`landing.features.${f.key}.desc`)}</p>
            <span className="module-arrow">{t("landing.explore")}</span>
          </motion.div>
        ))}
      </motion.section>

      <section className="final-cta">
        <div className="final-cta-bg" style={{ backgroundImage: "url(/images/hero-airport.jpg)" }} aria-hidden="true" />
        <div className="final-cta-scrim" aria-hidden="true" />
        <div className="final-cta-grid" aria-hidden="true" />
        <motion.div
          className="final-cta-inner"
          initial={{ opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.5 }}
          transition={{ duration: 0.7, ease: EASE }}
        >
          <h2>{t("landing.finalCtaTitle")}</h2>
          <p>{t("landing.finalCtaSubtitle")}</p>
          <button className="btn btn-gradient" onClick={goVerify}>{t("nav.startVerification")}</button>
        </motion.div>
      </section>
    </div>
  );
}
