import { useEffect, useState } from "react";
import { listWatchlist, addWatchlist, deleteWatchlist } from "../lib/api";

export default function AdminWatchlist() {
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
      setError("Invalid credentials");
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
        <h2>Admin Login</h2>
        <label>Username</label>
        <input type="text" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} />
        <label>Password</label>
        <input type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
        {error && <p style={{ color: "var(--red)" }}>{error}</p>}
        <button className="btn btn-primary btn-block" type="submit">Log In</button>
        <p className="mini" style={{ marginTop: 10 }}>Demo credentials: admin / admin123 (see backend .env)</p>
      </form>
    );
  }

  return (
    <div>
      <div className="card">
        <h2>Add Watchlist Entry</h2>
        <p className="subtitle mini">
          Tip for the live demo: upload the presenter's own captured face photo here right before the demo, then
          re-scan the same photo at the checkpoint to trigger a watchlist match on stage.
        </p>
        <form onSubmit={handleAdd}>
          <label>Reference Label</label>
          <input type="text" value={label} onChange={(e) => setLabel(e.target.value)} placeholder="e.g. Case #4471 (fictional)" />
          <label>Photo</label>
          <input type="file" accept="image/*" onChange={(e) => setFile(e.target.files[0])} style={{ marginBottom: 14 }} />
          <button className="btn btn-primary" type="submit">Add to Watchlist</button>
        </form>
      </div>

      <div className="card">
        <h2>Watchlist Entries ({entries.length})</h2>
        {entries.map((e) => (
          <div key={e.id} className="watchlist-item">
            <img src={e.photo_url} alt={e.reference_label} />
            <div style={{ flex: 1 }}>
              <div>{e.reference_label}</div>
              <div className="mini">Added {new Date(e.uploaded_at).toLocaleString()}</div>
            </div>
            <button className="btn btn-outline" onClick={() => handleDelete(e.id)}>Remove</button>
          </div>
        ))}
        {entries.length === 0 && <p className="mini">No entries yet.</p>}
      </div>
    </div>
  );
}
