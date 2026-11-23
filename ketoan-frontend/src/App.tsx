import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "./contexts/AuthContext";
import { ToastProvider } from "./contexts/ToastContext";
import { Layout } from "./components/Layout";
import { LoginPage } from "./pages/LoginPage";
import { DashboardPage } from "./pages/DashboardPage";
import { ScanImportPage } from "./pages/ScanImportPage";
import { ScanHistoryPage } from "./pages/ScanHistoryPage";
import { VouchersPage } from "./pages/VouchersPage";
import { SellersPage } from "./pages/SellersPage";
import { CustomersPage } from "./pages/CustomersPage";
import { SalesInvoicesPage } from "./pages/SalesInvoicesPage";
import { ExportPage } from "./pages/ExportPage";
import { SettingsPage } from "./pages/SettingsPage";

export default function App() {
  return (
    <BrowserRouter>
      <ToastProvider>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/" element={<Layout />}>
              <Route index element={<Navigate to="/dashboard" replace />} />
              <Route path="dashboard" element={<DashboardPage />} />
              <Route path="scan-import" element={<ScanImportPage />} />
              <Route path="scan-history" element={<ScanHistoryPage />} />
              <Route path="vouchers" element={<VouchersPage />} />
              <Route path="sellers" element={<SellersPage />} />
              <Route path="customers" element={<CustomersPage />} />
              <Route path="sales-invoices" element={<SalesInvoicesPage />} />
              <Route path="export" element={<ExportPage />} />
              <Route path="settings" element={<SettingsPage />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </AuthProvider>
      </ToastProvider>
    </BrowserRouter>
  );
}
