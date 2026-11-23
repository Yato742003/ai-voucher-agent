# Backend — Hệ thống quản lý kế toán nội bộ

Phase 0/1 (theo `../docs/KE_HOACH_HE_THONG_KE_TOAN.md`): schema DB + khung FastAPI.
**Đã test thật** trên PostgreSQL 16 + dữ liệu Excel thật (T6/2026) — xem mục
"Đã kiểm thử" bên dưới để biết chính xác phần nào đã chạy được, phần nào
chưa.

## 1. Cấu trúc project

```
app/
  models/       - SQLAlchemy ORM (10 bảng: users, roles, sellers, customers,
                  vouchers, sales_invoices, attachments, audit_log, accounts,
                  sequence_counters, app_settings)
  schemas/      - Pydantic (validate request/response)
  api/          - FastAPI routers (auth, sellers, customers, vouchers,
                  attachments, sales_invoices, export)
  core/         - security (JWT/bcrypt), audit log helper
  services/     - business logic (cấp số phiếu, phát hiện trùng tên, xuất
                  file gom nhóm, đổi số thành chữ, cấu hình)
  migration/    - import dữ liệu lịch sử từ Excel
alembic/        - migration DB (2 revision: schema gốc + trigger audit_log)
scripts/        - seed dữ liệu ban đầu (role + admin)
docker-compose.yml, Dockerfile, .env.example
```

## 2. Chạy bằng Docker (khuyến nghị — dùng khi đã sẵn sàng deploy)

```bash
cp .env.example .env
# mở .env, đổi POSTGRES_PASSWORD, SECRET_KEY, INITIAL_ADMIN_PASSWORD

docker compose up -d --build
docker compose exec backend alembic upgrade head
docker compose exec backend python -m scripts.seed_initial_data
```

Sau đó API chạy ở `http://<ip-server>:8000`, xem docs tự động tại
`http://<ip-server>:8000/docs`.

## 3. Chạy trực tiếp (lúc code/test, không qua Docker)

Yêu cầu: Python 3.12, PostgreSQL đã cài & đang chạy.

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# tạo DB rỗng, ví dụ:
createdb ketoan_db

cp .env.example .env
# sửa DATABASE_URL trong .env nếu bạn dùng user/pass khác mặc định.
# Mặc định của repo là:
# DATABASE_URL=postgresql+psycopg2://ketoan:<POSTGRES_PASSWORD>@127.0.0.1:5432/ketoan_db
# Nếu chạy qua Docker Compose, backend sẽ tự nhận DATABASE_URL do compose cấp.

alembic upgrade head
python -m scripts.seed_initial_data
uvicorn app.main:app --reload
```

## 4. Import dữ liệu lịch sử từ Excel (Phase 0)

```bash
# xem trước, KHÔNG lưu gì (an toàn để thử):
python -m app.migration.import_from_excel "duong/dan/PHIEU_CHI_Tx.xlsx" --dry-run

