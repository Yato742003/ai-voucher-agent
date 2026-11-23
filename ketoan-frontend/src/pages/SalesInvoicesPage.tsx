import { useEffect, useMemo, useState, type FormEvent } from "react";
import { api, ApiError } from "../api/client";
import type { Customer, PaymentMethod, SalesInvoice } from "../api/types";
import { SALES_INVOICE_STATUS_LABEL } from "../api/types";
import { useToast } from "../contexts/ToastContext";

export function SalesInvoicesPage() {
  const { showToast } = useToast();
  const [invoices, setInvoices] = useState<SalesInvoice[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [markingId, setMarkingId] = useState<string | null>(null);
  const [soHoaDon, setSoHoaDon] = useState("");
  const [kyHieu, setKyHieu] = useState("");

  const customerById = useMemo(() => Object.fromEntries(customers.map((c) => [c.id, c.company_name])), [customers]);

  function loadData() {
    setLoading(true);
    setError(null);
    Promise.all([api.get<SalesInvoice[]>("/sales-invoices/"), api.get<Customer[]>("/customers/")])
      .then(([inv, cust]) => {
        setInvoices(inv);
        setCustomers(cust);
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : "Không tải được dữ liệu"))
      .finally(() => setLoading(false));
  }

  useEffect(loadData, []);

  async function handleMarkIssued(id: string) {
    try {
      await api.post(`/sales-invoices/${id}/mark-issued`, { so_hoa_don: soHoaDon, ky_hieu: kyHieu });
      setMarkingId(null);
      setSoHoaDon("");
      setKyHieu("");
      showToast("success", "Đã cập nhật số hoá đơn.");
      loadData();
    } catch (err) {
      showToast("error", err instanceof ApiError ? err.message : "Không cập nhật được");
    }
  }

  async function handleMarkPaid(id: string) {
    try {
      await api.post(`/sales-invoices/${id}/mark-paid`);
      showToast("success", "Đã đánh dấu thu tiền.");
      loadData();
    } catch (err) {
      showToast("error", err instanceof ApiError ? err.message : "Không cập nhật được");
    }
  }

  return (
    <div>

      <div className="page-header">
        <div>
          <div className="page-header__eyebrow">Bán ra · ghi nhận nội bộ</div>
          <h1>Hoá đơn bán ra</h1>
        </div>
        <button className="btn btn--primary" onClick={() => setShowForm((v) => !v)}>
          {showForm ? "Đóng" : "+ Tạo hoá đơn"}
        </button>
      </div>

      <div className="banner banner--info">
        Đây chỉ là bản ghi nội bộ để theo dõi/đối chiếu — hoá đơn GTGT hợp lệ về pháp lý
        vẫn phải phát hành qua phần mềm hoá đơn điện tử đang dùng. Sau khi xuất hoá đơn thật,
        quay lại đây bấm "Đã xuất hoá đơn" để nhập số/ký hiệu thật, dùng đối chiếu.
      </div>

      {error && <div className="banner banner--error">{error}</div>}

      {showForm && (
        <SalesInvoiceCreateForm
          customers={customers}
          onCreated={() => {
            setShowForm(false);
            loadData();
          }}
          onError={(msg) => showToast("error", msg)}
        />
      )}

      <div className="card">
        {loading ? (
          <p>Đang tải…</p>
        ) : invoices.length === 0 ? (
          <div className="empty-state">Chưa có hoá đơn bán ra nào.</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Ngày</th>
                <th>Khách hàng</th>
                <th>Hàng hoá</th>
                <th>SL</th>
                <th>Đơn giá</th>
                <th>Tổng tiền</th>
                <th>Số HĐ / Ký hiệu</th>
                <th>Trạng thái</th>
                <th>Công nợ</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {invoices.map((inv) => (
                <tr key={inv.id}>
                  <td>{formatDate(inv.ngay)}</td>
                  <td>{customerById[inv.customer_id] || "—"}</td>
                  <td>{inv.ten_hang}</td>
                  <td className="num">{Number(inv.so_luong).toLocaleString("vi-VN")}</td>
                  <td className="num">{Number(inv.don_gia).toLocaleString("vi-VN")}</td>
                  <td className="num">{Number(inv.tong_tien).toLocaleString("vi-VN")} đ</td>
                  <td className="num">{inv.so_hoa_don ? `${inv.so_hoa_don} / ${inv.ky_hieu}` : "—"}</td>
                  <td>
                    <span className={`status-seal status-seal--${inv.trang_thai === "draft" ? "draft" : "signed"}`}>
                      {SALES_INVOICE_STATUS_LABEL[inv.trang_thai]}
                    </span>
                  </td>
                  <td>
                    {inv.trang_thai !== "draft" &&
                      (inv.paid_at ? (
                        <span className="status-seal status-seal--signed">Đã thu tiền</span>
                      ) : (
                        <button className="btn btn--ghost" onClick={() => handleMarkPaid(inv.id)}>
                          Đánh dấu đã thu
                        </button>
                      ))}
                  </td>
                  <td>
                    {inv.trang_thai === "draft" &&
                      (markingId === inv.id ? (
                        <div style={{ display: "flex", gap: 6 }}>
                          <input
                            placeholder="Số HĐ"
                            value={soHoaDon}
                            onChange={(e) => setSoHoaDon(e.target.value)}
                            style={{ width: 90, padding: "5px 8px", border: "1px solid var(--color-rule)", borderRadius: 4 }}
                          />
                          <input
                            placeholder="Ký hiệu"
                            value={kyHieu}
                            onChange={(e) => setKyHieu(e.target.value)}
                            style={{ width: 90, padding: "5px 8px", border: "1px solid var(--color-rule)", borderRadius: 4 }}
                          />
                          <button
                            className="btn btn--accent"
                            onClick={() => handleMarkIssued(inv.id)}
                            disabled={!soHoaDon.trim() || !kyHieu.trim()}
                          >
                            Lưu
                          </button>
                        </div>
                      ) : (
                        <button className="btn btn--ghost" onClick={() => setMarkingId(inv.id)}>
                          Đã xuất hoá đơn
                        </button>
                      ))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

function SalesInvoiceCreateForm({
  customers,
  onCreated,
  onError,
}: {
  customers: Customer[];
  onCreated: () => void;
  onError: (msg: string) => void;
}) {
  const [customerId, setCustomerId] = useState("");
  const [ngay, setNgay] = useState(() => new Date().toISOString().slice(0, 10));
  const [tenHang, setTenHang] = useState("Mủ cao su nguyên liệu tạp");
  const [soLuong, setSoLuong] = useState("");
  const [donGia, setDonGia] = useState("");
  const [thueSuat, setThueSuat] = useState("KKKNT");
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>("chuyen_khoan");
  const [submitting, setSubmitting] = useState(false);

  const tongTien = (() => {
    const q = parseFloat(soLuong);
    const p = parseFloat(donGia);
    return !isNaN(q) && !isNaN(p) ? q * p : null;
  })();

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      await api.post("/sales-invoices/", {
        ngay,
        customer_id: customerId,
        ten_hang: tenHang,
        so_luong: Number(soLuong),
        don_gia: Number(donGia),
        thue_suat: thueSuat,
        payment_method: paymentMethod,
      });
      onCreated();
    } catch (err) {
      onError(err instanceof ApiError ? err.message : "Không tạo được hoá đơn");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="card" style={{ marginBottom: 24 }}>
      <h3>Hoá đơn bán ra mới</h3>
      {customers.length === 0 ? (
        <p style={{ color: "var(--color-ink-soft)" }}>Chưa có khách hàng nào — hãy sang mục "Khách hàng" để thêm trước.</p>
      ) : (
        <form onSubmit={handleSubmit} className="form-grid">
          <div className="field">
            <label>Khách hàng *</label>
            <select value={customerId} onChange={(e) => setCustomerId(e.target.value)} required>
              <option value="">— Chọn khách hàng —</option>
              {customers.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.company_name}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label>Ngày *</label>
            <input type="date" value={ngay} onChange={(e) => setNgay(e.target.value)} required />
          </div>
          <div className="field">
            <label>Tên hàng hoá *</label>
            <input value={tenHang} onChange={(e) => setTenHang(e.target.value)} required />
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <div className="field">
              <label>Số lượng (kg) *</label>
              <input value={soLuong} onChange={(e) => setSoLuong(e.target.value)} required />
            </div>
            <div className="field">
              <label>Đơn giá *</label>
              <input value={donGia} onChange={(e) => setDonGia(e.target.value)} required />
            </div>
          </div>
          {tongTien !== null && (
            <div className="banner banner--info num">Tổng tiền: {tongTien.toLocaleString("vi-VN")} đ</div>
          )}
          <div className="field">
            <label>Thuế suất</label>
            <select value={thueSuat} onChange={(e) => setThueSuat(e.target.value)}>
              <option value="KKKNT">KKKNT (không kê khai, không tính thuế)</option>
              <option value="0%">0%</option>
              <option value="5%">5%</option>
              <option value="8%">8%</option>
              <option value="10%">10%</option>
            </select>
          </div>
          <div className="field">
            <label>Hình thức thanh toán</label>
            <select value={paymentMethod} onChange={(e) => setPaymentMethod(e.target.value as PaymentMethod)}>
              <option value="chuyen_khoan">Chuyển khoản</option>
              <option value="tien_mat">Tiền mặt</option>
            </select>
          </div>
          <button className="btn btn--primary" type="submit" disabled={submitting}>
            {submitting ? "Đang lưu…" : "Lưu hoá đơn (nháp)"}
          </button>
        </form>
      )}
    </div>
  );
}

function formatDate(iso: string): string {
  const [y, m, d] = iso.split("-");
  return `${d}/${m}/${y}`;
}
