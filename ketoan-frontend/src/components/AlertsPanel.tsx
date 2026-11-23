import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { AgentAlert } from "../api/types";

type LoadState = "loading" | "ready" | "error";

const DEFAULT_VISIBLE = 4;

const TYPE_LABELS: Record<string, string> = {
  receivable_overdue: "Nợ quá hạn",
  price_anomaly: "Giá bất thường",
  seller_missing_id: "Thiếu CCCD",
};

/**
 * Cảnh báo chủ động: server quét giá lệch / công nợ quá hạn / thiếu CCCD bằng quy tắc xác định.
 * Lỗi tải không được làm hỏng cả Dashboard; giữ trạng thái gọn để tránh nhảy bố cục.
 */
export function AlertsPanel() {
  const [alerts, setAlerts] = useState<AgentAlert[]>([]);
  const [status, setStatus] = useState<LoadState>("loading");
  const [expanded, setExpanded] = useState(false);
  const reqId = useRef(0);

  const load = useCallback((isActive?: () => boolean) => {
    const id = ++reqId.current;
    setStatus("loading");
    api
      .get<AgentAlert[]>("/agent/alerts")
      .then((a) => {
        if ((isActive && !isActive()) || id !== reqId.current) return;
        setAlerts(a);
        setStatus("ready");
      })
      .catch(() => {
        if ((isActive && !isActive()) || id !== reqId.current) return;
        setAlerts([]);
        setStatus("error");
      });
  }, []);

  useEffect(() => {
    let active = true;
    load(() => active);
    return () => {
      active = false;
    };
  }, [load]);

  if (status === "loading") {
    return (
      <div className="alerts-strip" role="status" aria-live="polite">
        <span className="cmdbar__dots" aria-hidden="true"><span /><span /><span /></span>
        <span>Đang rà soát giá thu mua, công nợ quá hạn &amp; hồ sơ CCCD…</span>
      </div>
    );
  }

  if (status === "error") {
    return (
      <div className="alerts-strip alerts-strip--error" role="status">
        <span>Không kiểm tra được cảnh báo tự động.</span>
        <button type="button" className="btn btn--ghost alerts__btn" onClick={() => load()}>
          Thử lại
        </button>
      </div>
    );
  }

  if (alerts.length === 0) {
    return (
      <div className="alerts-strip alerts-strip--ok" role="status">
        <span className="alerts__ok-mark" aria-hidden="true">✓</span>
        <span>Giám sát tự động: chưa phát hiện đơn giá lệch, công nợ quá 30 ngày hay thiếu CCCD.</span>
      </div>
    );
  }

  const sorted = [...alerts].sort((a, b) => (a.severity === "alert" ? 0 : 1) - (b.severity === "alert" ? 0 : 1));
  const urgentCount = alerts.filter((a) => a.severity === "alert").length;
  const warnCount = alerts.length - urgentCount;
  const visible = expanded ? sorted : sorted.slice(0, DEFAULT_VISIBLE);
  const remaining = alerts.length - DEFAULT_VISIBLE;

  return (
    <section className="card alerts" aria-label="Cảnh báo giám sát tự động">
      <div className="alerts__head">
        <div>
          <h3 className="alerts__heading">Cần chú ý ({alerts.length})</h3>
          <div className="alerts__sub">Rà soát tự động 30–90 ngày gần nhất</div>
        </div>
        <div className="alerts__counts">
          {urgentCount > 0 && <span className="alerts__tag alerts__tag--alert">{urgentCount} khẩn</span>}
          {warnCount > 0 && <span className="alerts__tag alerts__tag--warn">{warnCount} lưu ý</span>}
        </div>
      </div>

      <ul className="alerts__list">
        {visible.map((a, i) => (
          <li key={`${a.type}-${a.title}-${i}`} className={`alerts__item alerts__item--${a.severity}`}>
            <div className="alerts__content">
              <div className="alerts__meta">
                <span className={`alerts__tag alerts__tag--${a.severity}`}>
                  {TYPE_LABELS[a.type] ?? (a.severity === "alert" ? "Khẩn" : "Lưu ý")}
                </span>
              </div>
              <div className="alerts__title">{a.title}</div>
              <div className="alerts__detail">{a.detail}</div>
            </div>
            <Link to={a.link} className="btn btn--ghost alerts__action">
              Xem →
            </Link>
          </li>
        ))}
      </ul>

      {remaining > 0 && (
        <div className="alerts__foot">
          <button type="button" className="alerts__more" onClick={() => setExpanded((v) => !v)}>
            {expanded ? "Thu gọn danh sách" : `Xem thêm ${remaining} cảnh báo khác`}
          </button>
        </div>
      )}
    </section>
  );
}
