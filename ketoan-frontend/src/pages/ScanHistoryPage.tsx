import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type { ExtractedRow, ScanConfirmResponse, ScanImportDetail, ScanImportListItem, Seller } from "../api/types";
import { SearchableSelect } from "../components/SearchableSelect";
import { useToast } from "../contexts/ToastContext";

interface EditableRow extends ExtractedRow {
  seller_id: string | null;
}

// ── Nhãn trạng thái ──────────────────────────────────────────────────────────
const STATUS_LABEL: Record<ScanImportListItem["status"], string> = {
  pending:   "Chờ xác nhận",
  confirmed: "Đã xác nhận",
  discarded: "Đã huỷ",
};

const STATUS_CLASS: Record<ScanImportListItem["status"], string> = {
  pending:   "status-seal--pending_signature",
  confirmed: "status-seal--signed",
  discarded: "status-seal--void",
};

// ── Component thumbnail (fetch ảnh với auth, tạo blob URL) ───────────────────
function ScanThumbnail({ scanId }: { scanId: string }) {
  const [src, setSrc] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let blobUrl: string | null = null;
    api.get<Blob>(`/scans/${scanId}/image`)
      .then((blob) => {
        blobUrl = URL.createObjectURL(blob);
        setSrc(blobUrl);
      })
      .catch(() => setFailed(true));
    return () => {
      if (blobUrl) URL.revokeObjectURL(blobUrl);
    };
  }, [scanId]);

  if (failed) {
    return (
      <div style={{
        width: "100%", aspectRatio: "3/4", background: "var(--color-paper)",
        border: "1px solid var(--color-rule)", borderRadius: 4,
        display: "flex", alignItems: "center", justifyContent: "center",
        fontSize: "1.5rem", color: "var(--color-ink-soft)",
      }}>
        📷
      </div>
    );
  }

  if (!src) {
    return (
      <div style={{
        width: "100%", aspectRatio: "3/4", background: "var(--color-paper)",
        border: "1px dashed var(--color-rule)", borderRadius: 4,
        display: "flex", alignItems: "center", justifyContent: "center",
        fontSize: "0.8rem", color: "var(--color-ink-soft)",
        animation: "pulse 1.5s ease-in-out infinite",
      }}>
        Đang tải…
      </div>
    );
  }

  return (
    <img
      src={src}
      alt="Bảng kê"
      style={{
        width: "100%",
        borderRadius: 4,
        border: "1px solid var(--color-rule)",
        display: "block",
        objectFit: "cover",
        aspectRatio: "3/4",
      }}
    />
  );
}

