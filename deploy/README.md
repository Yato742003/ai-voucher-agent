# Triển khai lên VPS thật — HTTPS tự động + backup định kỳ

## 0. Đã test thật những gì, chưa test được gì

**Đã test thật** (trong lúc code, không chỉ viết cho có):
- Caddyfile hợp lệ — validate bằng chính binary Caddy v2.10.2 tải trực tiếp từ GitHub, xác nhận tự bật HTTPS + redirect HTTP→HTTPS cho cả 2 domain.
- Frontend build thật với `VITE_API_BASE_URL` trỏ sang domain API — xác nhận domain được nhúng đúng vào file JS build ra.
- `CORS_ORIGINS` đọc từ biến môi trường dạng JSON list — test thật, parse đúng.
- **Cốt lõi script backup**: `pg_dump | gzip` rồi phục hồi lại vào 1 DB mới — đối chiếu đúng 289 phiếu ở cả DB gốc và DB phục hồi, dump toàn vẹn.

**CHƯA test được** (môi trường code không có Docker):
- Chưa chạy được `docker compose up` thật — chưa xác nhận 4 service (caddy/frontend/backend/db) nói chuyện được với nhau khi thật sự lên container.
- Chưa xin được chứng chỉ Let's Encrypt thật (cần domain thật trỏ DNS + port 80/443 mở ra Internet — sandbox lúc code không có).
- Script backup đã test riêng phần lõi (pg_dump/gzip/restore), nhưng **chưa test qua lớp `docker compose exec` thật** (dòng gọi trong `backup_db.sh`).

**=> Việc đầu tiên khi bạn deploy thật: chạy `docker compose up -d --build`, xem log kỹ, và tự chạy thử `scripts/backup_db.sh` 1 lần tay trước khi thêm vào cron.**

## 1. Chuẩn bị

- 1 VPS (Ubuntu 22.04+ khuyến nghị), đã cài Docker + Docker Compose plugin.
- 1 domain, tạo 2 bản ghi DNS loại A trỏ về IP VPS:
  - `ketoan.congtyban.com` → IP VPS (Frontend)
  - `api.ketoan.congtyban.com` → IP VPS (Backend API)
- Mở port 80 và 443 trên firewall VPS (Caddy cần cả 2: 80 để xác thực Let's Encrypt + redirect, 443 để phục vụ HTTPS thật).

## 2. Cấu trúc thư mục

```
cong-ty-ban/
  ketoan-backend/     <- giải nén từ file zip backend đã có
  ketoan-frontend/    <- giải nén từ file zip frontend đã có
  deploy/             <- các file trong gói này (docker-compose.yml, Caddyfile, scripts/)
```

## 3. Chạy lần đầu

```bash
cd cong-ty-ban/deploy
cp .env.example .env
nano .env   # điền DOMAIN, API_DOMAIN, đổi hết các mật khẩu/secret

docker compose up -d --build
docker compose logs -f caddy   # theo dõi Caddy xin chứng chỉ HTTPS — có thể mất 10-30s
```

Sau khi build xong, chạy migration + seed (giống hệt cách chạy local, chỉ đổi `docker compose exec`):

```bash
docker compose exec backend alembic upgrade head
docker compose exec backend python -m scripts.seed_initial_data
```

Mở `https://ketoan.congtyban.com` — nếu Caddy xin chứng chỉ thành công, trình duyệt sẽ hiện ổ khoá HTTPS ngay, không cần cấu hình gì thêm.

## 4. Bật backup tự động

```bash
chmod +x scripts/backup_db.sh
./scripts/backup_db.sh   # chạy tay 1 lần trước, xem có lỗi gì không

crontab -e
# thêm dòng này (chạy 2 giờ sáng mỗi ngày):
0 2 * * * /duong/dan/day/du/cong-ty-ban/deploy/scripts/backup_db.sh >> /var/log/ketoan-backup.log 2>&1
```

Mặc định backup chỉ lưu trên chính VPS (`/var/backups/ketoan`) — **không chống được rủi ro mất/hỏng cả VPS**. Muốn backup thật sự an toàn (off-site), mở `scripts/backup_db.sh`, điền 4 biến `S3_*` ở đầu file (dùng được với Backblaze B2, Wasabi, DigitalOcean Spaces — không bắt buộc AWS) rồi `pip install awscli`.

## 5. Cập nhật khi có bản mới

```bash
cd cong-ty-ban
# thay nội dung ketoan-backend/ và/hoặc ketoan-frontend/ bằng bản mới
cd deploy
docker compose up -d --build
docker compose exec backend alembic upgrade head   # nếu có migration mới
```

## 6. Việc CẦN làm trước khi coi là "production sẵn sàng"

- [ ] Tự chạy `docker compose up` thật trên VPS, xác nhận cả 4 service khởi động sạch (mục 0 nói rõ mình chưa test được bước này).
- [ ] Xác nhận HTTPS thật hoạt động (ổ khoá xanh trên trình duyệt).
- [ ] Chạy thử `scripts/backup_db.sh` tay, xác nhận file `.sql.gz` tạo ra đúng và phục hồi được (giống cách mình đã test ở máy code, nhưng qua `docker compose exec` thật).
- [ ] Cân nhắc cấu hình `S3_*` để backup off-site thật sự, không chỉ nằm trên VPS.
