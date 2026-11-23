import { useState } from "react";
import { NavLink, Outlet, Navigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import { CommandBar } from "./CommandBar";

const NAV_ITEMS = [
  { to: "/dashboard", label: "Tổng quan", icon: "📊" },
  { to: "/vouchers", label: "Phiếu chi", icon: "💸" },
  { to: "/scan-import",  label: "Scan bảng kê", icon: "📷" },
  { to: "/scan-history", label: "Lịch sử scan", icon: "📜", indent: true },
  { to: "/sellers", label: "Người bán", icon: "🤝" },
  { to: "/customers", label: "Khách hàng", icon: "👥" },
  { to: "/sales-invoices", label: "Hoá đơn bán", icon: "🧾" },
  { to: "/export", label: "Xuất file", icon: "📥" },
  { to: "/settings", label: "Cài đặt", icon: "⚙️" },
];

export function Layout() {
  const { user, loading, logout } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [cmdOpen, setCmdOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(() => {
    return localStorage.getItem("sidebar_collapsed") === "true";
  });

  if (loading) return null;
  if (!user) return <Navigate to="/login" replace />;

  const toggleCollapse = () => {
    setCollapsed((prev) => {
      const next = !prev;
      localStorage.setItem("sidebar_collapsed", String(next));
      return next;
    });
  };

  return (
    <div className="app-shell">
      <aside className={`sidebar${collapsed ? " sidebar--collapsed" : ""}`}>
        <div className="sidebar__brand" style={{ display: "flex", flexDirection: "column", alignItems: collapsed ? "center" : "flex-start" }}>
          {collapsed ? (
            <span style={{ fontSize: "1.35rem" }} title="Sổ Kế Toán">📖</span>
          ) : (
            <>
              Sổ Kế Toán
              <small>Quản lý phiếu chi nội bộ</small>
            </>
          )}
        </div>
        <button className="sidebar__toggle" onClick={() => setMobileOpen((v) => !v)} aria-label="Mở menu">
          {mobileOpen ? "Đóng ✕" : "Menu ☰"}
        </button>
        <nav className={"sidebar__nav" + (mobileOpen ? " sidebar__nav--open" : "")}>
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              onClick={() => setMobileOpen(false)}
              title={collapsed ? item.label : undefined}
              className={({ isActive }) => "sidebar__link" + (isActive ? " sidebar__link--active" : "")}
              style={{
                display: "flex",
                alignItems: "center",
                gap: collapsed ? 0 : 10,
                justifyContent: collapsed ? "center" : "flex-start",
                padding: collapsed ? "12px 0" : "9px 12px",
              }}
            >
              <span style={{ fontSize: "1.1rem" }}>{item.icon}</span>
              {!collapsed && (
                <span>{item.indent ? `↳ ${item.label}` : item.label}</span>
              )}
            </NavLink>
          ))}
        </nav>

        <button
          type="button"
          onClick={() => setCmdOpen(true)}
          className="sidebar__collapse-btn sidebar__cmd-btn"
          title="Trợ lý kế toán (Ctrl+K)"
          aria-haspopup="dialog"
          aria-expanded={cmdOpen}
        >
          <span aria-hidden="true">✦</span>
          {!collapsed && <span>Trợ lý <kbd className="sidebar__kbd">Ctrl K</kbd></span>}
        </button>
        
        {/* Nút thu gọn / mở rộng menu */}
        <button
          type="button"
          onClick={toggleCollapse}
          className="sidebar__collapse-btn sidebar__collapse-toggle"
          title={collapsed ? "Mở rộng menu" : "Thu gọn menu"}
        >
          <span aria-hidden="true">{collapsed ? "▶" : "◀"}</span>
          {!collapsed && <span>Thu gọn</span>}
        </button>

        <div className={"sidebar__footer" + (mobileOpen ? " sidebar__footer--open" : "")} style={{ textAlign: collapsed ? "center" : "left" }}>
          {!collapsed ? (
            <>
              {user.full_name}
              <br />
              <span style={{ opacity: 0.7 }}>{roleLabel(user.role_name)}</span>
              <br />
              <button className="sidebar__signout" onClick={logout}>
                Đăng xuất
              </button>
            </>
          ) : (
            <button className="sidebar__signout" onClick={logout} title="Đăng xuất" style={{ fontSize: "1.2rem", padding: "4px 0", cursor: "pointer", background: "none", border: "none", color: "inherit" }}>
              🚪
            </button>
          )}
        </div>
      </aside>
      <main className="main">
        <Outlet />
      </main>
      <CommandBar open={cmdOpen} onOpenChange={setCmdOpen} />
    </div>
  );
}

function roleLabel(role: string): string {
  const map: Record<string, string> = {
    giam_doc: "Giám đốc",
    ke_toan: "Kế toán",
    thu_quy: "Thủ quỹ",
    nhan_vien: "Nhân viên",
  };
  return map[role] || role;
}

