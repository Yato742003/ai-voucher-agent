import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type { ExtractedRow, ScanConfirmResponse, ScanExtractResponse, Seller } from "../api/types";
import { SearchableSelect } from "../components/SearchableSelect";
import { useToast } from "../contexts/ToastContext";

// ── Types ─────────────────────────────────────────────────────────
interface EditableRow extends ExtractedRow {
  seller_id: string | null;
}

interface CropRect {
  x: number; y: number; w: number; h: number; // fractions 0–1
}

type ScanPhase = "idle" | "editing" | "scanning" | "results";

// ── Loading steps ─────────────────────────────────────────────────
const SCAN_STEPS = [
  { label: "Tải ảnh lên server", afterMs: 0 },
  { label: "Gửi cho AI phân tích", afterMs: 1500 },
  { label: "AI đang đọc từng dòng", afterMs: 4000 },
  { label: "Kiểm tra chéo dữ liệu", afterMs: 12000 },
  { label: "Sắp xong…", afterMs: 20000 },
];

// ── Error classifier ──────────────────────────────────────────────
function classifyError(err: unknown): { icon: string; title: string; detail: string } {
  if (err instanceof TypeError) {
    return { icon: "📡", title: "Lỗi kết nối mạng", detail: "Không kết nối được tới server. Kiểm tra kết nối internet hoặc server backend đang tắt." };
  }
  if (err instanceof ApiError) {
    const msg = err.message.toLowerCase();
    if (msg.includes("api_key") || msg.includes("api key") || msg.includes("nim_api_key") || msg.includes("anthropic_api_key"))
      return { icon: "🔑", title: "Chưa cấu hình API Key", detail: err.message };
    if (msg.includes("quota") || msg.includes("rate") || msg.includes("429") || msg.includes("hạn mức"))
      return { icon: "⏳", title: "Hết quota API", detail: err.message };
    if (msg.includes("timeout") || msg.includes("timed out"))
      return { icon: "⏱", title: "Hết thời gian chờ", detail: err.message || "Server AI phản hồi quá lâu. Thử lại hoặc chụp ảnh nhỏ/rõ hơn." };
    if (msg.includes("kết nối"))
      return { icon: "📡", title: "Lỗi kết nối API", detail: err.message };
    return { icon: "⚠️", title: `Lỗi từ server (${err.status})`, detail: err.message };
  }
  return { icon: "❌", title: "Lỗi không xác định", detail: String(err) };
}

// ── Canvas utilities ──────────────────────────────────────────────
function loadImageFromFile(file: File): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => { URL.revokeObjectURL(url); resolve(img); };
    img.onerror = () => { URL.revokeObjectURL(url); reject(new Error("Load failed")); };
    img.src = url;
  });
}

function applyTransforms(img: HTMLImageElement, rotation: number, crop: CropRect | null): Promise<Blob> {
  return new Promise((resolve, reject) => {
    // Bước 1: xoay
    const rotC = document.createElement("canvas");
    const rotCtx = rotC.getContext("2d")!;
    const swap = rotation === 90 || rotation === 270;
    rotC.width = swap ? img.naturalHeight : img.naturalWidth;
    rotC.height = swap ? img.naturalWidth : img.naturalHeight;
    rotCtx.translate(rotC.width / 2, rotC.height / 2);
    rotCtx.rotate((rotation * Math.PI) / 180);
    rotCtx.drawImage(img, -img.naturalWidth / 2, -img.naturalHeight / 2);

    // Bước 2: cắt
    let out: HTMLCanvasElement;
    if (crop && crop.w > 0.01 && crop.h > 0.01) {
      out = document.createElement("canvas");
      const cx = Math.round(crop.x * rotC.width);
      const cy = Math.round(crop.y * rotC.height);
      const cw = Math.round(crop.w * rotC.width);
      const ch = Math.round(crop.h * rotC.height);
      out.width = cw; out.height = ch;
      out.getContext("2d")!.drawImage(rotC, cx, cy, cw, ch, 0, 0, cw, ch);
    } else {
      out = rotC;
    }

    out.toBlob((b) => (b ? resolve(b) : reject(new Error("Canvas export failed"))), "image/jpeg", 0.92);
  });
}

