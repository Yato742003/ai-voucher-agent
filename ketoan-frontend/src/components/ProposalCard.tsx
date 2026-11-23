import { useId, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type { AgentProposal, Seller, Voucher } from "../api/types";
import { useToast } from "../contexts/ToastContext";
import { SearchableSelect } from "./SearchableSelect";

type Status = "idle" | "saving" | "saved" | "dismissed";

/**
 * Thẻ đề xuất do Agent soạn. Người dùng sửa được mọi trường rồi bấm Lưu — lúc đó mới
 * gọi đúng POST /vouchers/ như thao tác tay (cùng RBAC, cùng audit). Agent không có đường ghi riêng.
 */
export function ProposalCard({
  proposal,
  sellers,
  sellersLoadFailed,
  onNavigate,
}: {
  proposal: AgentProposal;
  sellers: Seller[];
  sellersLoadFailed?: boolean;
  onNavigate?: () => void;
}) {
  const uid = useId();
  const { showToast } = useToast();
  const [sellerId, setSellerId] = useState(proposal.seller_id ?? "");
  const [ngay, setNgay] = useState(proposal.ngay);
  const [lyDo, setLyDo] = useState(proposal.ly_do_chi);
  const [soLuong, setSoLuong] = useState(proposal.so_luong === null ? "" : String(proposal.so_luong));
  const [donGia, setDonGia] = useState(proposal.don_gia === null ? "" : String(proposal.don_gia));
  const [soTien, setSoTien] = useState(String(proposal.so_tien));
  const [status, setStatus] = useState<Status>("idle");
  const [savedNo, setSavedNo] = useState("");
  const [error, setError] = useState<string | null>(null);

  // Sửa số lượng/đơn giá thì tự tính lại tổng tiền (giống form sửa phiếu); tổng tiền vẫn sửa tay được.
  function recompute(nextQty: string, nextPrice: string) {
    if (nextQty === "" || nextPrice === "") return;
    const q = Number(nextQty);
    const p = Number(nextPrice);
    if (!Number.isNaN(q) && !Number.isNaN(p)) setSoTien(String(q * p));
  }

  async function save() {
    const tien = Number(soTien);
    const qty = soLuong === "" ? null : Number(soLuong);
    const price = donGia === "" ? null : Number(donGia);
    if (!sellerId) return setError("Chọn người bán trước khi lưu");
    if (!ngay) return setError("Chọn ngày lập phiếu");
    if (!lyDo.trim()) return setError("Nhập lý do chi");
    if (qty !== null && (Number.isNaN(qty) || qty < 0)) return setError("Số lượng không hợp lệ");
    if (price !== null && (Number.isNaN(price) || price < 0)) return setError("Đơn giá không hợp lệ");
    if (soTien === "" || Number.isNaN(tien) || tien <= 0) return setError("Số tiền phải lớn hơn 0");

    setStatus("saving");
    setError(null);
    try {
      const v = await api.post<Voucher>("/vouchers/", {
        seller_id: sellerId,
        ngay,
        ly_do_chi: lyDo.trim(),
        so_tien: tien,
        so_luong: qty,
        don_gia: price,
      });
      setSavedNo(v.so_phieu);
      setStatus("saved");
      showToast("success", `Đã lưu nháp phiếu ${v.so_phieu}`);
    } catch (e) {
      setStatus("idle");
      setError(e instanceof ApiError ? e.message : "Không lưu được phiếu");
    }
  }

  if (status === "dismissed") return <div className="proposal proposal--dismissed">Đã bỏ đề xuất.</div>;
  if (status === "saved") {
    return (
      <div className="proposal proposal--done">
        <div className="proposal__done-row">
          <span className="status-seal status-seal--signed">Đã lưu nháp</span>
          <span>
            Phiếu <strong className="num">{savedNo}</strong> đã tạo (chờ Giám đốc duyệt trước khi in).
          </span>
        </div>
        <Link to="/vouchers" onClick={onNavigate} className="proposal__done-link">
          Xem phiếu chi →
        </Link>
      </div>
    );
  }

  const parsedTien = Number(soTien);
  const formattedTien = soTien !== "" && !Number.isNaN(parsedTien) && parsedTien > 0 ? `${Math.round(parsedTien).toLocaleString("vi-VN")} đ` : null;
  const qtyNum = soLuong === "" ? null : Number(soLuong);
  const priceNum = donGia === "" ? null : Number(donGia);
  const manualDiff =
    qtyNum !== null &&
    priceNum !== null &&
    !Number.isNaN(qtyNum) &&
    !Number.isNaN(priceNum) &&
    !Number.isNaN(parsedTien) &&
    Math.round(qtyNum * priceNum) !== Math.round(parsedTien);

  return (
    <div className="proposal">
      <div className="proposal__head">
        <span>Đề xuất phiếu chi nháp</span>
        <span className="status-seal status-seal--pending_signature">Chưa lưu</span>
      </div>
      {proposal.warnings.map((w) => (
        <div key={w} className="proposal__warn">
          <span aria-hidden="true">⚠ </span>
          {w}
        </div>
      ))}
      <div className="proposal__grid">
        <div className="field proposal__full">
          <label htmlFor={`${uid}-seller`}>Người bán</label>
          <SearchableSelect
            id={`${uid}-seller`}
            options={sellers.map((s) => ({ value: s.id, label: s.name }))}
            value={sellerId}
            onChange={(val) => {
              setSellerId(val);
              setError(null);
            }}
            placeholder={proposal.seller_name ? `Tìm (${proposal.seller_name})…` : "Chọn người bán…"}
          />
          {sellersLoadFailed && sellers.length === 0 && (
            <div className="field-error">
              Chưa tải được danh sách người bán{proposal.seller_name ? ` (${proposal.seller_name})` : ""} — bấm Ctrl+K mở lại để thử.
            </div>
          )}
        </div>
        <div className="field">
          <label htmlFor={`${uid}-date`}>Ngày</label>
          <input
            id={`${uid}-date`}
            type="date"
            value={ngay}
            onChange={(e) => {
              setNgay(e.target.value);
              setError(null);
            }}
          />
        </div>
        <div className="field">
          <label htmlFor={`${uid}-reason`}>Lý do chi</label>
          <input
            id={`${uid}-reason`}
            value={lyDo}
            onChange={(e) => {
              setLyDo(e.target.value);
              setError(null);
            }}
          />
        </div>
        <div className="field">
          <label htmlFor={`${uid}-qty`}>Số lượng (kg)</label>
          <input
            id={`${uid}-qty`}
            className="num"
            type="number"
            step="any"
            min="0"
            value={soLuong}
            onChange={(e) => {
              setSoLuong(e.target.value);
              recompute(e.target.value, donGia);
              setError(null);
            }}
          />
        </div>
        <div className="field">
          <label htmlFor={`${uid}-price`}>Đơn giá</label>
          <input
            id={`${uid}-price`}
            className="num"
            type="number"
            step="any"
            min="0"
            value={donGia}
            onChange={(e) => {
              setDonGia(e.target.value);
              recompute(soLuong, e.target.value);
              setError(null);
            }}
          />
        </div>
        <div className="field proposal__full">
          <div className="proposal__label-row">
            <label htmlFor={`${uid}-total`}>Số tiền (đồng)</label>
            <span className="proposal__amount-preview num">
              {formattedTien && <><strong>= {formattedTien}</strong></>}
              {manualDiff && <span className="proposal__diff-note"> · đã sửa tay khác SL × ĐG</span>}
            </span>
          </div>
          <input
            id={`${uid}-total`}
            className="num"
            type="number"
            step="any"
            min="0"
            value={soTien}
            onChange={(e) => {
              setSoTien(e.target.value);
              setError(null);
            }}
          />
        </div>
      </div>
      {error && (
        <div className="proposal__error" role="alert">
          {error}
        </div>
      )}
      <div className="proposal__actions">
        <button type="button" className="btn btn--ghost" onClick={() => setStatus("dismissed")} disabled={status === "saving"}>
          Bỏ
        </button>
        <button type="button" className="btn btn--primary" onClick={save} disabled={status === "saving"}>
          {status === "saving" ? "Đang lưu…" : "Lưu nháp"}
        </button>
      </div>
    </div>
  );
}
