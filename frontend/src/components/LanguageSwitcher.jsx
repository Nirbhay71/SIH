import { useTranslation } from "react-i18next";

const LANGUAGES = [
  { code: "en", label: "English" },
  { code: "hi", label: "हिन्दी" },
  { code: "ne", label: "नेपाली" },
];

export default function LanguageSwitcher() {
  const { i18n } = useTranslation();

  function changeLanguage(code) {
    i18n.changeLanguage(code);
    localStorage.setItem("bss_lang", code);
  }

  return (
    <select
      className="lang-switcher"
      value={i18n.resolvedLanguage || i18n.language}
      onChange={(e) => changeLanguage(e.target.value)}
      aria-label="Language"
    >
      {LANGUAGES.map((l) => (
        <option key={l.code} value={l.code}>
          {l.label}
        </option>
      ))}
    </select>
  );
}
