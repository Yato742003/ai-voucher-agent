import { useEffect, useMemo, useState, type FormEvent } from "react";
import { api, ApiError, downloadFile } from "../api/client";
import type { Seller, Voucher } from "../api/types";
import { StatusSeal } from "../components/StatusSeal";
import { SearchableSelect } from "../components/SearchableSelect";
import { useAuth } from "../contexts/AuthContext";
import { useToast } from "../contexts/ToastContext";

function currentMonthYear() {
  const now = new Date();
  return { month: now.getMonth() + 1, year: now.getFullYear() };
}

export function VouchersPage() {
  const { user } = useAuth();
  const { showToast } = useToast();
  const isGiamDoc = user?.role_name === "giam_doc";

  const { month: curMonth, year: curYear } = currentMonthYear();
  const [month, setMonth] = useState(curMonth);
  const [year, setYear] = useState(curYear);
  const [query, setQuery] = useState("");
  const [vouchers, setVouchers] = useState<Voucher[]>([]);
  const [sellers, setSellers] = useState<Seller[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [voidingId, setVoidingId] = useState<string | null>(null);
  const [voidReason, setVoidReason] = useState("");
  const [uploadingId, setUploadingId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const [showImport, setShowImport] = useState(false);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<{
    file: string;
    total: number;
    imported: number;
    skipped_existing: number;
    skipped_no_name: number;
    sellers_created: number;
  } | null>(null);
  const [importError, setImportError] = useState<string | null>(null);
  const [editingVoucher, setEditingVoucher] = useState<Voucher | null>(null);

  const sellerById = useMemo(() => Object.fromEntries(sellers.map((s) => [s.id, s.name])), [sellers]);

  function loadData() {
    setLoading(true);
    setError(null);
    Promise.all([api.get<Voucher[]>(`/vouchers/?month=${month}&year=${year}`), api.get<Seller[]>("/sellers/")])
      .then(([v, s]) => {
        setVouchers(v);
        setSellers(s);
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : "Không tải được dữ liệu"))
      .finally(() => setLoading(false));
  }

  useEffect(loadData, [month, year]);

  const filteredVouchers = useMemo(() => {
    if (!query.trim()) return vouchers;
    const q = query.toLowerCase();
    return vouchers.filter(
      (v) =>
        v.ly_do_chi.toLowerCase().includes(q) ||
        v.so_phieu.toLowerCase().includes(q) ||
        (sellerById[v.seller_id] || "").toLowerCase().includes(q)
    );
  }, [vouchers, query, sellerById]);

  async function handleApprove(id: string) {
    try {
      await api.post(`/vouchers/${id}/approve`);
      showToast("success", "Đã duyệt phiếu.");
      loadData();
    } catch (err) {
      showToast("error", err instanceof ApiError ? err.message : "Không duyệt được phiếu");
    }
  }

  async function handleVoid(id: string) {
    try {
      await api.post(`/vouchers/${id}/void`, { ly_do_huy: voidReason });
      setVoidingId(null);
      setVoidReason("");
      showToast("success", "Đã huỷ phiếu.");
      loadData();
    } catch (err) {
      showToast("error", err instanceof ApiError ? err.message : "Không huỷ được phiếu");
    }
  }

  async function handleDelete(id: string, soPhieu: string) {
    if (!confirm(`Bạn có chắc chắn muốn xoá phiếu chi ${soPhieu}? Hành động này sẽ xoá hẳn phiếu khỏi hệ thống.`)) {
      return;
    }
    setDeletingId(id);
    try {
      await api.delete(`/vouchers/${id}`);
      showToast("success", `Đã xoá phiếu chi ${soPhieu}.`);
      loadData();
    } catch (err) {
      showToast("error", err instanceof ApiError ? err.message : "Không xoá được phiếu");
    } finally {
      setDeletingId(null);
    }
  }

  async function handleUploadSignedScan(id: string, file: File) {
    setUploadingId(id);
    try {
      const formData = new FormData();
      formData.append("file", file);
      await api.post(`/vouchers/${id}/signed-scan`, formData);
      showToast("success", "Đã lưu ảnh phiếu đã ký.");
      loadData();
    } catch (err) {
      showToast(
        "error",
        err instanceof ApiError ? err.message : "Không upload được ảnh — kiểm tra định dạng file (.jpg/.png/.pdf/.webp)"
      );
    } finally {
      setUploadingId(null);
    }
  }

  const totalAmount = filteredVouchers.filter((v) => v.trang_thai !== "void").reduce((sum, v) => sum + Number(v.so_tien), 0);

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-header__eyebrow">Chứng từ</div>
          <h1>Phiếu chi</h1>
        </div>
        <div style={{ display: "flex", gap: 10 }}>
          <button className="btn btn--ghost" onClick={() => { setShowImport((v) => !v); setShowForm(false); }}>
            {showImport ? "Đóng Excel" : "📥 Nhập từ Excel"}
          </button>
          <button className="btn btn--primary" onClick={() => { setShowForm((v) => !v); setShowImport(false); }}>
            {showForm ? "Đóng" : "+ Tạo phiếu chi"}
          </button>
        </div>
      </div>

      {error && <div className="banner banner--error">{error}</div>}

      {showImport && (
        <div className="card" style={{ marginBottom: 24, padding: 20 }}>
          <h3 style={{ margin: "0 0 8px" }}>Nhập phiếu chi từ Excel</h3>
          <p style={{ fontSize: "0.88rem", color: "var(--color-ink-soft)", marginBottom: 16, marginTop: 0 }}>
            Chọn file Excel (.xlsx, .xlsm) chứa lịch sử phiếu chi của bạn. Hệ thống sẽ tự động phân tích và import các phiếu chưa tồn tại.
          </p>

          {!importing && !importResult && (
            <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
              <input
                type="file"
                accept=".xlsx,.xlsm"
                onChange={async (e) => {
                  const file = e.target.files?.[0];
                  if (!file) return;
                  setImporting(true);
                  setImportError(null);
                  setImportResult(null);

                  try {
                    const formData = new FormData();
                    formData.append("file", file);
                    const res = await api.post<{
                      file: string;
                      total: number;
                      imported: number;
                      skipped_existing: number;
                      skipped_no_name: number;
                      sellers_created: number;
                    }>("/vouchers/import-excel", formData);
                    setImportResult(res);
                    showToast("success", `Tải xong: ${res.imported}/${res.total} phiếu!`);
                    loadData();
                  } catch (err) {
                    setImportError(err instanceof ApiError ? err.message : "Có lỗi xảy ra khi tải file");
                  } finally {
                    setImporting(false);
                    e.target.value = "";
                  }
                }}
              />
            </div>
          )}

          {importing && (
            <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 0" }}>
              <div style={{ width: 18, height: 18, border: "2px solid var(--color-primary)", borderTopColor: "transparent", borderRadius: "50%", animation: "scan-spin 0.8s linear infinite" }} />
              <span style={{ fontSize: "0.9rem" }}>Đang phân tích và import dữ liệu Excel…</span>
            </div>
          )}

          {importError && (
            <div className="banner banner--error" style={{ margin: "10px 0 0" }}>
              {importError}
            </div>
          )}

          {importResult && (
            <div style={{ marginTop: 12, padding: 12, background: "var(--color-primary-soft)", borderRadius: "var(--radius-sm)", fontSize: "0.9rem" }}>
              <div style={{ fontWeight: 600, marginBottom: 8, color: "var(--color-ink)" }}>Kết quả import từ file: {importResult.file}</div>
              <ul style={{ margin: 0, paddingLeft: 20, color: "var(--color-ink-soft)", lineHeight: 1.6 }}>
                <li>Tổng số phiếu quét thấy: <strong>{importResult.total}</strong></li>
                <li style={{ color: "var(--color-status-signed)" }}>Số phiếu đã import thành công: <strong>{importResult.imported}</strong></li>
                <li>Số phiếu trùng (bỏ qua): <strong>{importResult.skipped_existing}</strong></li>
                {importResult.skipped_no_name > 0 && <li style={{ color: "var(--color-status-void)" }}>Số phiếu thiếu tên/dữ liệu bắt buộc (bỏ qua): <strong>{importResult.skipped_no_name}</strong></li>}
                <li>Số người bán mới được tạo: <strong>{importResult.sellers_created}</strong></li>
              </ul>
              <button className="btn btn--ghost" style={{ marginTop: 12, fontSize: "0.8rem", padding: "4px 10px" }} onClick={() => setImportResult(null)}>
                Chọn file khác
              </button>
            </div>
          )}
        </div>
      )}

      {showForm && (
        <VoucherCreateForm
          sellers={sellers}
          onCreated={() => {
            setShowForm(false);
            showToast("success", "Đã tạo phiếu chi (nháp).");
            loadData();
          }}
          onError={(msg) => showToast("error", msg)}
        />
      )}

      {editingVoucher && (
        <VoucherEditForm
          voucher={editingVoucher}
          sellers={sellers}
          onUpdated={() => {
            setEditingVoucher(null);
            showToast("success", "Đã cập nhật phiếu chi.");
            loadData();
          }}
          onCancel={() => setEditingVoucher(null)}
          onError={(msg) => showToast("error", msg)}
        />
      )}

      <div className="toolbar">
        <div className="field" style={{ margin: 0 }}>
          <label>Tháng</label>
          <select value={month} onChange={(e) => setMonth(Number(e.target.value))}>
            {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
              <option key={m} value={m}>
                Tháng {m}
              </option>
            ))}
          </select>
        </div>
        <div className="field" style={{ margin: 0 }}>
          <label>Năm</label>
          <input type="number" value={year} onChange={(e) => setYear(Number(e.target.value))} style={{ width: 90 }} />
        </div>
        <div className="field" style={{ margin: 0, flex: 1, minWidth: 180 }}>
          <label>Tìm kiếm</label>
          <input
            placeholder="Tìm theo số phiếu, người bán, lý do chi…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
      </div>

      <div className="card">
        {loading ? (
          <p>Đang tải…</p>
        ) : filteredVouchers.length === 0 ? (
          <div className="empty-state">
            {vouchers.length === 0 ? "Chưa có phiếu chi nào trong kỳ này." : "Không tìm thấy phiếu nào khớp với tìm kiếm."}
          </div>
        ) : (
          <>
            <table>
              <thead>
                <tr>
                  <th>Số phiếu</th>
                  <th>Ngày</th>
                  <th>Người bán</th>
                  <th>Lý do chi</th>
                  <th>Số tiền</th>
                  <th>Trạng thái</th>
                  <th>Thao tác</th>
                </tr>
              </thead>
              <tbody>
                {filteredVouchers.map((v) => (
                  <tr key={v.id}>
                    <td className="num">{v.so_phieu}</td>
                    <td>{formatDate(v.ngay)}</td>
                    <td>{sellerById[v.seller_id] || "—"}</td>
                    <td>
                      {v.ly_do_chi}
                      {v.ghi_chu_chat_luong && (
                        <div style={{ fontSize: "0.78rem", color: "var(--color-ink-soft)" }}>{v.ghi_chu_chat_luong}</div>
                      )}
                    </td>
                    <td className="num">{formatMoney(v.so_tien)}</td>
                    <td>
                      <StatusSeal status={v.trang_thai} />
                    </td>
                    <td>
                      {v.trang_thai === "draft" && (
                        <div style={{ display: "flex", gap: 8 }}>
                          <button className="btn btn--ghost" onClick={() => { setEditingVoucher(v); setShowForm(false); setShowImport(false); }}>
                            Sửa
                          </button>
                          {isGiamDoc && (
                            <>
                              <button className="btn btn--ghost" onClick={() => handleApprove(v.id)}>
                                Duyệt
                              </button>
                              <button className="btn btn--danger" onClick={() => setVoidingId(v.id)}>
                                Huỷ
                              </button>
                            </>
                          )}
                          <button
                            className="btn btn--ghost"
                            style={{ color: "var(--color-status-void)" }}
                            disabled={deletingId === v.id}
                            onClick={() => handleDelete(v.id, v.so_phieu)}
                          >
                            {deletingId === v.id ? "Đang xoá…" : "Xoá"}
                          </button>
                        </div>
                      )}

                      {v.trang_thai === "pending_signature" && (
                        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                          <label className="btn btn--accent" style={{ cursor: "pointer" }}>
                            {uploadingId === v.id ? "Đang tải…" : "Upload ảnh đã ký"}
                            <input
                              type="file"
                              accept=".jpg,.jpeg,.png,.pdf,.webp"
                              style={{ display: "none" }}
                              disabled={uploadingId !== null}
                              onChange={(e) => {
                                const file = e.target.files?.[0];
                                if (file) handleUploadSignedScan(v.id, file);
                                e.target.value = "";
                              }}
                            />
                          </label>
                          {isGiamDoc && (
                            <button
                              className="btn btn--ghost"
                              style={{ color: "var(--color-status-void)" }}
                              disabled={deletingId === v.id}
                              onClick={() => handleDelete(v.id, v.so_phieu)}
                            >
                              {deletingId === v.id ? "Đang xoá…" : "Xoá"}
                            </button>
                          )}
                        </div>
                      )}

                      {v.trang_thai === "signed" && (
                        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                          <button
                            className="btn btn--ghost"
                            onClick={() => downloadFile(`/vouchers/${v.id}/signed-scan`, `PhieuDaKy_${v.so_phieu.replace('/', '-')}.jpg`)}
                          >
                            👁 Xem ảnh ký
                          </button>
                          {isGiamDoc && (
                            <button
                              className="btn btn--ghost"
                              style={{ color: "var(--color-status-void)" }}
                              disabled={deletingId === v.id}
                              onClick={() => handleDelete(v.id, v.so_phieu)}
                            >
                              {deletingId === v.id ? "Đang xoá…" : "Xoá"}
                            </button>
                          )}
                        </div>
                      )}

                      {v.trang_thai === "void" && isGiamDoc && (
                        <button
                          className="btn btn--ghost"
                          style={{ color: "var(--color-status-void)" }}
                          disabled={deletingId === v.id}
                          onClick={() => handleDelete(v.id, v.so_phieu)}
                        >
                          {deletingId === v.id ? "Đang xoá…" : "Xoá"}
                        </button>
                      )}

                      {voidingId === v.id && (
                        <div style={{ marginTop: 8, display: "flex", gap: 6 }}>
                          <input
                            placeholder="Lý do huỷ…"
                            value={voidReason}
                            onChange={(e) => setVoidReason(e.target.value)}
                            style={{ width: 160, padding: "5px 8px", border: "1px solid var(--color-rule)", borderRadius: 4 }}
                          />
                          <button className="btn btn--danger" onClick={() => handleVoid(v.id)} disabled={!voidReason.trim()}>
                            Xác nhận
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div style={{ marginTop: 14, textAlign: "right", fontWeight: 600 }} className="num">
              Tổng (không tính phiếu huỷ): {formatMoney(String(totalAmount))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function VoucherCreateForm({
  sellers,
  onCreated,
  onError,
}: {
  sellers: Seller[];
  onCreated: () => void;
  onError: (msg: string) => void;
}) {
  const [sellerId, setSellerId] = useState("");
  const [ngay, setNgay] = useState(() => new Date().toISOString().slice(0, 10));
  const [lyDoChi, setLyDoChi] = useState("");
  const [soTien, setSoTien] = useState("");
  const [soLuong, setSoLuong] = useState("");
  const [donGia, setDonGia] = useState("");
  const [ghiChuChatLuong, setGhiChuChatLuong] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const sellerOptions = sellers.map((s) => ({ value: s.id, label: s.name }));

  // Tự tính số tiền = số lượng * đơn giá nếu người dùng điền cả 2 (có thể sửa tay lại nếu khác)
  function handleQtyOrPriceChange(qty: string, price: string) {
    setSoLuong(qty);
    setDonGia(price);
    const q = parseFloat(qty);
    const p = parseFloat(price);
    if (!isNaN(q) && !isNaN(p)) setSoTien(String(q * p));
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      await api.post("/vouchers/", {
        ngay,
        seller_id: sellerId,
        ly_do_chi: lyDoChi,
        so_tien: Number(soTien),
        so_luong: soLuong ? Number(soLuong) : null,
        don_gia: donGia ? Number(donGia) : null,
        ghi_chu_chat_luong: ghiChuChatLuong || null,
      });
      onCreated();
    } catch (err) {
      onError(err instanceof ApiError ? err.message : "Không tạo được phiếu chi");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="card" style={{ marginBottom: 24 }}>
      <h3>Phiếu chi mới</h3>
      {sellers.length === 0 ? (
        <p style={{ color: "var(--color-ink-soft)" }}>
          Chưa có người bán nào — hãy sang mục "Người bán" để thêm trước.
        </p>
      ) : (
        <form onSubmit={handleSubmit} className="form-grid">
          <div className="field">
            <label>Người bán *</label>
            <SearchableSelect
              options={sellerOptions}
              value={sellerId}
              onChange={setSellerId}
              placeholder="Gõ để tìm người bán…"
              required
            />
          </div>
          <div className="field">
            <label>Ngày *</label>
            <input type="date" value={ngay} onChange={(e) => setNgay(e.target.value)} required />
          </div>
          <div className="field">
            <label>Lý do chi *</label>
            <input value={lyDoChi} onChange={(e) => setLyDoChi(e.target.value)} placeholder="VD: Mua mủ cao su nước" required />
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <div className="field">
              <label>Số lượng (kg)</label>
              <input value={soLuong} onChange={(e) => handleQtyOrPriceChange(e.target.value, donGia)} />
            </div>
            <div className="field">
              <label>Đơn giá</label>
              <input value={donGia} onChange={(e) => handleQtyOrPriceChange(soLuong, e.target.value)} />
            </div>
          </div>
          <div className="field">
            <label>Số tiền (đồng) *</label>
            <input value={soTien} onChange={(e) => setSoTien(e.target.value)} required />
          </div>
          <div className="field">
            <label>Ghi chú chất lượng (nếu có)</label>
            <input
              value={ghiChuChatLuong}
              onChange={(e) => setGhiChuChatLuong(e.target.value)}
              placeholder="VD: độ ẩm 8%, tạp chất 2%, trọng lượng xe 1.2 tấn…"
            />
          </div>
          <button className="btn btn--primary" type="submit" disabled={submitting}>
            {submitting ? "Đang lưu…" : "Lưu phiếu chi (nháp)"}
          </button>
        </form>
      )}
    </div>
  );
}

function formatMoney(value: string): string {
  const n = Number(value);
  return n.toLocaleString("vi-VN") + " đ";
}

function formatDate(iso: string): string {
  const [y, m, d] = iso.split("-");
  return `${d}/${m}/${y}`;
}


function VoucherEditForm({
  voucher,
  sellers,
  onUpdated,
  onCancel,
  onError,
}: {
  voucher: Voucher;
  sellers: Seller[];
  onUpdated: () => void;
  onCancel: () => void;
  onError: (msg: string) => void;
}) {
  const [sellerId, setSellerId] = useState(voucher.seller_id);
  const [ngay, setNgay] = useState(voucher.ngay);
  const [lyDoChi, setLyDoChi] = useState(voucher.ly_do_chi);
  const [soTien, setSoTien] = useState(String(voucher.so_tien));
  const [soLuong, setSoLuong] = useState(voucher.so_luong !== null ? String(voucher.so_luong) : "");
  const [donGia, setDonGia] = useState(voucher.don_gia !== null ? String(voucher.don_gia) : "");
  const [ghiChuChatLuong, setGhiChuChatLuong] = useState(voucher.ghi_chu_chat_luong || "");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (soLuong && donGia) {
      const q = parseFloat(soLuong);
      const p = parseFloat(donGia);
      if (!isNaN(q) && !isNaN(p)) {
        setSoTien(String(q * p));
      }
    }
  }, [soLuong, donGia]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!sellerId) return onError("Vui lòng chọn người bán");
    if (!lyDoChi.trim()) return onError("Vui lòng nhập lý do chi");
    const numTien = parseFloat(soTien);
    if (isNaN(numTien) || numTien <= 0) return onError("Số tiền phải lớn hơn 0");

    setSubmitting(true);
    try {
      await api.patch(`/vouchers/${voucher.id}`, {
        seller_id: sellerId,
        ngay,
        ly_do_chi: lyDoChi,
        so_tien: numTien,
        so_luong: soLuong ? parseFloat(soLuong) : null,
        don_gia: donGia ? parseFloat(donGia) : null,
        ghi_chu_chat_luong: ghiChuChatLuong || null,
      });
      onUpdated();
    } catch (err) {
      onError(err instanceof ApiError ? err.message : "Không cập nhật được chứng từ");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="card" style={{ marginBottom: 24, padding: 20 }}>
      <h3 style={{ margin: "0 0 16px" }}>Sửa phiếu chi {voucher.so_phieu}</h3>
      <form onSubmit={handleSubmit} style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <div className="field">
          <label>Người bán *</label>
          <SearchableSelect
            options={sellers.map((s) => ({ value: s.id, label: s.name }))}
            value={sellerId}
            onChange={setSellerId}
            placeholder="Chọn người bán…"
          />
        </div>
        <div className="field">
          <label>Ngày chi *</label>
          <input type="date" value={ngay} onChange={(e) => setNgay(e.target.value)} required />
        </div>
        <div className="field" style={{ gridColumn: "1 / -1" }}>
          <label>Lý do chi *</label>
          <input value={lyDoChi} onChange={(e) => setLyDoChi(e.target.value)} required placeholder="Mủ cao su nước, ứng tiền..." />
        </div>
        <div className="field">
          <label>Số lượng (tùy chọn)</label>
          <input type="number" step="any" value={soLuong} onChange={(e) => setSoLuong(e.target.value)} placeholder="Tấn, kg..." />
        </div>
        <div className="field">
          <label>Đơn giá (tùy chọn)</label>
          <input type="number" step="any" value={donGia} onChange={(e) => setDonGia(e.target.value)} placeholder="Giá mỗi đơn vị..." />
        </div>
        <div className="field">
          <label>Số tiền (đồng) *</label>
          <input type="number" step="any" value={soTien} onChange={(e) => setSoTien(e.target.value)} required />
        </div>
        <div className="field">
          <label>Ghi chú chất lượng (tùy chọn)</label>
          <input value={ghiChuChatLuong} onChange={(e) => setGhiChuChatLuong(e.target.value)} placeholder="VD: độ ẩm 8%, tạp chất 2%..." />
        </div>
        <div style={{ gridColumn: "1 / -1", display: "flex", gap: 10, justifyContent: "flex-end", marginTop: 8 }}>
          <button type="button" className="btn btn--ghost" onClick={onCancel}>Huỷ</button>
          <button type="submit" className="btn btn--primary" disabled={submitting}>
            {submitting ? "Đang lưu..." : "Lưu thay đổi"}
          </button>
        </div>
      </form>
    </div>
  );
}
