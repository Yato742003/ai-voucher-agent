import { useEffect, useId, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type { AgentChatResponse, AgentHistoryMessage, AgentProposal, Seller } from "../api/types";
import { ProposalCard } from "./ProposalCard";

interface Turn {
  role: "user" | "assistant";
  text: string;
  error?: boolean;
  proposals?: AgentProposal[];
}

const SUGGESTIONS = [
  "Tháng này chi bao nhiêu?",
  "Ai còn nợ mình?",
  "Mua 500kg mủ anh Kiếm giá 15.000",
  "Giá mua mủ 3 tháng gần đây thế nào?",
];

const PAGE_LABELS: Record<string, string> = {
  "/dashboard": "Tổng quan",
  "/vouchers": "Phiếu chi",
  "/scan-import": "Scan bảng kê",
  "/scan-history": "Lịch sử scan",
  "/sellers": "Người bán",
  "/customers": "Khách hàng",
  "/sales-invoices": "Hoá đơn bán",
  "/export": "Xuất file",
  "/settings": "Cài đặt",
};

/**
 * Thanh lệnh Ctrl+K — không phải khung chat tán gẫu: câu trả lời là số liệu ngắn hoặc
 * thẻ đề xuất sửa được. Biết trang đang mở (gửi kèm pathname) nên "ở đây" có nghĩa.
 */
export function CommandBar({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const location = useLocation();
  const titleId = useId();
  const [input, setInput] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [history, setHistory] = useState<AgentHistoryMessage[]>([]);
  const [busy, setBusy] = useState(false);
  const [sellers, setSellers] = useState<Seller[]>([]);
  const [sellersError, setSellersError] = useState(false);
  const requestId = useRef(0); // chặn phản hồi cũ ghi đè sau khi người dùng đã xoá/đổi hội thoại
  const dialogRef = useRef<HTMLDialogElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        onOpenChange(!open);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onOpenChange]);

  // <dialog> modal gốc lo focus trap, Esc, inert, trả focus về nút gọi — chỉ đồng bộ state ↔ DOM.
  useEffect(() => {
    const d = dialogRef.current;
    if (!d) return;
    if (open && !d.open) {
      d.showModal();
      inputRef.current?.focus(); // mặc định showModal focus nút đầu tiên, ta muốn ô nhập
    } else if (!open && d.open) d.close();
  }, [open]);

  useEffect(() => {
    if (!open || sellers.length > 0) return;
    api
      .get<Seller[]>("/sellers/")
      .then((list) => {
        setSellers(list);
        setSellersError(false);
      })
      .catch(() => setSellersError(true)); // chỉ để chọn người bán trong thẻ đề xuất
  }, [open, sellers.length]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "end" });
  }, [turns, busy]);

  async function send(text: string) {
    const message = text.trim();
    if (!message || busy) return;
    const myId = ++requestId.current;
    setTurns((t) => [...t, { role: "user", text: message }]);
    setInput("");
    setBusy(true);
    try {
      const res = await api.post<AgentChatResponse>("/agent/chat", { message, history, context: location.pathname });
      if (myId !== requestId.current) return;
      setHistory(res.history);
      setTurns((t) => [...t, { role: "assistant", text: res.reply, proposals: res.proposals }]);
    } catch (e) {
      if (myId !== requestId.current) return;
      setTurns((t) => [
        ...t,
        { role: "assistant", text: e instanceof ApiError ? e.message : "Không gọi được trợ lý", error: true },
      ]);
    } finally {
      if (myId === requestId.current) setBusy(false);
    }
  }

  function clear() {
    requestId.current++;
    setTurns([]);
    setHistory([]);
    setBusy(false);
    inputRef.current?.focus();
  }

  const pageLabel = PAGE_LABELS[location.pathname];

  return (
    <dialog
      ref={dialogRef}
      className="cmdbar"
      aria-labelledby={titleId}
      {...({ closedby: "any" } as object)}
      onClose={() => onOpenChange(false)}
    >
        <div className="cmdbar__head">
          <div className="cmdbar__title-group">
            <span aria-hidden="true" className="cmdbar__spark">✦</span>
            <h2 id={titleId} className="cmdbar__title">Trợ lý kế toán</h2>
            {pageLabel && <span className="cmdbar__ctx">Tại: {pageLabel}</span>}
          </div>
          <div className="cmdbar__head-actions">
            <button type="button" className="btn btn--ghost cmdbar__btn-sm" onClick={clear} disabled={turns.length === 0}>
              Xoá
            </button>
            <button
              type="button"
              className="btn btn--ghost cmdbar__btn-sm"
              onClick={() => onOpenChange(false)}
              aria-label="Đóng trợ lý"
              title="Đóng (Esc)"
            >
              ✕
            </button>
          </div>
        </div>

        <form
          className="cmdbar__top"
          onSubmit={(e) => {
            e.preventDefault();
            send(input);
          }}
        >
          <input
            ref={inputRef}
            className="cmdbar__input"
            aria-label="Nhập câu hỏi hoặc lệnh kế toán"
            placeholder="Hỏi số liệu hoặc ra lệnh: “mua 500kg mủ anh Kiếm giá 15.000”"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            readOnly={busy}
            aria-busy={busy}
          />
          <button type="submit" className="btn btn--primary cmdbar__send" disabled={busy || !input.trim()}>
            {busy ? "Đang xử lý…" : "Gửi"}
          </button>
        </form>

        <div className="cmdbar__body" aria-live="polite">
          {turns.length === 0 && (
            <div className="cmdbar__empty">
              <div>Trợ lý chỉ tra cứu số liệu và soạn nháp — chỉ lưu khi bạn bấm <strong>Lưu nháp</strong>.</div>
              <div className="cmdbar__hint">Gợi ý hỏi nhanh:</div>
              <div className="cmdbar__chips">
                {SUGGESTIONS.map((s) => (
                  <button key={s} type="button" className="cmdbar__chip" onClick={() => send(s)}>
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {turns.map((t, i) => (
            <div key={i} className={`cmdbar__turn cmdbar__turn--${t.role}`}>
              {t.text && (
                <div className={t.error ? "cmdbar__text cmdbar__text--error" : "cmdbar__text"} role={t.error ? "alert" : undefined}>
                  {t.text}
                </div>
              )}
              {t.proposals?.map((p, j) => (
                <ProposalCard
                  key={j}
                  proposal={p}
                  sellers={sellers}
                  sellersLoadFailed={sellersError}
                  onNavigate={() => onOpenChange(false)}
                />
              ))}
            </div>
          ))}
          {busy && (
            <div className="cmdbar__turn cmdbar__turn--assistant">
              <div className="cmdbar__text cmdbar__text--muted cmdbar__loading">
                <span className="cmdbar__dots" aria-hidden="true"><span /><span /><span /></span>
                <span>Đang tra cứu dữ liệu…</span>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        <div className="cmdbar__foot">
          <span><kbd>Enter</kbd> gửi</span>
          <span><kbd>Esc</kbd> đóng</span>
          <span><kbd>Ctrl</kbd>+<kbd>K</kbd> bật/tắt</span>
        </div>
    </dialog>
  );
}
