import { useEffect, useState, type FormEvent } from "react";
import { api, ApiError } from "../api/client";
import type { CompanySettings, RoleName, UserOut } from "../api/types";
import { useAuth } from "../contexts/AuthContext";

export function SettingsPage() {
  const { user } = useAuth();
  const isGiamDoc = user?.role_name === "giam_doc";

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-header__eyebrow">Quản trị</div>
          <h1>Cài đặt</h1>
        </div>
      </div>

      <div style={{ display: "grid", gap: 24 }}>
        <ChangePasswordSection />
        {isGiamDoc && <CompanySettingsSection />}
        {isGiamDoc && <UsersSection />}
      </div>
    </div>
  );
}

function ChangePasswordSection() {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [message, setMessage] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setMessage(null);
    try {
      await api.post("/auth/change-password", { current_password: currentPassword, new_password: newPassword });
      setMessage({ kind: "ok", text: "Đã đổi mật khẩu thành công." });
      setCurrentPassword("");
      setNewPassword("");
    } catch (err) {
      setMessage({ kind: "error", text: err instanceof ApiError ? err.message : "Không đổi được mật khẩu" });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="card" style={{ maxWidth: 420 }}>
      <h3>Đổi mật khẩu</h3>
      {message && <div className={`banner banner--${message.kind === "ok" ? "info" : "error"}`}>{message.text}</div>}
      <form onSubmit={handleSubmit} className="form-grid">
        <div className="field">
          <label>Mật khẩu hiện tại</label>
          <input type="password" value={currentPassword} onChange={(e) => setCurrentPassword(e.target.value)} required />
        </div>
        <div className="field">
          <label>Mật khẩu mới (tối thiểu 8 ký tự)</label>
          <input type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} minLength={8} required />
        </div>
        <button className="btn btn--primary" type="submit" disabled={submitting}>
          {submitting ? "Đang lưu…" : "Đổi mật khẩu"}
        </button>
      </form>
    </div>
  );
}

function CompanySettingsSection() {
  const [settings, setSettings] = useState<CompanySettings>({
    company_name: "",
    company_address: "",
    company_tax_code: "",
    company_phone: "",
  });
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    api
      .get<CompanySettings>("/settings/company")
      .then(setSettings)
      .catch(() => setMessage({ kind: "error", text: "Không tải được thông tin công ty" }))
      .finally(() => setLoading(false));
  }, []);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setMessage(null);
    try {
      await api.put("/settings/company", settings);
      setMessage({ kind: "ok", text: "Đã lưu thông tin công ty. Sẽ hiện trên các phiếu in ra từ giờ." });
    } catch (err) {
      setMessage({ kind: "error", text: err instanceof ApiError ? err.message : "Không lưu được" });
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) return <div className="card">Đang tải…</div>;

  return (
    <div className="card" style={{ maxWidth: 480 }}>
      <h3>Thông tin công ty</h3>
      <p style={{ color: "var(--color-ink-soft)", fontSize: "0.85rem", marginTop: -8 }}>
        Hiện trên phần đầu mọi phiếu chi và Bảng kê 02/TNDN khi xuất file.
      </p>
      {message && <div className={`banner banner--${message.kind === "ok" ? "info" : "error"}`}>{message.text}</div>}
      <form onSubmit={handleSubmit} className="form-grid">
        <div className="field">
          <label>Tên công ty</label>
          <input value={settings.company_name} onChange={(e) => setSettings({ ...settings, company_name: e.target.value })} />
        </div>
        <div className="field">
          <label>Địa chỉ</label>
          <input value={settings.company_address} onChange={(e) => setSettings({ ...settings, company_address: e.target.value })} />
        </div>
        <div className="field">
          <label>Mã số thuế</label>
          <input value={settings.company_tax_code} onChange={(e) => setSettings({ ...settings, company_tax_code: e.target.value })} />
        </div>
        <div className="field">
          <label>Số điện thoại</label>
          <input value={settings.company_phone} onChange={(e) => setSettings({ ...settings, company_phone: e.target.value })} />
        </div>
        <button className="btn btn--primary" type="submit" disabled={submitting}>
          {submitting ? "Đang lưu…" : "Lưu thông tin công ty"}
        </button>
      </form>
    </div>
  );
}

const ROLE_OPTIONS: { value: RoleName; label: string }[] = [
  { value: "giam_doc", label: "Giám đốc" },
  { value: "ke_toan", label: "Kế toán" },
  { value: "thu_quy", label: "Thủ quỹ" },
  { value: "nhan_vien", label: "Nhân viên" },
];

function UsersSection() {
  const [users, setUsers] = useState<UserOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const [username, setUsername] = useState("");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [roleName, setRoleName] = useState<RoleName>("ke_toan");

  function loadUsers() {
    setLoading(true);
    api
      .get<UserOut[]>("/users/")
      .then(setUsers)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Không tải được danh sách"))
      .finally(() => setLoading(false));
  }

  useEffect(loadUsers, []);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await api.post("/users/", { username, full_name: fullName, password, role_name: roleName });
      setUsername("");
      setFullName("");
      setPassword("");
      setShowForm(false);
      loadUsers();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Không tạo được tài khoản");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="card" style={{ maxWidth: 560 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <h3>Tài khoản người dùng</h3>
        <button className="btn btn--ghost" onClick={() => setShowForm((v) => !v)}>
          {showForm ? "Đóng" : "+ Thêm tài khoản"}
        </button>
      </div>

      {error && <div className="banner banner--error">{error}</div>}

      {showForm && (
        <form onSubmit={handleSubmit} className="form-grid" style={{ marginBottom: 20 }}>
          <div className="field">
            <label>Tên đăng nhập *</label>
            <input value={username} onChange={(e) => setUsername(e.target.value)} required />
          </div>
          <div className="field">
            <label>Họ và tên *</label>
            <input value={fullName} onChange={(e) => setFullName(e.target.value)} required />
          </div>
          <div className="field">
            <label>Mật khẩu ban đầu * (tối thiểu 8 ký tự)</label>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} minLength={8} required />
          </div>
          <div className="field">
            <label>Vai trò</label>
            <select value={roleName} onChange={(e) => setRoleName(e.target.value as RoleName)}>
              {ROLE_OPTIONS.map((r) => (
                <option key={r.value} value={r.value}>
                  {r.label}
                </option>
              ))}
            </select>
          </div>
          <button className="btn btn--primary" type="submit" disabled={submitting}>
            {submitting ? "Đang lưu…" : "Tạo tài khoản"}
          </button>
        </form>
      )}

      {loading ? (
        <p>Đang tải…</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Tên đăng nhập</th>
              <th>Họ và tên</th>
              <th>Vai trò</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id}>
                <td>{u.username}</td>
                <td>{u.full_name}</td>
                <td>{ROLE_OPTIONS.find((r) => r.value === u.role_name)?.label || u.role_name}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