function normalizeCrop(s: CropRect): CropRect {
  return {
    x: Math.max(0, Math.min(1, s.w < 0 ? s.x + s.w : s.x)),
    y: Math.max(0, Math.min(1, s.h < 0 ? s.y + s.h : s.y)),
    w: Math.min(1, Math.abs(s.w)),
    h: Math.min(1, Math.abs(s.h)),
  };
}

// ══════════════════════════════════════════════════════════════════
// Component chính
// ══════════════════════════════════════════════════════════════════

export function ScanImportPage() {
  const { showToast } = useToast();
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const cropContainerRef = useRef<HTMLDivElement>(null);

  // ── Phase ──
  const [phase, setPhase] = useState<ScanPhase>("idle");

  // ── Image editing ──
  const [originalFile, setOriginalFile] = useState<File | null>(null);
  const [originalImg, setOriginalImg] = useState<HTMLImageElement | null>(null);
  const [rotation, setRotation] = useState(0);
  const [cropRect, setCropRect] = useState<CropRect | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  // ── Crop interaction ──
  const [cropMode, setCropMode] = useState(false);
  const [cropDragging, setCropDragging] = useState(false);
  const [cropDraft, setCropDraft] = useState<CropRect | null>(null);
  const [dragOver, setDragOver] = useState(false);

  // ── Scan results ──
  const [scanId, setScanId] = useState<string | null>(null);
  const [rows, setRows] = useState<EditableRow[]>([]);
  const [ngay, setNgay] = useState(() => new Date().toISOString().slice(0, 10));
  const [sellers, setSellers] = useState<Seller[]>([]);
  const [confirming, setConfirming] = useState(false);
  const [editedImageUrl, setEditedImageUrl] = useState<string | null>(null);
  const [imgZoomed, setImgZoomed] = useState(false);
  const [showInstructions, setShowInstructions] = useState(true);

  // ── Loading & error ──
  const [scanError, setScanError] = useState<ReturnType<typeof classifyError> | null>(null);
  const [scanStartTime, setScanStartTime] = useState(0);
  const [scanElapsed, setScanElapsed] = useState(0);
  const [confirmError, setConfirmError] = useState<string | null>(null);

  // ── Tự động thu gọn hướng dẫn khi bắt đầu có hình/kết quả ──
  useEffect(() => {
    if (phase === "results" || phase === "editing") {
      setShowInstructions(false);
    }
  }, [phase]);

  // ── Preview cập nhật khi xoay ──
  useEffect(() => {
    if (!originalImg) return;
    let cancelled = false;
    applyTransforms(originalImg, rotation, null).then((blob) => {
      if (cancelled) return;
      setPreviewUrl((old) => { if (old) URL.revokeObjectURL(old); return URL.createObjectURL(blob); });
    });
    return () => { cancelled = true; };
  }, [originalImg, rotation]);

  // ── Timer khi scanning ──
  useEffect(() => {
    if (phase !== "scanning") return;
    const id = setInterval(() => setScanElapsed(Date.now() - scanStartTime), 200);
    return () => clearInterval(id);
  }, [phase, scanStartTime]);

  // ═══════════════════════════════════════════════════════════════
  // Handlers
  // ═══════════════════════════════════════════════════════════════

  function handleFileSelected(file: File) {
    setScanError(null);
    setConfirmError(null);
    setRotation(0);
    setCropRect(null);
    setCropMode(false);
    setCropDraft(null);
    setRows([]);
    setScanId(null);
    loadImageFromFile(file).then((img) => {
      setOriginalFile(file);
      setOriginalImg(img);
      setPhase("editing");
    }).catch(() => {
      setScanError({ icon: "📷", title: "Ảnh không hợp lệ", detail: "Không đọc được file ảnh — thử file khác." });
    });
  }

  function handleRotate(deg: number) {
    setRotation((p) => (p + deg + 360) % 360);
    setCropRect(null);
    setCropDraft(null);
    setCropMode(false);
  }

  // ── Crop mouse handlers ──
  const handleCropMouseDown = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if (!cropContainerRef.current) return;
    e.preventDefault();
    const rect = cropContainerRef.current.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width;
    const y = (e.clientY - rect.top) / rect.height;
    setCropDragging(true);
    setCropDraft({ x, y, w: 0, h: 0 });
  }, []);

  const handleCropMouseMove = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if (!cropContainerRef.current) return;
    const rect = cropContainerRef.current.getBoundingClientRect();
    const x = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    const y = Math.max(0, Math.min(1, (e.clientY - rect.top) / rect.height));
    setCropDraft((prev) => prev ? { ...prev, w: x - prev.x, h: y - prev.y } : null);
  }, []);

  const handleCropMouseUp = useCallback(() => {
    setCropDragging(false);
    setCropDraft((prev) => {
      if (prev && Math.abs(prev.w) < 0.02 && Math.abs(prev.h) < 0.02) return null;
      return prev;
    });
  }, []);

  function applyCrop() {
    if (cropDraft) { setCropRect(normalizeCrop(cropDraft)); setCropDraft(null); setCropMode(false); }
  }

  function resetEdits() {
    setRotation(0); setCropRect(null); setCropDraft(null); setCropMode(false);
  }

  // ── Start scan ──
  async function handleStartScan() {
    if (!originalImg) return;
    setPhase("scanning");
    setScanError(null);
    setScanStartTime(Date.now());
    setScanElapsed(0);
    try {
      const editedBlob = await applyTransforms(originalImg, rotation, cropRect);
      setEditedImageUrl((old) => { if (old) URL.revokeObjectURL(old); return URL.createObjectURL(editedBlob); });

      const [sellerList] = await Promise.all([api.get<Seller[]>("/sellers/")]);
      setSellers(sellerList);

      const formData = new FormData();
      formData.append("file", editedBlob, originalFile?.name || "scan.jpg");
      const result = await api.post<ScanExtractResponse>("/scans/extract", formData);

      setScanId(result.scan_id);
      setRows(result.rows.map((r) => ({ ...r, seller_id: r.seller_id_goi_y })));
      setPhase("results");

      const warns = result.rows.filter((r) => r.canh_bao_phep_nhan || r.canh_bao_ten_khong_khop).length;
      showToast(warns > 0 ? "info" : "success",
        warns > 0
          ? `Trích xuất xong ${result.rows.length} dòng — có ${warns} dòng cần xem lại.`
          : `Trích xuất xong ${result.rows.length} dòng, không có cảnh báo.`
      );
    } catch (err) {
      setScanError(classifyError(err));
      setPhase("editing");
    }
  }

  // ── Row editing ──
  function updateRow(i: number, patch: Partial<EditableRow>) {
    setRows((prev) => prev.map((r, j) => (j === i ? { ...r, ...patch } : r)));
  }
  function removeRow(i: number) {
    setRows((prev) => prev.filter((_, j) => j !== i));
  }

  // ── Confirm ──
  async function handleConfirm() {
    if (!scanId || rows.length === 0) return;
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
      showToast("success", `Đã tạo ${result.so_phieu_da_tao} phiếu chi nháp — vào mục Phiếu chi để duyệt.`);
      navigate("/vouchers");
    } catch (err) {
      setConfirmError(err instanceof ApiError ? err.message : "Không tạo được phiếu");
    } finally {
      setConfirming(false);
    }
  }

  // ── Reset ──
  function handleReset() {
    if (scanId) {
      api.post(`/scans/${scanId}/discard`).catch(() => {});
    }
    setPhase("idle");
    setRows([]); setScanId(null); setOriginalFile(null); setOriginalImg(null);
    setRotation(0); setCropRect(null); setCropMode(false); setCropDraft(null);
    setImgZoomed(false); setScanError(null); setConfirmError(null);
    setPreviewUrl((old) => { if (old) URL.revokeObjectURL(old); return null; });
    setEditedImageUrl((old) => { if (old) URL.revokeObjectURL(old); return null; });
  }

  // ═══════════════════════════════════════════════════════════════
  // Render helpers
  // ═══════════════════════════════════════════════════════════════

  const sellerOptions = sellers.map((s) => ({ value: s.id, label: s.name }));
  const soCanhBao = rows.filter((r) => r.canh_bao_phep_nhan || r.canh_bao_ten_khong_khop).length;

  // Crop overlay (dùng chung cho cả draft khi đang kéo và applied crop)
  function renderCropOverlay() {
    const sel = cropMode ? (cropDraft ? normalizeCrop(cropDraft) : null) : cropRect;
    if (!sel || (sel.w < 0.01 && sel.h < 0.01)) return null;
    const ov = { position: "absolute" as const, pointerEvents: "none" as const, background: "rgba(0,0,0,0.45)" };
    return (
      <>
        <div style={{ ...ov, top: 0, left: 0, right: 0, height: `${sel.y * 100}%` }} />
        <div style={{ ...ov, bottom: 0, left: 0, right: 0, height: `${Math.max(0, (1 - sel.y - sel.h)) * 100}%` }} />
        <div style={{ ...ov, top: `${sel.y * 100}%`, left: 0, width: `${sel.x * 100}%`, height: `${sel.h * 100}%` }} />
        <div style={{ ...ov, top: `${sel.y * 100}%`, right: 0, width: `${Math.max(0, (1 - sel.x - sel.w)) * 100}%`, height: `${sel.h * 100}%` }} />
        <div style={{
          position: "absolute", pointerEvents: "none",
          top: `${sel.y * 100}%`, left: `${sel.x * 100}%`,
          width: `${sel.w * 100}%`, height: `${sel.h * 100}%`,
          border: cropMode ? "2px dashed white" : "2px solid var(--color-primary)",
          boxShadow: "0 0 0 1px rgba(0,0,0,0.3)",
        }} />
      </>
    );
  }

  // ═══════════════════════════════════════════════════════════════
  // Render
  // ═══════════════════════════════════════════════════════════════

  return (
    <div>
      <div className="page-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <div>
          <div className="page-header__eyebrow">Nhập nhanh từ ảnh</div>
          <h1>Scan bảng kê</h1>
        </div>
        {phase !== "idle" && (
          <button
            className="btn btn--ghost"
            onClick={() => setShowInstructions((prev) => !prev)}
            style={{ fontSize: "0.85rem", padding: "6px 12px" }}
          >
            {showInstructions ? "🙈 Ẩn hướng dẫn" : "ℹ️ Hướng dẫn"}
          </button>
        )}
      </div>

      {showInstructions && (
        <div className="banner banner--info" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", transition: "all 0.2s" }}>
          <span>
            Chụp/tải ảnh bảng kê viết tay — chỉnh sửa ảnh nếu cần (cắt, xoay) rồi bấm Scan.
            Hệ thống đọc và điền sẵn từng dòng — bạn xem lại trước khi xác nhận tạo phiếu.
          </span>
          {phase === "idle" && (
            <button
              className="btn btn--ghost"
              onClick={() => setShowInstructions(false)}
              style={{ fontSize: "0.8rem", padding: "2px 6px", border: "none", background: "none", color: "inherit", textDecoration: "underline", cursor: "pointer", marginLeft: 10 }}
            >
              Ẩn
            </button>
          )}
        </div>
      )}

      {!showInstructions && phase === "idle" && (
        <div style={{ textAlign: "right", marginBottom: 12 }}>
          <button
            className="btn btn--ghost"
            onClick={() => setShowInstructions(true)}
            style={{ fontSize: "0.8rem", padding: "4px 8px" }}
          >
            Hiện hướng dẫn ℹ️
          </button>
        </div>
      )}

      {/* ══════════════════ PHASE: IDLE ══════════════════ */}
      {phase === "idle" && (
        <div
          className="card"
          onClick={() => fileInputRef.current?.click()}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault(); setDragOver(false);
            const file = e.dataTransfer.files[0];
            if (file) handleFileSelected(file);
          }}
          style={{
            padding: 48, textAlign: "center", cursor: "pointer",
            border: dragOver ? "2px dashed var(--color-primary)" : "2px dashed var(--color-rule)",
            background: dragOver ? "var(--color-primary-soft)" : "transparent",
            borderRadius: "var(--radius-md)",
            transition: "border-color 0.2s, background 0.2s",
          }}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".jpg,.jpeg,.png,.webp"
            style={{ display: "none" }}
            onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFileSelected(f); }}
          />
          <div style={{ fontSize: "3rem", marginBottom: 12 }}>📷</div>
          <div style={{ fontWeight: 600, marginBottom: 4, fontSize: "1.05rem" }}>Kéo thả ảnh vào đây</div>
          <div style={{ fontSize: "0.85rem", color: "var(--color-ink-soft)" }}>hoặc click để chọn file · JPG, PNG, WebP</div>
        </div>
      )}

      {/* ══════════════════ PHASE: EDITING ══════════════════ */}
      {phase === "editing" && previewUrl && (
        <>
          <div className="card" style={{ marginBottom: 24, padding: 16 }}>
            {/* Toolbar chỉnh sửa ảnh */}
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 12 }}>
              <button className="btn btn--ghost" onClick={() => handleRotate(-90)}>↺ Xoay trái</button>
              <button className="btn btn--ghost" onClick={() => handleRotate(90)}>↻ Xoay phải</button>
              <div style={{ width: 1, background: "var(--color-rule)", margin: "0 4px" }} />
              {!cropMode ? (
                <button className="btn btn--ghost" onClick={() => setCropMode(true)}>
                  {cropRect ? "✂ Cắt lại" : "✂ Cắt ảnh"}
                </button>
              ) : (
                <>
                  <button className="btn btn--primary" onClick={applyCrop}
                    disabled={!cropDraft || (Math.abs(cropDraft.w) < 0.02 && Math.abs(cropDraft.h) < 0.02)}>
                    ✓ Áp dụng cắt
                  </button>
                  <button className="btn btn--ghost" onClick={() => { setCropMode(false); setCropDraft(null); }}>
                    Huỷ cắt
                  </button>
                </>
              )}
              {(rotation !== 0 || cropRect) && (
                <button className="btn btn--ghost" onClick={resetEdits} style={{ marginLeft: "auto" }}>
                  ↩ Reset ảnh gốc
                </button>
              )}
            </div>

            {/* Gợi ý crop mode */}
            {cropMode && !cropDraft && (
              <div className="banner banner--info" style={{ margin: "0 0 12px", fontSize: "0.85rem", padding: "8px 12px" }}>
                Kéo chuột trên ảnh để chọn vùng cần giữ lại
              </div>
            )}

            {/* Indicator: đã crop */}
            {cropRect && !cropMode && (
              <div style={{ marginBottom: 12, display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ fontSize: "0.82rem", background: "var(--color-primary-soft)", padding: "3px 10px", borderRadius: "var(--radius-sm)" }}>
                  ✂ Đã cắt — chỉ vùng được chọn sẽ gửi cho AI
                </span>
                <button className="btn btn--ghost" style={{ fontSize: "0.8rem", padding: "2px 6px" }} onClick={() => setCropRect(null)}>
                  Xoá vùng cắt
                </button>
              </div>
            )}

            {/* Ảnh preview với crop overlay */}
            <div
              ref={cropContainerRef}
              style={{ position: "relative", maxWidth: 700, margin: "0 auto", userSelect: "none" }}
              onMouseDown={cropMode ? handleCropMouseDown : undefined}
              onMouseMove={(cropMode && cropDragging) ? handleCropMouseMove : undefined}
              onMouseUp={cropMode ? handleCropMouseUp : undefined}
              onMouseLeave={cropMode ? handleCropMouseUp : undefined}
            >
              <img
                src={previewUrl}
                alt="Preview bảng kê"
                draggable={false}
                style={{
                  width: "100%", display: "block", borderRadius: 4,
                  border: "1px solid var(--color-rule)",
                  cursor: cropMode ? "crosshair" : "default",
                }}
              />
              {renderCropOverlay()}
            </div>

            {/* Nút hành động */}
            <div style={{ marginTop: 16, display: "flex", gap: 10, justifyContent: "center" }}>
              <button className="btn btn--primary" onClick={handleStartScan} disabled={cropMode}
                style={{ padding: "10px 32px", fontSize: "1rem" }}>
                🔍 Bắt đầu scan bảng kê
              </button>
              <button className="btn btn--ghost" onClick={handleReset}>
                Chọn ảnh khác
              </button>
            </div>
          </div>

          {/* Error card */}
          {scanError && (
            <div className="card" style={{ marginBottom: 24, padding: 24, borderLeft: "4px solid var(--color-status-void)" }}>
              <div style={{ display: "flex", gap: 16, alignItems: "flex-start" }}>
                <div style={{ fontSize: "2rem", flexShrink: 0 }}>{scanError.icon}</div>
                <div>
                  <div style={{ fontWeight: 700, marginBottom: 4 }}>{scanError.title}</div>
                  <div style={{ fontSize: "0.88rem", color: "var(--color-ink-soft)", marginBottom: 12 }}>{scanError.detail}</div>
                  <div style={{ display: "flex", gap: 8 }}>
                    <button className="btn btn--primary" onClick={handleStartScan}>🔄 Thử lại</button>
                    <button className="btn btn--ghost" onClick={handleReset}>Chọn ảnh khác</button>
                  </div>
                </div>
              </div>
            </div>
          )}
        </>
      )}

      {/* ══════════════════ PHASE: SCANNING ══════════════════ */}
      {phase === "scanning" && (
        <div className="card" style={{ padding: 48, maxWidth: 520, margin: "0 auto" }}>
          <div style={{ textAlign: "center", marginBottom: 20 }}>
            <div style={{ fontSize: "3.5rem", display: "inline-block", animation: "scan-pulse 1.5s ease-in-out infinite" }}>🔍</div>
          </div>
          <h2 style={{ textAlign: "center", marginBottom: 24 }}>Đang đọc bảng kê…</h2>

          <div style={{ maxWidth: 340, margin: "0 auto" }}>
            {SCAN_STEPS.map((step, i) => {
              const activeIdx = SCAN_STEPS.findIndex((_, j) => {
                const next = SCAN_STEPS[j + 1];
                return !next || scanElapsed < next.afterMs;
              });
              const isDone = i < activeIdx;
              const isActive = i === activeIdx;
              const dots = ".".repeat((Math.floor(scanElapsed / 400) % 3) + 1);
              return (
                <div key={i} style={{ display: "flex", alignItems: "center", gap: 12, padding: "7px 0", fontSize: "0.92rem" }}>
                  <span style={{
                    width: 22, height: 22, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center",
                    fontSize: "0.7rem", fontWeight: 700, flexShrink: 0,
                    background: isDone ? "var(--color-status-signed)" : isActive ? "var(--color-primary)" : "var(--color-rule)",
                    color: (isDone || isActive) ? "white" : "var(--color-ink-soft)",
                    transition: "background 0.3s",
                  }}>
                    {isDone ? "✓" : i + 1}
                  </span>
                  <span style={{
                    color: isDone ? "var(--color-status-signed)" : isActive ? "var(--color-ink)" : "var(--color-ink-soft)",
                    fontWeight: isActive ? 600 : 400,
                  }}>
                    {step.label}{isActive ? dots : ""}
                  </span>
                  {isActive && (
                    <span style={{
                      width: 14, height: 14, border: "2px solid var(--color-primary)",
                      borderTopColor: "transparent", borderRadius: "50%",
                      animation: "scan-spin 0.8s linear infinite", flexShrink: 0,
                    }} />
                  )}
                </div>
              );
            })}
          </div>

          <div style={{ textAlign: "center", marginTop: 24, fontSize: "0.88rem", color: "var(--color-ink-soft)" }}>
            ⏱ {Math.floor(scanElapsed / 1000)} giây
          </div>
        </div>
      )}

      {/* ══════════════════ PHASE: RESULTS ══════════════════ */}

      {/* Edge case: model không đọc được dòng nào */}
      {phase === "results" && scanId && rows.length === 0 && (
        <div className="card" style={{ marginBottom: 24 }}>
          <div style={{ display: "flex", gap: 20, alignItems: "flex-start" }}>
            {editedImageUrl && (
              <img src={editedImageUrl} alt="Ảnh đã gửi" style={{ maxWidth: 200, borderRadius: 4, border: "1px solid var(--color-rule)", flexShrink: 0 }} />
            )}
            <div>
              <p style={{ margin: "0 0 12px", fontWeight: 600 }}>Model không đọc được dòng nào từ ảnh này.</p>
              <p style={{ margin: "0 0 16px", fontSize: "0.88rem", color: "var(--color-ink-soft)" }}>
                Thử chụp lại ảnh: đủ ánh sáng, vuông góc, không bị mờ/rung. Hoặc dùng chức năng cắt để chỉ giữ phần bảng kê.
              </p>
              <button className="btn btn--ghost" onClick={handleReset}>Chọn ảnh khác</button>
            </div>
          </div>
        </div>
      )}

      {/* Bảng kết quả chỉnh sửa */}
      {phase === "results" && rows.length > 0 && (
        <>
          {confirmError && <div className="banner banner--error">{confirmError}</div>}

          <div className="toolbar">
            <div className="field" style={{ margin: 0 }}>
              <label>Ngày mua (áp dụng cho cả bảng)</label>
              <input type="date" value={ngay} onChange={(e) => setNgay(e.target.value)} />
            </div>
            {soCanhBao > 0 && (
              <div className="banner banner--warn" style={{ margin: 0, flex: 1 }}>
                {soCanhBao} dòng cần xem lại — highlight màu bên dưới.
              </div>
            )}
          </div>

          {/* 2 cột: ảnh đã gửi (trái) + bảng dữ liệu (phải) */}
          <div style={{ display: "flex", gap: 20, alignItems: "flex-start" }}>

            {/* ── Cột trái: ảnh đối chứng ── */}
            {editedImageUrl && (
              <div style={{ flexShrink: 0, width: imgZoomed ? 560 : 280, transition: "width 0.25s ease" }}>
                <div className="card" style={{ padding: 12, position: "sticky", top: 20 }}>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
                    <span style={{ fontSize: "0.72rem", textTransform: "uppercase", letterSpacing: "0.07em", color: "var(--color-ink-soft)", fontWeight: 600 }}>
                      📷 Ảnh đã gửi AI
                    </span>
                    <button className="btn btn--ghost" style={{ padding: "3px 8px", fontSize: "0.78rem" }}
                      onClick={() => setImgZoomed((z) => !z)} title={imgZoomed ? "Thu nhỏ" : "Phóng to"}>
                      {imgZoomed ? "⊖ Thu nhỏ" : "⊕ Phóng to"}
                    </button>
                  </div>
                  <div style={{ maxHeight: "calc(100vh - 140px)", overflowY: "auto" }}>
                    <img
                      src={editedImageUrl}
                      alt="Ảnh bảng kê đã chỉnh"
                      onClick={() => setImgZoomed((z) => !z)}
                      style={{
                        width: "100%", borderRadius: 4, border: "1px solid var(--color-rule)",
                        cursor: imgZoomed ? "zoom-out" : "zoom-in", display: "block",
                      }}
                    />
                  </div>
                  <div style={{ marginTop: 8, fontSize: "0.76rem", color: "var(--color-ink-soft)", textAlign: "center" }}>
                    Click ảnh để {imgZoomed ? "thu nhỏ" : "phóng to"}
                  </div>
                </div>
              </div>
            )}

            {/* ── Cột phải: bảng chỉnh sửa ── */}
            <div style={{ flex: 1, minWidth: 0 }}>
              <div className="card">
                <div style={{ overflowX: "auto" }}>
                <table>
                  <thead>
                    <tr>
                      <th>Người bán</th>
                      <th>Hàng hoá</th>
                      <th>SL</th>
                      <th>Đơn giá</th>
                      <th>Tổng tiền</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((row, i) => {
                      const hasWarning = row.canh_bao_phep_nhan || row.canh_bao_ten_khong_khop || row.do_tin_cay_thap;
                      return (
                        <tr key={i} style={hasWarning ? { background: "var(--color-status-pending-bg)" } : undefined}>
                          <td style={{ minWidth: 200 }}>
                            <input
                              value={row.ten_nguoi_ban}
                              onChange={(e) => updateRow(i, { ten_nguoi_ban: e.target.value })}
                              style={{ width: "100%", padding: "6px 8px", border: "1px solid var(--color-rule)", borderRadius: 4, marginBottom: 4 }}
                            />
                            {row.canh_bao_ten_khong_khop ? (
                              <div style={{ fontSize: "0.78rem", color: "var(--color-status-pending)" }}>
                                ⚠ không khớp ai có sẵn — sẽ tạo người bán mới, hoặc chọn đúng người:
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
                            {row.do_tin_cay_thap && (
                              <div style={{ fontSize: "0.78rem", color: "var(--color-status-void)" }}>⚠ chữ mờ, model không chắc chắn</div>
                            )}
                          </td>
                          <td>
                            <input value={row.ten_hang_hoa || ""} onChange={(e) => updateRow(i, { ten_hang_hoa: e.target.value })}
                              style={{ width: 100, padding: "6px 8px", border: "1px solid var(--color-rule)", borderRadius: 4 }} />
                          </td>
                          <td>
                            <input type="number" value={row.so_luong} onChange={(e) => updateRow(i, { so_luong: Number(e.target.value) })}
                              style={{ width: 75, padding: "6px 8px", border: "1px solid var(--color-rule)", borderRadius: 4 }} />
                          </td>
                          <td>
                            <input type="number" value={row.don_gia} onChange={(e) => updateRow(i, { don_gia: Number(e.target.value) })}
                              style={{ width: 85, padding: "6px 8px", border: "1px solid var(--color-rule)", borderRadius: 4 }} />
                          </td>
                          <td>
                            <input type="number" value={row.tong_gia_thanh_toan} onChange={(e) => updateRow(i, { tong_gia_thanh_toan: Number(e.target.value) })}
                              style={{ width: 100, padding: "6px 8px", border: "1px solid var(--color-rule)", borderRadius: 4 }} />
                            {row.canh_bao_phep_nhan && (
                              <div style={{ fontSize: "0.78rem", color: "var(--color-status-void)" }}>
                                ⚠ SL × đơn giá ≠ tổng tiền — kiểm tra lại
                              </div>
                            )}
                          </td>
                          <td>
                            <button className="btn btn--ghost" onClick={() => removeRow(i)}>Bỏ dòng</button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
                </div>

                <div style={{ marginTop: 20, display: "flex", gap: 10 }}>
                  <button className="btn btn--primary" onClick={handleConfirm} disabled={confirming || rows.length === 0}>
                    {confirming ? "Đang tạo phiếu…" : `Xác nhận & tạo ${rows.length} phiếu chi nháp`}
                  </button>
                  <button className="btn btn--ghost" onClick={handleReset}>Huỷ, chọn ảnh khác</button>
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