# import thật:
python -m app.migration.import_from_excel "duong/dan/PHIEU_CHI_Tx.xlsx"
```

Script tự dò người bán trùng tên (theo tên đã chuẩn hoá) để không tạo
trùng, tự bỏ qua nếu số phiếu đã tồn tại (và **in ra** số phiếu nào bị bỏ
qua để bạn tra lại — file gốc có thể có lỗi đánh trùng số ngoài đời, như
đã gặp thật ở file T6: số **048/06** và **049/06** mỗi số bị lặp 2 lần).

Sau khi import xong 1 tháng, bộ đếm cấp số tự động (`sequence_counters`)
được đồng bộ theo số lớn nhất đã import — phiếu MỚI tạo sau này qua API
sẽ tiếp nối đúng, không trùng với lịch sử.

## 5. Đăng nhập lần đầu

Dùng `INITIAL_ADMIN_USERNAME`/`INITIAL_ADMIN_PASSWORD` trong `.env` để lấy
token qua `POST /auth/login`, sau đó **đổi mật khẩu ngay** (hiện chưa có
endpoint đổi mật khẩu qua API — cách nhanh nhất lúc này là chạy lại
`scripts/seed_initial_data.py` sau khi xoá user admin cũ, hoặc update
trực tiếp `password_hash` bằng `app.core.security.hash_password`).

## 6. Vai trò & phân quyền

| Role        | Được làm gì (đã áp dụng ở tầng API)                                                           |
| ----------- | --------------------------------------------------------------------------------------------- |
| `giam_doc`  | Mọi việc, đặc biệt: duyệt phiếu (`/vouchers/{id}/approve`), huỷ phiếu (`/vouchers/{id}/void`) |
| `ke_toan`   | Tạo/sửa phiếu (khi còn nháp), quản lý người bán/khách hàng, xuất file                         |
| `thu_quy`   | (hiện dùng chung quyền với ke_toan — Phase 2 sẽ tách chi tiết hơn cùng UI upload ảnh ký)      |
| `nhan_vien` | Tạo phiếu nháp                                                                                |

**Nguyên tắc cứng đã cài (test thật, không chỉ lý thuyết)**: phiếu chỉ sửa
được khi còn `draft`; sau khi `approve` thì bị khoá, sửa sẽ trả lỗi 409 —
muốn điều chỉnh phải tạo phiếu mới. Chỉ `giam_doc` gọi được `/approve` và
`/void` — tài khoản `ke_toan` gọi thử bị chặn đúng lỗi 403.

## 7. Chạy bộ test tự động

**Tính năng mới: Scan bảng kê -> phiếu chi.** Cần thêm `ANTHROPIC_API_KEY`
vào `.env` (lấy tại console.anthropic.com). Không có key, `/scans/extract`
vẫn chạy nhưng trả lỗi 502 rõ ràng (đã test — xem `tests/test_scans.py`).
Luồng: upload ảnh -> Claude đọc từng dòng -> hệ thống tự đối chiếu
SL×đơn giá với tổng tiền + đối chiếu tên với danh sách người bán có sẵn,
đánh dấu dòng nghi ngờ -> người dùng xem/sửa trên Frontend -> xác nhận
mới thật sự tạo phiếu (luôn ở trạng thái nháp, vẫn qua duyệt như thường).
Toàn bộ ảnh gốc + kết quả thô + kết quả đã sửa được lưu trong bảng
`scan_imports` — đây là dữ liệu gán nhãn dùng để fine-tune 1 model OCR
riêng cho chữ viết tay của công ty sau này (xem
`../docs/KE_HOACH_NANG_CAP_UX_TINH_NANG.md`).

**Cập nhật mới (nghiên cứu + nâng cấp UX/tính năng):** xem
`../docs/KE_HOACH_NANG_CAP_UX_TINH_NANG.md` để biết nguồn nghiên cứu và lý do
ưu tiên. Đã thêm: `GET /reports/dashboard` (tổng quan), công nợ phải thu
(`paid_at` trên hoá đơn bán ra + `POST /sales-invoices/{id}/mark-paid`),
ghi chú chất lượng trên phiếu chi (`ghi_chu_chat_luong` — độ ẩm/tạp chất,
tuỳ chọn). 5 test mới trong `tests/test_reports.py`.

```bash
pip install -r requirements-dev.txt
createdb ketoan_test_db   # 1 lần duy nhất, DB test riêng biệt với DB dev
pytest -v
```

25 test, phủ: đăng nhập/rate-limit/đổi mật khẩu, tạo & phát hiện trùng
người bán, cấp số phiếu tự động, state machine phiếu chi (sửa/duyệt/huỷ +
RBAC), upload ảnh ký, xuất file (gom nhóm + Bảng kê 02/TNDN, loại trừ
phiếu huỷ), hoá đơn bán ra, và audit_log append-only.

## 8. API chính

Xem đầy đủ + thử trực tiếp tại `/docs` (Swagger UI tự sinh). Tóm tắt:

- `POST /auth/login`, `GET /auth/me`, `POST /auth/change-password`
- `GET/POST/PATCH /sellers/`, `GET /sellers/check-duplicate?name=...`, `POST /sellers/{id}/merge-into/{target_id}`
- `GET/POST/PATCH /customers/`
- `GET/POST/PATCH /vouchers/`, `POST /vouchers/{id}/approve`, `POST /vouchers/{id}/void`
- `POST /vouchers/{id}/signed-scan` (upload ảnh phiếu đã ký, multipart/form-data)
- `GET/POST /sales-invoices/`, `POST /sales-invoices/{id}/mark-issued`, `POST /sales-invoices/{id}/mark-paid`
- `GET /reports/dashboard?month=&year=` (tổng quan: tổng chi, phiếu chờ duyệt/ký quá hạn, top người bán, công nợ phải thu)
- `GET /export/grouped-by-seller?month=&year=` (tải file .xlsx gom nhóm theo người bán)
- `GET /export/bang-ke-02-tndn?month=&year=` (tải Bảng kê 02/TNDN)
- `GET/PUT /settings/company` (PUT chỉ giám đốc)
- `GET/POST /users/` (chỉ giám đốc — tạo tài khoản kế toán/thủ quỹ mới)

## 9. Đã kiểm thử (thật, trên Postgres 16 + dữ liệu thật)

- [x] Migration chạy sạch, tạo đủ 10 bảng + 2 kiểu enum + trigger.
- [x] Trigger chặn UPDATE/DELETE `audit_log` — test bằng lệnh SQL trực tiếp, bị chặn đúng.
- [x] bcrypt hash/verify (đã phát hiện & sửa lỗi tương thích passlib/bcrypt).
- [x] Đăng nhập, JWT, `/auth/me`.
- [x] Tạo người bán + phát hiện trùng tên (rapidfuzz) — test với tên viết khác dấu/hoa thường.
- [x] Tạo phiếu chi, cấp số tự động theo tháng (`001/07`, `002/07`...).
- [x] Sửa phiếu khi DRAFT — được phép; sửa sau khi duyệt — bị chặn 409.
- [x] Duyệt phiếu — chỉ `giam_doc`; `ke_toan` gọi thử bị chặn 403 (RBAC test thật).
- [x] Upload ảnh ký → tự chuyển trạng thái `signed`.
- [x] Tạo khách hàng + hoá đơn bán ra — đối chiếu đúng số liệu hoá đơn thật (Công ty Đối tác A, 66.144.000đ).
- [x] Hàm đổi số thành chữ — đối chiếu đúng với hoá đơn thật, phát hiện & sửa 1 lỗi (bốn/tư).
- [x] Xuất file gom nhóm theo người bán — test với 282 phiếu thật (T6/2026), 28 nhóm, kết quả khớp với lần xử lý thủ công trước đó.
- [x] Import dữ liệu lịch sử từ Excel — phát hiện đúng 2 cặp số phiếu trùng thật có trong file gốc.
- [x] requirements.txt cài sạch trong venv mới, độc lập môi trường dev.
- [x] Đổi mật khẩu (`/auth/change-password`) — test đổi + xác nhận mật khẩu cũ hết hiệu lực.
- [x] Rate limiting chống brute-force login (429 sau 5 lần sai, khoá 5 phút).
- [x] Cấu hình thông tin công ty (`/settings/company`) — chỉ giám đốc sửa được.
- [x] Xuất Bảng kê 02/TNDN — đối chiếu đúng cột với ảnh mẫu thật bạn gửi, thêm trường `so_luong`/`don_gia` vào Voucher để điền đủ cột.
- [x] **Bộ test tự động (pytest, 25 test, PASS)** — hình thức hoá toàn bộ những gì test tay ở trên, dùng DB Postgres test riêng + transaction rollback per test.
- [x] **Frontend (React + TS + Vite)** — xem `ketoan-frontend/README.md`. Đăng nhập, danh sách/tạo/duyệt/huỷ phiếu, quản lý người bán (cảnh báo trùng real-time), khách hàng, tải file xuất. Đã kiểm chứng field-by-field API thật (không phải chỉ đoán schema).

## 10. CHƯA làm (rõ ràng, để không hiểu nhầm là xong hết)

- **Agent-BE** — chưa bắt đầu (Phase 3 theo kế hoạch; nên làm sau khi Frontend đã dùng thử một thời gian).
- **Test tự động cho Frontend (Playwright/E2E)** — sandbox không tải được browser binary; xem `ketoan-frontend/README.md` mục kiểm chứng thay thế đã làm.
- **Backup tự động** — docker-compose mới lưu volume tại chỗ, CHƯA có backup off-site tự động (việc này quan trọng, nên làm sớm — xem mục rủi ro lưu trữ trong kế hoạch tổng).
- Layout phiếu chi khi xuất file là **dựng mới bằng code**, không phải bản sao y hệt pixel-by-pixel mẫu Excel gốc của công ty — nếu cần khớp tuyệt đối, nên cung cấp lại file mẫu trắng gốc để chỉnh `app/services/export_service.py` cho khớp.
- Quên mật khẩu (qua email/SMS) — chưa có, hiện chỉ đổi được khi đã đăng nhập.

## 11. Bước tiếp theo gợi ý

1. Mở Frontend bằng trình duyệt thật, test lại toàn bộ luồng (mục đã kiểm chứng ở README Frontend là kiểm chứng API, chưa phải kiểm chứng UI thật).
2. Import nốt dữ liệu lịch sử T3, T4, T5 (dùng lại `import_from_excel.py`).
3. Bắt đầu Agent-BE (Phase 3), hoặc bổ sung nốt UI còn thiếu ở Frontend.
