import { useState, type FormEvent } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import { ApiError } from "../api/client";

export function LoginPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (user) return <Navigate to="/dashboard" replace />;

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(username, password);
      navigate("/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Không đăng nhập được — kiểm tra lại kết nối");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "var(--color-primary)",
      }}
    >
      <div className="card" style={{ width: 360 }}>
        <div style={{ marginBottom: 22 }}>
          <div className="page-header__eyebrow">Hệ thống kế toán nội bộ</div>
          <h1 style={{ marginBottom: 0 }}>Đăng nhập</h1>
        </div>

        {error && <div className="banner banner--error">{error}</div>}

        <form onSubmit={handleSubmit} className="form-grid">
          <div className="field">
            <label htmlFor="username">Tên đăng nhập</label>
            <input
              id="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoFocus
              required
            />
          </div>
          <div className="field">
            <label htmlFor="password">Mật khẩu</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          <button className="btn btn--primary" type="submit" disabled={submitting}>
            {submitting ? "Đang đăng nhập…" : "Đăng nhập"}
          </button>
        </form>
      </div>
    </div>
  );
}
