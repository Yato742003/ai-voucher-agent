# Frontend — Sổ Kế Toán

React 19 + TypeScript + Vite. MVP cho Phase 1 theo kế hoạch tổng
(`KE_HOACH_HE_THONG_KE_TOAN.md`).

## Chạy thử

```bash
npm install
cp .env.example .env
# sửa VITE_API_BASE_URL trong .env nếu backend không chạy ở localhost:8000

npm run dev
```

Mở `http://localhost:5173`. Cần Backend đang chạy (xem README của
`ketoan-backend`) và đã seed ít nhất 1 tài khoản (`scripts/seed_initial_data.py`).

## Build production

```bash
npm run build
```

Ra thư mục `dist/` — copy lên bất kỳ static hosting nào (Nginx, Caddy,
Netlify, hoặc chung server với backend qua reverse proxy).

## Đã có

- **Tổng quan (Dashboard)** — trang mặc định sau đăng nhập: tổng chi
  tháng, phiếu chờ duyệt, phiếu chờ ký quá 5 ngày (cảnh báo), top 5
  người bán, công nợ phải thu.
- **Công nợ phải thu** — hoá đơn bán ra có nút "Đánh dấu đã thu" riêng
  biệt với trạng thái "đã xuất hoá đơn" (2 việc độc lập).
- **Ghi chú chất lượng** trên phiếu chi (độ ẩm/tạp chất — tuỳ chọn).
- **Ô chọn người bán có tìm kiếm** (`SearchableSelect`) — gõ để lọc,
  không cần cuộn dropdown dài.
- **Tìm kiếm/lọc nhanh** trong danh sách phiếu chi (theo số phiếu,
  người bán, lý do chi).
- **Toast thông báo** — phản hồi ngay khi thao tác (tạo/duyệt/huỷ/upload)
  thành công hay lỗi, tự biến mất sau 4 giây.
- **Sidebar co gọn trên màn hình nhỏ** (menu hamburger dưới 820px) —
  dùng được trên điện thoại khi truy cập từ xa.
- Đăng nhập/đăng xuất (JWT lưu localStorage).
- Danh sách phiếu chi theo tháng/năm + tổng tiền.
- Tạo phiếu chi (tự tính số tiền nếu điền số lượng × đơn giá).
- Duyệt / huỷ phiếu (chỉ hiện nút cho tài khoản vai trò `giam_doc` — khớp
  đúng RBAC đã cài ở Backend; nút bị ẩn hoàn toàn với vai trò khác, KHÔNG
  chỉ dựa vào ẩn nút để bảo mật — Backend vẫn tự chặn nếu gọi thẳng API).
- Quản lý người bán — cảnh báo trùng tên real-time (gọi
  `/sellers/check-duplicate` khi gõ, debounce 400ms).
- Quản lý khách hàng.
- Tải file Excel gom nhóm theo người bán + Bảng kê 02/TNDN.
- Upload ảnh phiếu đã ký — hiện nút "Upload ảnh đã ký" cho MỌI vai trò khi
  phiếu ở trạng thái chờ ký (đúng theo Backend, không giới hạn giám đốc).
- Hoá đơn bán ra — tạo, xem, đánh dấu "đã xuất hoá đơn" (nhập lại số/ký
  hiệu hoá đơn thật đã phát hành qua phần mềm hoá đơn điện tử).
- Cài đặt: đổi mật khẩu (mọi vai trò), thông tin công ty + quản lý tài
  khoản người dùng (chỉ hiện với vai trò giám đốc — đã kiểm chứng lại
  Backend vẫn chặn đúng 403 nếu vai trò khác cố gọi thẳng API).
- Thiết kế riêng (không dùng theme mặc định): màu xanh mực + nâu đất lấy
  từ bối cảnh sổ sách/cao su, "con dấu" trạng thái phiếu (`StatusSeal`)
  làm điểm nhấn nhận diện xuyên suốt app.

## CHƯA có (rõ ràng, để không hiểu nhầm)

- **Chưa test bằng trình duyệt thật / chưa có E2E (Playwright)** — môi
  trường build sandbox không cho phép tải browser binary. Đã kiểm chứng
  kỹ ở mức khác: `tsc -b` build sạch không lỗi type, và đã mô phỏng đúng
  từng request/response thật (login, tạo người bán, check trùng, tạo
  phiếu, upload ảnh ký, hoá đơn bán ra, cài đặt công ty, quản lý user,
  và RBAC 403 cho vai trò không phải giám đốc) bằng Python `requests`,
  đối chiếu field-by-field với TypeScript types — khớp 100%. Nhưng
  **bạn nên tự mở trình duyệt test lại** trước khi dùng thật, để chắc
  chắn UI hiển thị đúng ý (bố cục, responsive, trải nghiệm thật).
- Phân trang — danh sách người bán/phiếu chi hiện tải hết 1 lần, ổn với
  quy mô hiện tại (vài trăm phiếu/tháng) nhưng nên phân trang khi dữ liệu
  nhiều năm cộng dồn.
- Quên mật khẩu (qua email/SMS) — chưa có (Backend cũng chưa có), hiện
  chỉ đổi được khi đã đăng nhập.
- Dark mode — có để sẵn biến CSS nhưng chưa triển khai đầy đủ.

## Lỗ hổng bảo mật đã biết (npm audit)

`react-router-dom` bị `npm audit` báo lỗ hổng "RSC Mode CSRF Bypass" ở các
bản ≥7.12.0 — project này ghim ở **7.11.0** (dưới ngưỡng bị ảnh hưởng) và
project **không dùng chế độ RSC/framework mode** (chỉ dùng
`BrowserRouter` + `Routes` thuần phía client) nên không nằm trong vector
tấn công đó. Vẫn nên theo dõi và nâng cấp khi có bản vá chính thức.