// ── Modal chi tiết ────────────────────────────────────────────────────────────
function DetailModal({ scanId, onClose, onRefresh }: { scanId: string; onClose: () => void; onRefresh?: () => void }) {
  const [detail, setDetail] = useState<ScanImportDetail | null>(null);
  const [imgSrc, setImgSrc] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [discarding, setDiscarding] = useState(false);

  const [sellers, setSellers] = useState<Seller[]>([]);
  const [rows, setRows] = useState<EditableRow[]>([]);
  const [ngay, setNgay] = useState(() => new Date().toISOString().slice(0, 10));
  const [confirming, setConfirming] = useState(false);
  const [confirmError, setConfirmError] = useState<string | null>(null);
  const [imgZoomed, setImgZoomed] = useState(false);

  const { showToast } = useToast();
  const navigate = useNavigate();

  useEffect(() => {
    let blobUrl: string | null = null;

    Promise.all([
      api.get<ScanImportDetail>(`/scans/${scanId}`),
      api.get<Blob>(`/scans/${scanId}/image`),
      api.get<Seller[]>("/sellers/"),
    ]).then(([det, blob, sList]) => {
      setDetail(det);
      setSellers(sList);
      const rawList = (det.confirmed_extraction ?? det.raw_extraction ?? []) as unknown as Array<ExtractedRow & { seller_id?: string | null }>;
      const initialRows: EditableRow[] = rawList.map((r) => ({
        ten_nguoi_ban: r.ten_nguoi_ban ?? "",
        ten_hang_hoa: r.ten_hang_hoa ?? null,
        so_luong: Number(r.so_luong ?? 0),
        don_gia: Number(r.don_gia ?? 0),
        tong_gia_thanh_toan: Number(r.tong_gia_thanh_toan ?? 0),
        do_tin_cay_thap: Boolean(r.do_tin_cay_thap),
        canh_bao_phep_nhan: Boolean(r.canh_bao_phep_nhan),
        canh_bao_ten_khong_khop: Boolean(r.canh_bao_ten_khong_khop),
        seller_id_goi_y: r.seller_id_goi_y ?? null,
        seller_id: r.seller_id ?? r.seller_id_goi_y ?? null,
      }));
      setRows(initialRows);
      setNgay(new Date(det.created_at).toISOString().slice(0, 10));
      blobUrl = URL.createObjectURL(blob);
      setImgSrc(blobUrl);
    }).catch(() => {}).finally(() => setLoading(false));

    return () => {
      if (blobUrl) URL.revokeObjectURL(blobUrl);
    };
  }, [scanId]);

  const handleDiscard = async () => {
    if (!confirm("Bạn có chắc chắn muốn huỷ lượt scan này? Trạng thái sẽ chuyển thành Đã huỷ.")) return;
    setDiscarding(true);
    try {
      await api.post(`/scans/${scanId}/discard`);
      showToast("success", "Đã huỷ lượt scan.");
      if (onRefresh) onRefresh();
      onClose();
    } catch (err) {
      showToast("error", "Không huỷ được lượt scan: " + (err instanceof Error ? err.message : String(err)));
    } finally {
      setDiscarding(false);
    }
  };

  function updateRow(i: number, patch: Partial<EditableRow>) {
    setRows((prev) => prev.map((r, j) => (j === i ? { ...r, ...patch } : r)));
  }
  function removeRow(i: number) {
    setRows((prev) => prev.filter((_, j) => j !== i));
  }

  async function handleConfirm() {
    if (rows.length === 0) return;
    setConfirming(true);
    setConfirmError(null);
    try {
      const result = await api.post<ScanConfirmResponse>(`/scans/${scanId}/confirm`, {
        rows: rows.map((r) => ({
          ten_nguoi_ban: r.ten_nguoi_ban, seller_id: r.seller_id,
          ten_hang_hoa: r.ten_hang_hoa, so_luong: r.so_luong,
          don_gia: r.don_gia, tong_gia_thanh_toan: r.tong_gia_thanh_toan, ngay,
        })),
      });
      showToast("success", `Đã xác nhận và tạo ${result.so_phieu_da_tao} phiếu chi nháp!`);
      if (onRefresh) onRefresh();
      onClose();
      navigate("/vouchers");
    } catch (err) {
      setConfirmError(err instanceof ApiError ? err.message : "Không xác nhận được lượt scan");
      showToast("error", err instanceof ApiError ? err.message : "Không xác nhận được lượt scan");
    } finally {
      setConfirming(false);
    }
  }

  // Đóng khi click backdrop
  function handleBackdropClick(e: React.MouseEvent<HTMLDivElement>) {
    if (e.target === e.currentTarget) onClose();
  }

  // Đóng khi nhấn Esc
  useEffect(() => {
    function handler(e: KeyboardEvent) { if (e.key === "Escape") onClose(); }
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  const isPending = detail?.status === "pending";
  const isConfirmed = detail?.status === "confirmed";
  const sellerOptions = sellers.map((s) => ({ value: s.id, label: s.name }));

  return (
    <div
      onClick={handleBackdropClick}
      style={{
        position: "fixed", inset: 0, zIndex: 200,
        background: "rgba(35,34,32,0.55)", backdropFilter: "blur(2px)",
        display: "flex", alignItems: "center", justifyContent: "center",
        padding: 24,
      }}
    >
      <div
        style={{
          background: "var(--color-paper-raised)",
          borderRadius: "var(--radius-md)",
          border: "1px solid var(--color-rule)",
          boxShadow: "0 16px 48px rgba(35,34,32,0.22)",
          width: "min(1250px, 98vw)",
          maxHeight: "92vh",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
        }}
      >
        {/* Header modal */}
        <div style={{
          display: "flex", alignItems: "center", justifyContent: "space-between",
          padding: "16px 20px", borderBottom: "1px solid var(--color-rule)", flexShrink: 0,
        }}>
          <div>
            <div style={{ fontSize: "0.72rem", textTransform: "uppercase", letterSpacing: "0.07em", color: "var(--color-ink-soft)", marginBottom: 2 }}>
              Chi tiết lượt scan
            </div>
            {detail && (
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <span style={{ fontFamily: "var(--font-display)", fontWeight: 600 }}>
                  {new Date(detail.created_at).toLocaleString("vi-VN")}
                </span>
                <span className={`status-seal ${STATUS_CLASS[detail.status]}`}>
                  {STATUS_LABEL[detail.status]}
                </span>
              </div>
            )}
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            {isPending && (
              <button
                className="btn btn--ghost"
                style={{ padding: "6px 12px", borderColor: "var(--color-status-void)", color: "var(--color-status-void)" }}
                onClick={handleDiscard}
                disabled={discarding}
              >
                🗑️ Huỷ lượt scan
              </button>
            )}
            <button
              className="btn btn--ghost"
              style={{ padding: "6px 12px" }}
              onClick={onClose}
              aria-label="Đóng"
            >
              ✕ Đóng
            </button>
          </div>
        </div>

        {/* Body modal */}
        {loading ? (
          <div style={{ padding: 40, textAlign: "center", color: "var(--color-ink-soft)" }}>
            Đang tải…
          </div>
        ) : (
          <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
            {/* Ảnh gốc */}
            <div style={{
              width: imgZoomed ? 520 : 280, flexShrink: 0, borderRight: "1px solid var(--color-rule)",
              overflowY: "auto", padding: 16, transition: "width 0.25s ease"
            }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
                <span style={{ fontSize: "0.72rem", textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--color-ink-soft)", fontWeight: 600 }}>
                  📷 Ảnh gốc
                </span>
                <button
                  className="btn btn--ghost"
                  style={{ padding: "2px 6px", fontSize: "0.75rem" }}
                  onClick={() => setImgZoomed(!imgZoomed)}
                >
                  {imgZoomed ? "⊖ Thu nhỏ" : "⊕ Phóng to"}
                </button>
              </div>
              {imgSrc ? (
                <img
                  src={imgSrc}
                  alt="Bảng kê gốc"
                  onClick={() => setImgZoomed(!imgZoomed)}
                  style={{ width: "100%", borderRadius: 4, border: "1px solid var(--color-rule)", cursor: imgZoomed ? "zoom-out" : "zoom-in" }}
                />
              ) : (
                <div style={{ color: "var(--color-ink-soft)", fontSize: "0.85rem" }}>Không tải được ảnh</div>
              )}
            </div>

            {/* Bảng dữ liệu */}
            <div style={{ flex: 1, overflowY: "auto", padding: 16 }}>
              {isPending && (
                <div className="toolbar" style={{ padding: "8px 12px", marginBottom: 16 }}>
                  <div className="field" style={{ margin: 0, display: "flex", alignItems: "center", gap: 10 }}>
                    <label style={{ whiteSpace: "nowrap", margin: 0 }}>Ngày bảng kê (áp dụng cho tất cả phiếu chi):</label>
                    <input type="date" value={ngay} onChange={(e) => setNgay(e.target.value)} style={{ width: 140 }} />
                  </div>
                </div>
              )}

              {confirmError && (
                <div className="banner banner--error" style={{ marginBottom: 12 }}>{confirmError}</div>
              )}

              <div style={{ marginBottom: 10, fontSize: "0.82rem", color: "var(--color-ink-soft)" }}>
                {isConfirmed
                  ? `Dữ liệu đã xác nhận (${detail?.so_dong_xac_nhan ?? 0} dòng)`
                  : `Dữ liệu trích xuất thô (${rows.length} dòng${isPending ? " — chưa xác nhận" : ""})`
                }
              </div>
              <div style={{ overflowX: "auto" }}>
                <table>
                  <thead>
                    <tr>
                      {isPending ? (
                        <>
                          <th>Người bán</th>
                          <th>Hàng hoá</th>
                          <th>SL</th>
                          <th>Đơn giá</th>
                          <th>Tổng tiền</th>
                          <th>Thao tác</th>
                        </>
                      ) : (
                        <>
                          <th>#</th>
                          <th>Người bán</th>
                          <th>Hàng hoá</th>
                          <th style={{ textAlign: "right" }}>Số lượng</th>
                          <th style={{ textAlign: "right" }}>Đơn giá</th>
                          <th style={{ textAlign: "right" }}>Tổng tiền</th>
                        </>
                      )}
                    </tr>
                  </thead>
                  <tbody>
                    {rows.length === 0 ? (
                      <tr>
                        <td colSpan={6} style={{ textAlign: "center", color: "var(--color-ink-soft)", padding: 24 }}>
                          Không có dữ liệu
                        </td>
                      </tr>
                    ) : isPending ? (
                      rows.map((row, i) => {
                        const hasWarning = row.canh_bao_phep_nhan || row.canh_bao_ten_khong_khop || row.do_tin_cay_thap;
                        return (
                          <tr key={i} style={hasWarning ? { background: "var(--color-status-pending-bg)" } : undefined}>
                            <td style={{ minWidth: 220 }}>
                              <input
                                value={row.ten_nguoi_ban}
                                onChange={(e) => updateRow(i, { ten_nguoi_ban: e.target.value })}
                                style={{ width: "100%", padding: "6px 8px", border: "1px solid var(--color-rule)", borderRadius: 4, marginBottom: 4 }}
                              />
                              {row.canh_bao_ten_khong_khop ? (
                                <div style={{ fontSize: "0.78rem", color: "var(--color-status-pending)" }}>
                                  ⚠ không khớp ai có sẵn — sẽ tạo mới, hoặc chọn đúng:
                                  <SearchableSelect
                                    options={sellerOptions}
                                    value={row.seller_id || ""}
                                    onChange={(v) => updateRow(i, { seller_id: v || null })}
                                    placeholder="Gõ để tìm người bán có sẵn…"
                                  />
                                </div>
                              ) : (
                                <div style={{ fontSize: "0.78rem", color: "var(--color-status-signed)" }}>✓ khớp người bán có sẵn</div>
                              )}
                            </td>
                            <td>
                              <input
                                value={row.ten_hang_hoa || ""}
                                onChange={(e) => updateRow(i, { ten_hang_hoa: e.target.value })}
                                style={{ width: 100, padding: "6px 8px", border: "1px solid var(--color-rule)", borderRadius: 4 }}
                              />
                            </td>
                            <td>
                              <input
                                type="number"
                                value={row.so_luong}
                                onChange={(e) => updateRow(i, { so_luong: Number(e.target.value) })}
                                style={{ width: 75, padding: "6px 8px", border: "1px solid var(--color-rule)", borderRadius: 4 }}
                              />
                            </td>
                            <td>
                              <input
                                type="number"
                                value={row.don_gia}
                                onChange={(e) => updateRow(i, { don_gia: Number(e.target.value) })}
                                style={{ width: 85, padding: "6px 8px", border: "1px solid var(--color-rule)", borderRadius: 4 }}
                              />
                            </td>
                            <td>
                              <input
                                type="number"
                                value={row.tong_gia_thanh_toan}
                                onChange={(e) => updateRow(i, { tong_gia_thanh_toan: Number(e.target.value) })}
                                style={{ width: 100, padding: "6px 8px", border: "1px solid var(--color-rule)", borderRadius: 4 }}
                              />
                              {row.canh_bao_phep_nhan && (
                                <div style={{ fontSize: "0.78rem", color: "var(--color-status-void)" }}>
                                  ⚠ Lệch phép nhân
                                </div>
                              )}
                            </td>
                            <td>
                              <button className="btn btn--ghost" style={{ padding: "4px 8px", fontSize: "0.8rem" }} onClick={() => removeRow(i)}>Bỏ dòng</button>
                            </td>
                          </tr>
                        );
                      })
                    ) : (
                      rows.map((row, i) => (
                        <tr key={i}>
                          <td style={{ color: "var(--color-ink-soft)", fontSize: "0.8rem" }}>{i + 1}</td>
                          <td>{String(row.ten_nguoi_ban ?? "")}</td>
                          <td>{String(row.ten_hang_hoa ?? "—")}</td>
                          <td className="num" style={{ textAlign: "right" }}>
                            {Number(row.so_luong).toLocaleString("vi-VN")}
                          </td>
                          <td className="num" style={{ textAlign: "right" }}>
                            {Number(row.don_gia).toLocaleString("vi-VN")}
                          </td>
                          <td className="num" style={{ textAlign: "right", fontWeight: 600 }}>
                            {Number(row.tong_gia_thanh_toan).toLocaleString("vi-VN")}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>

              {/* Tổng tiền */}
              {rows.length > 0 && (
                <div style={{
                  marginTop: 12, padding: "10px 14px", borderRadius: "var(--radius-sm)",
                  background: "var(--color-primary-soft)", display: "flex", justifyContent: "flex-end", gap: 8,
                }}>
                  <span style={{ fontSize: "0.85rem", color: "var(--color-ink-soft)" }}>Tổng cộng:</span>
                  <strong className="num" style={{ color: "var(--color-primary)" }}>
                    {rows.reduce((s, r) => s + Number(r.tong_gia_thanh_toan ?? 0), 0).toLocaleString("vi-VN")} đ
                  </strong>
                </div>
              )}

              {/* Action button confirmation when pending */}
              {isPending && rows.length > 0 && (
                <div style={{ marginTop: 20, display: "flex", gap: 12, justifyContent: "flex-end" }}>
                  <button
                    className="btn btn--primary"
                    onClick={handleConfirm}
                    disabled={confirming}
                    style={{ padding: "10px 28px", fontSize: "0.95rem" }}
                  >
                    {confirming ? "Đang xác nhận…" : `✓ Xác nhận & tạo ${rows.length} phiếu chi nháp`}
                  </button>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Trang lịch sử chính ───────────────────────────────────────────────────────
export function ScanHistoryPage() {
  const [scans, setScans] = useState<ScanImportListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [filterStatus, setFilterStatus] = useState<"all" | ScanImportListItem["status"]>("all");

  const loadScans = () => {
    setLoading(true);
    api.get<ScanImportListItem[]>("/scans/?limit=200")
      .then(setScans)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadScans();
  }, []);

  const filtered = filterStatus === "all"
    ? scans
    : scans.filter((s) => s.status === filterStatus);

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-header__eyebrow">Nhập từ ảnh</div>
          <h1>Lịch sử scan</h1>
        </div>
      </div>

      {error && <div className="banner banner--error">{error}</div>}

      {/* Bộ lọc trạng thái */}
      <div className="toolbar" style={{ marginBottom: 20 }}>
        {(["all", "pending", "confirmed", "discarded"] as const).map((s) => (
          <button
            key={s}
            onClick={() => setFilterStatus(s)}
            className={filterStatus === s ? "btn btn--primary" : "btn btn--ghost"}
            style={{ fontSize: "0.85rem" }}
          >
            {s === "all" ? `Tất cả (${scans.length})`
              : s === "pending"   ? `Chờ xác nhận (${scans.filter(x => x.status === "pending").length})`
              : s === "confirmed" ? `Đã xác nhận (${scans.filter(x => x.status === "confirmed").length})`
              : `Đã huỷ (${scans.filter(x => x.status === "discarded").length})`
            }
          </button>
        ))}
      </div>

      {/* Grid ảnh */}
      {loading ? (
        <div className="empty-state">Đang tải lịch sử…</div>
      ) : filtered.length === 0 ? (
        <div className="empty-state">
          <div style={{ fontSize: "2.5rem", marginBottom: 12 }}>📷</div>
          <div style={{ fontWeight: 600, marginBottom: 6 }}>Chưa có lượt scan nào</div>
          <div style={{ fontSize: "0.88rem" }}>Vào mục "Scan bảng kê" để bắt đầu trích xuất từ ảnh.</div>
        </div>
      ) : (
        <div style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))",
          gap: 16,
        }}>
          {filtered.map((scan) => (
            <div
              key={scan.id}
              onClick={() => setSelectedId(scan.id)}
              style={{
                background: "var(--color-paper-raised)",
                border: "1px solid var(--color-rule)",
                borderRadius: "var(--radius-md)",
                boxShadow: "var(--shadow-card)",
                overflow: "hidden",
                cursor: "pointer",
                transition: "box-shadow 0.15s ease, transform 0.15s ease",
              }}
              onMouseEnter={(e) => {
                (e.currentTarget as HTMLElement).style.boxShadow = "0 4px 16px rgba(35,34,32,0.14)";
                (e.currentTarget as HTMLElement).style.transform = "translateY(-2px)";
              }}
              onMouseLeave={(e) => {
                (e.currentTarget as HTMLElement).style.boxShadow = "var(--shadow-card)";
                (e.currentTarget as HTMLElement).style.transform = "";
              }}
            >
              {/* Thumbnail */}
              <div style={{ padding: 8 }}>
                <ScanThumbnail scanId={scan.id} />
              </div>

              {/* Info */}
              <div style={{ padding: "8px 12px 12px" }}>
                <div style={{ marginBottom: 6 }}>
                  <span className={`status-seal ${STATUS_CLASS[scan.status]}`} style={{ fontSize: "0.7rem" }}>
                    {STATUS_LABEL[scan.status]}
                  </span>
                </div>

                <div style={{ fontSize: "0.82rem", fontWeight: 600, marginBottom: 2 }}>
                  {new Date(scan.created_at).toLocaleDateString("vi-VN", {
                    day: "2-digit", month: "2-digit", year: "numeric",
                  })}
                </div>
                <div style={{ fontSize: "0.76rem", color: "var(--color-ink-soft)" }}>
                  {new Date(scan.created_at).toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" })}
                </div>

                <div style={{ marginTop: 8, fontSize: "0.78rem", color: "var(--color-ink-soft)" }}>
                  {scan.so_dong_trich_xuat} dòng trích xuất
                  {scan.so_dong_xac_nhan != null && (
                    <span style={{ color: "var(--color-status-signed)", marginLeft: 4 }}>
                      · {scan.so_dong_xac_nhan} đã xác nhận
                    </span>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Modal chi tiết */}
      {selectedId && (
        <DetailModal scanId={selectedId} onClose={() => setSelectedId(null)} onRefresh={loadScans} />
      )}
    </div>
  );
}
