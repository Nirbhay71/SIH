import { useEffect, useState } from "react";
import { Link, NavLink } from "react-router-dom";
import { useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import LanguageSwitcher from "./LanguageSwitcher.jsx";

const NAV_LINKS = [
  { to: "/", key: "nav.home", end: true },
  { to: "/audit", key: "nav.audit" },
  { to: "/admin/watchlist", key: "nav.admin" },
];

export default function Navbar() {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const location = useLocation();

  useEffect(() => setOpen(false), [location.pathname]);

  return (
    <header className="navbar">
      <Link to="/" className="navbar-brand" onClick={() => setOpen(false)}>
        <span className="navbar-brand-mark" aria-hidden="true">🛂</span>
        <span className="navbar-brand-text">
          {t("appName")}
          <small>{t("appTagline")}</small>
        </span>
      </Link>

      <button
        type="button"
        className={`navbar-toggle ${open ? "is-open" : ""}`}
        aria-label={open ? "Close menu" : "Open menu"}
        aria-expanded={open}
        aria-controls="primary-navigation"
        onClick={() => setOpen((v) => !v)}
      >
        <span />
        <span />
        <span />
      </button>

      <nav id="primary-navigation" className={`navbar-links ${open ? "is-open" : ""}`}>
        {NAV_LINKS.map((link) => (
          <NavLink
            key={link.to}
            to={link.to}
            end={link.end}
            className={({ isActive }) => "navbar-link" + (isActive ? " active" : "")}
          >
            {t(link.key)}
          </NavLink>
        ))}
        <div className="navbar-lang"><LanguageSwitcher /></div>
        <NavLink to="/verify/setup" className="btn-gradient navbar-cta">
          {t("nav.startVerification")}
        </NavLink>
      </nav>
    </header>
  );
}
