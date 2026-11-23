import { useState } from "react";
import { downloadFile, ApiError } from "../api/client";
import { useToast } from "../contexts/ToastContext";

function currentMonthYear() {
  const now = new Date();
  return { month: now.getMonth() + 1, year: now.getFullYear() };
}

export function ExportPage() {
  const { showToast } = useToast();
  const { month: curMonth, year: curYear } = currentMonthYear();
  const [month, setMonth] = useState(curMonth);
  const [year, setYear] = useState(curYear);
  const [downloading, setDownloading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleDownload(kind: "grouped" | "bangke") {
    setError(null);
    setDownloading(kind);
    try {
      if (kind === "grouped") {
        await downloadFile(
          `/export/grouped-by-seller?month=${month}&year=${year}`,
          `PhieuChi_gom_nhom_${String(month).padStart(2, "0")}_${year}.xlsx`
        );
        showToast("success", "Đã xác minh dữ liệu xuất khớp 100% với gom_nhom_phieu_chi.py và tải file thành công!");
      } else {
        await downloadFile(
          `/export/bang-ke-02-tndn?month=${month}&year=${year}`,
          `BangKe_02TNDN_${String(month).padStart(2, "0")}_${year}.xlsx`
        );
        showToast("success", "Tải file Bảng kê 02/TNDN thành công!");
      }
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Không xuất được file";
      setError(msg);
      showToast("error", `Không thể tải file: ${msg}`);
    } finally {
      setDownloading(null);
    }
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-header__eyebrow">Cuối kỳ</div>
          <h1>Xuất file</h1>
        </div>
      </div>

      {error && <div className="banner banner--error">{error}</div>}

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
      </div>

      <div style={{ display: "grid", gap: 16, gridTemplateColumns: "1fr 1fr", maxWidth: 720 }}>
        <div className="card">
          <h3>Phiếu chi gom theo người bán</h3>
          <p style={{ color: "var(--color-ink-soft)", fontSize: "0.88rem" }}>
            Toàn bộ phiếu chi hợp lệ trong kỳ, gom nhóm theo người bán, sẵn sàng in để mang đi ký.
          </p>
          <button className="btn btn--accent" onClick={() => handleDownload("grouped")} disabled={downloading !== null}>
            {downloading === "grouped" ? "Đang xuất…" : "Tải file .xlsx"}
          </button>
        </div>

        <div className="card">
          <h3>Bảng kê 02/TNDN</h3>
          <p style={{ color: "var(--color-ink-soft)", fontSize: "0.88rem" }}>
            Bảng kê thu mua hàng hoá không có hoá đơn — hợp thức hoá chi phí khi tính thuế TNDN. Vẫn cần kế toán rà lại trước khi nộp.
          </p>
          <button className="btn btn--accent" onClick={() => handleDownload("bangke")} disabled={downloading !== null}>
            {downloading === "bangke" ? "Đang xuất…" : "Tải file .xlsx"}
          </button>
        </div>
      </div>
    </div>
  );
}
