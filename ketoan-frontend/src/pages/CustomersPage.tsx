import { useEffect, useState, type FormEvent } from "react";
import { api, ApiError } from "../api/client";
import type { Customer } from "../api/types";

export function CustomersPage() {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const [companyName, setCompanyName] = useState("");
  const [taxCode, setTaxCode] = useState("");
  const [address, setAddress] = useState("");
  const [phone, setPhone] = useState("");
  const [bankAccount, setBankAccount] = useState("");

  function loadCustomers() {
    setLoading(true);
    api
      .get<Customer[]>("/customers/")
      .then(setCustomers)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Không tải được danh sách"))
      .finally(() => setLoading(false));
  }

  useEffect(loadCustomers, []);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await api.post("/customers/", {
        company_name: companyName,
        tax_code: taxCode || null,
        address: address || null,
        contact_phone: phone || null,
        bank_account: bankAccount || null,
      });
      setCompanyName("");
      setTaxCode("");
      setAddress("");
      setPhone("");
      setBankAccount("");
      setShowForm(false);
      loadCustomers();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Không tạo được khách hàng");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-header__eyebrow">Bên mua · doanh nghiệp</div>
          <h1>Khách hàng</h1>
        </div>
        <button className="btn btn--primary" onClick={() => setShowForm((v) => !v)}>
          {showForm ? "Đóng" : "+ Thêm khách hàng"}
        </button>
      </div>

      {error && <div className="banner banner--error">{error}</div>}

      {showForm && (
        <div className="card" style={{ marginBottom: 24 }}>
          <h3>Khách hàng mới</h3>
          <form onSubmit={handleSubmit} className="form-grid">
            <div className="field">
              <label>Tên công ty *</label>
              <input value={companyName} onChange={(e) => setCompanyName(e.target.value)} required />
            </div>
            <div className="field">
              <label>Mã số thuế</label>
              <input value={taxCode} onChange={(e) => setTaxCode(e.target.value)} />
            </div>
            <div className="field">
              <label>Địa chỉ</label>
              <input value={address} onChange={(e) => setAddress(e.target.value)} />
            </div>
            <div className="field">
              <label>Điện thoại liên hệ</label>
              <input value={phone} onChange={(e) => setPhone(e.target.value)} />
            </div>
            <div className="field">
              <label>Số tài khoản ngân hàng</label>
              <input value={bankAccount} onChange={(e) => setBankAccount(e.target.value)} />
            </div>
            <button className="btn btn--primary" type="submit" disabled={submitting}>
              {submitting ? "Đang lưu…" : "Lưu khách hàng"}
            </button>
          </form>
        </div>
      )}

      <div className="card">
        {loading ? (
          <p>Đang tải…</p>
        ) : customers.length === 0 ? (
          <div className="empty-state">Chưa có khách hàng nào — bấm "+ Thêm khách hàng" để bắt đầu.</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Tên công ty</th>
                <th>Mã số thuế</th>
                <th>Địa chỉ</th>
                <th>Điện thoại</th>
              </tr>
            </thead>
            <tbody>
              {customers.map((c) => (
                <tr key={c.id}>
                  <td>{c.company_name}</td>
                  <td className="num">{c.tax_code || "—"}</td>
                  <td>{c.address || "—"}</td>
                  <td className="num">{c.contact_phone || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
