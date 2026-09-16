import { useState } from "react";
import { useTranslation } from "react-i18next";
import { listWatchlist, addWatchlist, deleteWatchlist } from "../lib/api";

export default function AdminWatchlist() {
  const { t } = useTranslation();
  const [creds, setCreds] = useState(null);
  const [form, setForm] = useState({ username: "admin", password: "" });
  const [entries, setEntries] = useState([]);
  const [label, setLabel] = useState("");
  const [file, setFile] = useState(null);
  const [error, setError] = useState(null);

  async function login(e) {
    e.preventDefault();
    setError(null);
    try {
      const data = await listWatchlist(form);
      setEntries(data);
      setCreds(form);
    } catch {
      setError(t("admin.invalidCredentials"));
    }
  }

  async function refresh(activeCreds) {
    setEntries(await listWatchlist(activeCreds));
  }

  async function handleAdd(e) {
    e.preventDefault();
    if (!file || !label) return;
    await addWatchlist(creds, label, file);
    setLabel("");
    setFile(null);
    refresh(creds);
  }

  async function handleDelete(id) {
    await deleteWatchlist(creds, id);
    refresh(creds);
  }

  if (!creds) {
    return (
      <form className="card" style={{ maxWidth: 380, margin: "0 auto" }} onSubmit={login}>
        <h2>{t("admin.loginTitle")}</h2>
        <label>{t("admin.username")}</label>
        <input type="text" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} />
        <label>{t("admin.password")}</label>
        <input type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
        {error && <p style={{ color: "var(--red)" }}>{error}</p>}
        <button className="btn btn-primary btn-block" type="submit">{t("admin.logIn")}</button>
        <p className="mini" style={{ marginTop: 10 }}>{t("admin.demoCredentials")}</p>
      </form>
    );
  }

  return (
    <div>
      <div className="card">
        <h2>{t("admin.addEntryTitle")}</h2>
        <p className="subtitle mini">{t("admin.addEntryTip")}</p>
        <form onSubmit={handleAdd}>
          <label>{t("admin.referenceLabel")}</label>
          <input type="text" value={label} onChange={(e) => setLabel(e.target.value)} placeholder={t("admin.referencePlaceholder")} />
          <label>{t("admin.photo")}</label>
          <input type="file" accept="image/*" onChange={(e) => setFile(e.target.files[0])} style={{ marginBottom: 14 }} />
          <button className="btn btn-primary" type="submit">{t("admin.addToWatchlist")}</button>
        </form>
      </div>

      <div className="card">
        <h2>{t("admin.entriesTitle")} ({entries.length})</h2>
        {entries.map((e) => (
          <div key={e.id} className="watchlist-item">
            <img src={e.photo_url} alt={e.reference_label} />
            <div style={{ flex: 1 }}>
              <div>{e.reference_label}</div>
              <div className="mini">{t("admin.added")} {new Date(e.uploaded_at).toLocaleString()}</div>
            </div>
            <button className="btn btn-outline" onClick={() => handleDelete(e.id)}>{t("admin.remove")}</button>
          </div>
        ))}
        {entries.length === 0 && <p className="mini">{t("admin.noEntries")}</p>}
      </div>
    </div>
  );
}
