import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type { DashboardSummary, TopSeller } from "../api/types";
import { AlertsPanel } from "../components/AlertsPanel";

function currentMonthYear() {
  const now = new Date();
  return { month: now.getMonth() + 1, year: now.getFullYear() };
}

type SortKey = "tong_tien" | "tong_so_luong" | "so_phieu";

const PRESET_MONTHS = [1, 3, 6, 12];

export function DashboardPage() {
  const initial = currentMonthYear();
  const [month, setMonth] = useState(initial.month);
  const [year, setYear] = useState(initial.year);
  const [months, setMonths] = useState<number>(1);
  const [data, setData] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState<SortKey>("tong_tien");

  useEffect(() => {
    let cancelled = false;
    const validMonths = Math.max(1, Math.min(60, Number(months) || 1));
    setLoading(true);
    setError(null);
    api
      .get<DashboardSummary>(`/reports/dashboard?month=${month}&year=${year}&months=${validMonths}`)
      .then((res) => {
        if (!cancelled) setData(res);
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof ApiError ? e.message : "Không tải được dữ liệu tổng quan");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [month, year, months]);

  function shiftMonth(delta: number) {
    let nextMonth = month + delta;
    let nextYear = year;
    if (nextMonth < 1) {
      nextMonth = 12;
      nextYear -= 1;
    } else if (nextMonth > 12) {
      nextMonth = 1;
      nextYear += 1;
    }
    setMonth(nextMonth);
    setYear(nextYear);
  }

  const periodLabel = useMemo(() => {
    if (!data || (data.months ?? 1) <= 1) {
      return `Tháng ${month}/${year}`;
    }
    return `${data.months} tháng (${data.tu_thang} – ${data.den_thang})`;
  }, [data, month, year]);

  const rankedSellers = useMemo(() => {
    const list: TopSeller[] = data?.top_nguoi_ban ?? [];
    const q = search.trim().toLowerCase();
    const filtered = q
      ? list.filter(
          (s) =>
            s.seller_name.toLowerCase().includes(q) ||
            (s.id_card_number ?? "").toLowerCase().includes(q) ||
            (s.phone ?? "").toLowerCase().includes(q) ||
            (s.address ?? "").toLowerCase().includes(q)
        )
      : list;

    return [...filtered].sort((a, b) => (b[sortBy] ?? 0) - (a[sortBy] ?? 0));
  }, [data, search, sortBy]);

  const maxMetric = useMemo(() => {
    if (rankedSellers.length === 0) return 0;
    return Math.max(...rankedSellers.map((s) => s[sortBy] ?? 0), 0);
  }, [rankedSellers, sortBy]);

  const filteredTotalMoney = useMemo(
    () => rankedSellers.reduce((acc, s) => acc + (s.tong_tien ?? 0), 0),
    [rankedSellers]
  );
  const filteredTotalQty = useMemo(
    () => rankedSellers.reduce((acc, s) => acc + (s.tong_so_luong ?? 0), 0),
    [rankedSellers]
  );
  const filteredTotalVouchers = useMemo(
    () => rankedSellers.reduce((acc, s) => acc + (s.so_phieu ?? 0), 0),
    [rankedSellers]
  );

  const activeMonthsSpan = Math.max(1, data?.months ?? months ?? 1);

  return (
    <div>
      <div className="page-header" style={{ marginBottom: 16 }}>
        <div>
          <div className="page-header__eyebrow">Báo cáo thu mua &amp; hợp đồng · {periodLabel}</div>
          <h1 style={{ marginBottom: 0 }}>Tổng quan &amp; Xếp hạng người bán</h1>
        </div>

        <div className="toolbar" style={{ marginBottom: 0, gap: 8 }}>
          {/* Bộ chọn số tháng gộp */}
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 4,
              background: "var(--color-paper-raised)",
              border: "1px solid var(--color-rule)",
              borderRadius: "var(--radius-sm)",
              padding: "3px 6px",
            }}
          >
            <span style={{ fontSize: "0.78rem", color: "var(--color-ink-soft)", padding: "0 4px", fontWeight: 600 }}>
              Kỳ gộp:
            </span>
            {PRESET_MONTHS.map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => setMonths(m)}
                className={months === m ? "btn btn--primary" : "btn btn--ghost"}
                style={{
                  padding: "4px 8px",
                  fontSize: "0.8rem",
                  border: months === m ? "none" : "1px solid transparent",
                }}
              >
                {m}T
              </button>
            ))}
            <input
              aria-label="Số tháng tuỳ chọn"
              type="number"
              min={1}
              max={60}
              className="num"
              value={months}
              onChange={(e) => {
                const v = parseInt(e.target.value, 10);
                setMonths(Number.isNaN(v) ? 1 : Math.max(1, Math.min(60, v)));
              }}
              title="Nhập số tháng muốn gộp (1 đến 60 tháng)"
              style={{
                width: 54,
                height: 28,
                padding: "2px 6px",
                fontSize: "0.82rem",
                border: "1px solid var(--color-rule)",
                borderRadius: "var(--radius-sm)",
                textAlign: "right",
              }}
            />
            <span style={{ fontSize: "0.78rem", color: "var(--color-ink-soft)", paddingRight: 4 }}>tháng</span>
          </div>

          {/* Bộ chọn tháng/năm kết thúc */}
          <button
            type="button"
            className="btn btn--ghost"
            onClick={() => shiftMonth(-1)}
            title="Lùi 1 tháng"
            style={{ padding: "7px 10px" }}
          >
            ‹
          </button>
          <div className="field" style={{ margin: 0 }}>
            <select
              aria-label="Chọn tháng kết thúc"
              value={month}
              onChange={(e) => setMonth(Number(e.target.value))}
              style={{ height: 36, padding: "4px 10px" }}
            >
              {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
                <option key={m} value={m}>
                  Đến tháng {m}
                </option>
              ))}
            </select>
          </div>
          <div className="field" style={{ margin: 0 }}>
            <input
              aria-label="Chọn năm"
              type="number"
              className="num"
              value={year}
              onChange={(e) => setYear(Number(e.target.value))}
              style={{ width: 88, height: 36, padding: "4px 10px" }}
            />
          </div>
          <button
            type="button"
            className="btn btn--ghost"
            onClick={() => shiftMonth(1)}
            title="Tiến 1 tháng"
            style={{ padding: "7px 10px" }}
          >
            ›
          </button>
        </div>
      </div>

      {error && <div className="banner banner--error">{error}</div>}

      {loading && !data ? (
        <div className="card num" style={{ color: "var(--color-ink-soft)" }}>
          Đang tải số liệu…
        </div>
      ) : data ? (
        <>
          <div className="stat-grid">
            <div className="stat-card">
              <div className="stat-card__label">
                {activeMonthsSpan > 1 ? `Tổng chi (${data.tu_thang} – ${data.den_thang})` : `Tổng chi tháng ${data.month}/${data.year}`}
              </div>
              <div className="stat-card__value num">{(data.tong_chi_thang_nay ?? 0).toLocaleString("vi-VN")} đ</div>
            </div>
            <div className="stat-card">
              <div className="stat-card__label">Số người bán phát sinh</div>
              <div className="stat-card__value num">{data.top_nguoi_ban.length}</div>
            </div>
            <div className="stat-card">
              <div className="stat-card__label">Số phiếu chi trong kỳ</div>
              <div className="stat-card__value num">{data.so_phieu_thang_nay}</div>
            </div>
            <div className={"stat-card" + (data.so_phieu_cho_duyet > 0 ? " stat-card--warn" : "")}>
              <div className="stat-card__label">Phiếu chờ duyệt</div>
              <div className="stat-card__value num">{data.so_phieu_cho_duyet}</div>
            </div>
            <div className={"stat-card" + (data.so_phieu_cho_ky_qua_han > 0 ? " stat-card--alert" : "")}>
              <div className="stat-card__label">Chờ ký &gt; 5 ngày</div>
              <div className="stat-card__value num">{data.so_phieu_cho_ky_qua_han}</div>
            </div>
            <div className={"stat-card" + (data.cong_no_phai_thu > 0 ? " stat-card--warn" : "")}>
              <div className="stat-card__label">Công nợ phải thu</div>
              <div className="stat-card__value num">{(data.cong_no_phai_thu ?? 0).toLocaleString("vi-VN")} đ</div>
            </div>
          </div>

          {data.so_phieu_cho_ky_qua_han > 0 && (
            <div className="banner banner--warn">
              Có {data.so_phieu_cho_ky_qua_han} phiếu đã duyệt hơn 5 ngày nhưng chưa có ảnh ký — nên kiểm tra lại.{" "}
              <Link to="/vouchers">Xem danh sách phiếu →</Link>
            </div>
          )}
          {data.so_hoa_don_cho_thu > 0 && (
            <div className="banner banner--info">
              Có {data.so_hoa_don_cho_thu} hoá đơn đã xuất nhưng chưa thu tiền.{" "}
              <Link to="/sales-invoices">Xem hoá đơn bán ra →</Link>
            </div>
          )}

          <AlertsPanel />

          <div className="card" style={{ padding: 20 }}>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "flex-end",
                gap: 12,
                flexWrap: "wrap",
                marginBottom: 16,
              }}
            >
              <div>
                <h2 style={{ margin: 0, fontSize: "1.15rem" }}>
                  Bảng xếp hạng người bán theo phiếu chi — {periodLabel}
                </h2>
                <div style={{ fontSize: "0.82rem", color: "var(--color-ink-soft)", marginTop: 2 }}>
                  Tổng hợp phiếu chi hợp lệ (không tính phiếu đã huỷ) trong {activeMonthsSpan} tháng để đánh giá sản lượng, doanh số trung bình và ký hợp đồng.
                </div>
              </div>

              <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                <div className="field" style={{ margin: 0 }}>
                  <input
                    placeholder="Tìm tên, CCCD, SĐT, địa chỉ…"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    style={{ width: 220, height: 34, padding: "4px 10px", fontSize: "0.86rem" }}
                  />
                </div>
                <div className="field" style={{ margin: 0 }}>
                  <select
                    aria-label="Sắp xếp theo"
                    value={sortBy}
                    onChange={(e) => setSortBy(e.target.value as SortKey)}
                    style={{ height: 34, padding: "4px 10px", fontSize: "0.86rem" }}
                  >
                    <option value="tong_tien">Xếp theo: Tổng tiền cao nhất</option>
                    <option value="tong_so_luong">Xếp theo: Sản lượng cao nhất</option>
                    <option value="so_phieu">Xếp theo: Số phiếu nhiều nhất</option>
                  </select>
                </div>
                <Link
                  to={`/export`}
                  className="btn btn--ghost"
                  style={{ height: 34, padding: "4px 12px", fontSize: "0.84rem", textDecoration: "none" }}
                >
                  Xuất bảng kê / phiếu gom →
                </Link>
              </div>
            </div>

            {rankedSellers.length === 0 ? (
              <div className="empty-state">
                {data.top_nguoi_ban.length === 0
                  ? `Chưa có phiếu chi nào trong kỳ ${periodLabel}.`
                  : "Không tìm thấy người bán nào khớp với từ khoá lọc."}
              </div>
            ) : (
              <div style={{ overflowX: "auto" }}>
                <table>
                  <thead>
                    <tr>
                      <th style={{ width: 48 }}>Hạng</th>
                      <th>Người bán &amp; Địa chỉ</th>
                      <th>Hồ sơ ký HĐ (CCCD / SĐT)</th>
                      <th style={{ textAlign: "right", width: 90 }}>Số phiếu</th>
                      {activeMonthsSpan > 1 && <th style={{ textAlign: "right", width: 105 }}>Tháng bán</th>}
                      <th style={{ textAlign: "right", width: 120 }}>Tổng sản lượng</th>
                      <th style={{ textAlign: "right", width: 155 }}>Tổng tiền bán</th>
                      {activeMonthsSpan > 1 && <th style={{ textAlign: "right", width: 145 }}>TB / tháng</th>}
                      <th style={{ width: 175 }}>Tỷ trọng kỳ</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rankedSellers.map((s, idx) => {
                      const sharePct =
                        data.tong_chi_thang_nay > 0 ? (s.tong_tien / data.tong_chi_thang_nay) * 100 : 0;
                      const barWidthPct = maxMetric > 0 ? Math.max(2, ((s[sortBy] ?? 0) / maxMetric) * 100) : 0;
                      const hasIdCard = Boolean(s.id_card_number && s.id_card_number.trim());
                      const avgPerMonth = Math.round(s.tong_tien / activeMonthsSpan);

                      return (
                        <tr key={s.seller_id}>
                          <td className="num" style={{ fontWeight: idx < 3 ? 700 : 500, color: idx < 3 ? "var(--color-accent)" : "var(--color-ink-soft)" }}>
                            #{idx + 1}
                          </td>
                          <td>
                            <div style={{ fontWeight: 600 }}>{s.seller_name}</div>
                            {s.address && (
                              <div style={{ fontSize: "0.78rem", color: "var(--color-ink-soft)" }}>{s.address}</div>
                            )}
                          </td>
                          <td>
                            {hasIdCard ? (
                              <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                                <span className="num" style={{ fontFamily: "monospace", fontSize: "0.86rem", fontWeight: 600 }}>
                                  CCCD: {s.id_card_number}
                                </span>
                                {s.phone && (
                                  <span className="num" style={{ fontSize: "0.78rem", color: "var(--color-ink-soft)" }}>
                                    SĐT: {s.phone}
                                  </span>
                                )}
                              </div>
                            ) : (
                              <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                                <span className="status-seal status-seal--pending_signature">Thiếu CCCD</span>
                                <Link to="/sellers" style={{ fontSize: "0.78rem" }}>
                                  Bổ sung →
                                </Link>
                              </div>
                            )}
                          </td>
                          <td className="num" style={{ textAlign: "right" }}>
                            {s.so_phieu}
                          </td>
                          {activeMonthsSpan > 1 && (
                            <td className="num" style={{ textAlign: "right", color: "var(--color-ink-soft)" }}>
                              {s.so_thang_phat_sinh ?? 1}/{activeMonthsSpan} tháng
                            </td>
                          )}
                          <td className="num" style={{ textAlign: "right" }}>
                            {(s.tong_so_luong ?? 0) > 0
                              ? (s.tong_so_luong ?? 0).toLocaleString("vi-VN", { maximumFractionDigits: 2 })
                              : "—"}
                          </td>
                          <td className="num" style={{ textAlign: "right", fontWeight: 600 }}>
                            {s.tong_tien.toLocaleString("vi-VN")} đ
                          </td>
                          {activeMonthsSpan > 1 && (
                            <td className="num" style={{ textAlign: "right", color: "var(--color-ink-soft)" }}>
                              {avgPerMonth.toLocaleString("vi-VN")} đ
                            </td>
                          )}
                          <td>
                            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                              <div
                                style={{
                                  flex: 1,
                                  height: 8,
                                  background: "var(--color-rule)",
                                  borderRadius: 4,
                                  overflow: "hidden",
                                }}
                              >
                                <div
                                  style={{
                                    width: `${barWidthPct}%`,
                                    height: "100%",
                                    background: idx === 0 ? "var(--color-accent)" : "var(--color-primary)",
                                  }}
                                />
                              </div>
                              <span
                                className="num"
                                style={{
                                  width: 48,
                                  textAlign: "right",
                                  fontSize: "0.8rem",
                                  color: "var(--color-ink-soft)",
                                }}
                              >
                                {sharePct.toFixed(1)}%
                              </span>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                  <tfoot>
                    <tr style={{ borderTop: "1.5px solid var(--color-rule-strong)", fontWeight: 600 }}>
                      <td colSpan={3}>
                        Tổng cộng ({rankedSellers.length} người bán)
                      </td>
                      <td className="num" style={{ textAlign: "right" }}>
                        {filteredTotalVouchers}
                      </td>
                      {activeMonthsSpan > 1 && (
                        <td className="num" style={{ textAlign: "right", color: "var(--color-ink-soft)" }}>
                          {activeMonthsSpan} tháng
                        </td>
                      )}
                      <td className="num" style={{ textAlign: "right" }}>
                        {filteredTotalQty > 0
                          ? filteredTotalQty.toLocaleString("vi-VN", { maximumFractionDigits: 2 })
                          : "—"}
                      </td>
                      <td className="num" style={{ textAlign: "right", color: "var(--color-primary)" }}>
                        {filteredTotalMoney.toLocaleString("vi-VN")} đ
                      </td>
                      {activeMonthsSpan > 1 && (
                        <td className="num" style={{ textAlign: "right", color: "var(--color-ink-soft)" }}>
                          {Math.round(filteredTotalMoney / activeMonthsSpan).toLocaleString("vi-VN")} đ
                        </td>
                      )}
                      <td className="num" style={{ textAlign: "right", fontSize: "0.82rem", color: "var(--color-ink-soft)" }}>
                        {data.tong_chi_thang_nay > 0
                          ? `${((filteredTotalMoney / data.tong_chi_thang_nay) * 100).toFixed(1)}% kỳ`
                          : "0.0%"}
                      </td>
                    </tr>
                  </tfoot>
                </table>
              </div>
            )}
          </div>
        </>
      ) : null}
    </div>
  );
}
