import { useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import type { Seller, SellerDuplicateCandidate } from "../api/types";

export function SellersPage() {
  const [sellers, setSellers] = useState<Seller[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [address, setAddress] = useState("");
  const [idCard, setIdCard] = useState("");
  const [phone, setPhone] = useState("");
  const [duplicates, setDuplicates] = useState<SellerDuplicateCandidate[]>([]);
  const [checkingDup, setCheckingDup] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  function loadSellers() {
    setLoading(true);
    api
      .get<Seller[]>("/sellers/")
      .then(setSellers)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Không tải được danh sách"))
      .finally(() => setLoading(false));
  }

  useEffect(loadSellers, []);

  // Kiểm tra trùng tên khi người dùng dừng gõ 400ms — cảnh báo NGAY khi tạo,
  // đúng vấn đề đã gặp thật với dữ liệu Excel cũ (cùng người, viết tên khác nhau).
  useEffect(() => {
    if (name.trim().length < 3) {
      setDuplicates([]);
      return;
    }
    const timer = setTimeout(() => {
      setCheckingDup(true);
      api
        .get<SellerDuplicateCandidate[]>(`/sellers/check-duplicate?name=${encodeURIComponent(name)}`)
        .then(setDuplicates)
        .catch(() => setDuplicates([]))
        .finally(() => setCheckingDup(false));
    }, 400);
    return () => clearTimeout(timer);
  }, [name]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await api.post("/sellers/", {
        name,
        address: address || null,
        id_card_number: idCard || null,
        phone: phone || null,
      });
      setName("");
      setAddress("");
      setIdCard("");
      setPhone("");
      setDuplicates([]);
      setShowForm(false);
      loadSellers();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Không tạo được người bán");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-header__eyebrow">Bên bán · cá nhân</div>
          <h1>Người bán</h1>
        </div>
        <button className="btn btn--primary" onClick={() => setShowForm((v) => !v)}>
          {showForm ? "Đóng" : "+ Thêm người bán"}
        </button>
      </div>

      {error && <div className="banner banner--error">{error}</div>}

      {showForm && (
        <div className="card" style={{ marginBottom: 24 }}>
          <h3>Người bán mới</h3>
          <form onSubmit={handleSubmit} className="form-grid">
            <div className="field">
              <label>Họ và tên *</label>
              <input value={name} onChange={(e) => setName(e.target.value)} required />
            </div>

            {checkingDup && <div style={{ fontSize: "0.82rem", color: "var(--color-ink-soft)" }}>Đang kiểm tra trùng…</div>}

            {duplicates.length > 0 && (
              <div className="banner banner--warn">
                Có thể trùng với người bán đã có:
                <ul style={{ margin: "6px 0 0 0", paddingLeft: 18 }}>
                  {duplicates.map((d) => (
                    <li key={d.seller.id}>
                      {d.seller.name} (giống {d.similarity_score.toFixed(0)}%)
                    </li>
                  ))}
                </ul>
                Vẫn có thể tạo tiếp nếu chắc chắn đây là người khác.
              </div>
            )}

            <div className="field">
              <label>Địa chỉ</label>
              <input value={address} onChange={(e) => setAddress(e.target.value)} />
            </div>
            <div className="field">
              <label>Số căn cước</label>
              <input value={idCard} onChange={(e) => setIdCard(e.target.value)} />
            </div>
            <div className="field">
              <label>Số điện thoại</label>
              <input value={phone} onChange={(e) => setPhone(e.target.value)} />
            </div>
            <button className="btn btn--primary" type="submit" disabled={submitting}>
              {submitting ? "Đang lưu…" : "Lưu người bán"}
            </button>
          </form>
        </div>
      )}

      <div className="card">
        {loading ? (
          <p>Đang tải…</p>
        ) : sellers.length === 0 ? (
          <div className="empty-state">Chưa có người bán nào — bấm "+ Thêm người bán" để bắt đầu.</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Họ và tên</th>
                <th>Địa chỉ</th>
                <th>Số căn cước</th>
                <th>Điện thoại</th>
              </tr>
            </thead>
            <tbody>
              {sellers.map((s) => (
                <tr key={s.id}>
                  <td>{s.name}</td>
                  <td>{s.address || "—"}</td>
                  <td className="num">{s.id_card_number || "—"}</td>
                  <td className="num">{s.phone || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
