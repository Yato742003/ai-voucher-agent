# Nghiên cứu & kế hoạch nâng cấp tính năng / UX-UI

## Nguồn nghiên cứu
- UX dashboard/enterprise 2026 (best practice chung): rõ ràng - súc tích - có ngữ cảnh (không chỉ số khô), responsive mặc định, empty-state có hướng dẫn, tìm kiếm thông minh.
- Khảo sát các phần mềm **cùng ngành** (thu mua nông sản/cà phê/tiêu tại VN — TTV Software, NextFarm, Sapo...): 3 tính năng lặp lại nhiều nhất mà hệ thống hiện tại **chưa có**:
  1. **Công nợ** (phải trả người bán / phải thu khách hàng) theo dõi theo từng phiếu, không chỉ xem từng phiếu rời rạc.
  2. **Tham số phụ trên phiếu cân**: độ ẩm, tạp chất, trọng lượng xe — để trừ ra số lượng quy chuẩn (rất phổ biến trong ngành thu mua nông sản cân theo trọng lượng).
  3. **Báo cáo tổng hợp/dashboard** đầu trang — hiện hệ thống vào thẳng danh sách phiếu, không có màn hình tổng quan.
  4. Phân quyền chi tiết hơn (đã có sẵn ở hệ thống, không cần thêm).

## Ưu tiên — làm ngay trong lượt này

| # | Hạng mục | Vì sao ưu tiên |
|---|---|---|
| 1 | **Dashboard tổng quan** (trang mới, endpoint mới) | Validated bởi cả 2 nguồn nghiên cứu; hiện thiếu hẳn |
| 2 | **Công nợ phải thu** (khách hàng chưa thanh toán hoá đơn bán ra) | Lặp lại nhiều nhất trong khảo sát cùng ngành |
| 3 | **Ghi chú chất lượng trên phiếu chi** (độ ẩm/tạp chất — trường tuỳ chọn, không ép buộc vì chưa chắc bạn đang đo) | Đặc thù ngành, nhẹ, không đoán quá tay |
| 4 | **Ô chọn người bán có tìm kiếm** (thay dropdown thường) | Danh sách đã 28+ người bán, dropdown thường khó dùng |
| 5 | **Sidebar co gọn trên màn hình nhỏ** | "Responsive mặc định" — bạn cần truy cập từ xa, có thể xem trên điện thoại |
| 6 | **Toast thông báo** thay banner tĩnh đầu trang | Phản hồi hành động rõ ràng hơn, đúng UX pattern |
| 7 | **Tìm kiếm/lọc nhanh trong danh sách phiếu chi** | Bổ trợ cho #1, #4 |

## Cân nhắc nhưng CHƯA làm (để tránh làm quá tay khi chưa chắc bạn cần)

- **Tồn kho đầy đủ** (nhập/xuất kho mủ cao su theo lô) — cần xác nhận trước: bạn có giữ hàng tồn hay mua bao nhiêu bán hết bấy nhiêu? Nếu cần, đây sẽ là 1 module riêng khá lớn.
- **Tính tự động số lượng quy chuẩn từ độ ẩm/tạp chất** (công thức trừ hao) — cần biết công thức thực tế công ty áp dụng, không tự đoán.
- **Kết nối cân điện tử** — cần thiết bị cụ thể, ngoài phạm vi phần mềm thuần web.
- Keyboard shortcuts, dark mode hoàn chỉnh — polish thêm, ưu tiên thấp hơn nghiệp vụ.

## Danh sách file thay đổi trong lượt này

Backend: `app/models/voucher.py`, `app/models/sales_invoice.py`, migration mới, `app/api/reports.py` (mới), `app/api/sales_invoices.py`, `app/schemas/voucher.py`, `app/schemas/sales_invoice.py`, `app/main.py`, `tests/test_reports.py` (mới), `tests/test_sales_invoices.py`.

Frontend: `src/pages/DashboardPage.tsx` (mới), `src/components/SearchableSelect.tsx` (mới), `src/components/Toast.tsx` (mới), `src/contexts/ToastContext.tsx` (mới), `src/components/Layout.tsx`, `src/pages/VouchersPage.tsx`, `src/pages/SalesInvoicesPage.tsx`, `src/App.tsx`, `src/api/types.ts`, `src/styles/global.css`.
