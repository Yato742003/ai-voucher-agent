#!/bin/bash
# Backup định kỳ cho DB kế toán. Chạy qua cron trên HOST (không phải trong
# container) — xem hướng dẫn crontab trong deploy/README.md.
#
# Mặc định chỉ lưu LOCAL trên VPS — KHÔNG bảo vệ được nếu mất/hỏng cả VPS.
# Để backup thật sự "off-site" (khuyến nghị), điền thêm 4 biến S3_* bên
# dưới (dùng được với bất kỳ dịch vụ tương thích S3 nào: Backblaze B2,
# Wasabi, DigitalOcean Spaces... không bắt buộc phải AWS).
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/var/backups/ketoan}"
KEEP_DAYS="${KEEP_DAYS:-30}"
COMPOSE_DIR="$(dirname "$(readlink -f "$0")")/.."

# --- Tuỳ chọn: đẩy lên lưu trữ ngoài tương thích S3 ---
# S3_BUCKET="ketoan-backups"
# S3_ENDPOINT_URL="https://s3.us-west-000.backblazeb2.com"
# AWS_ACCESS_KEY_ID="..."
# AWS_SECRET_ACCESS_KEY="..."

mkdir -p "$BACKUP_DIR"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
FILENAME="ketoan_${TIMESTAMP}.sql.gz"
FILEPATH="${BACKUP_DIR}/${FILENAME}"

echo "[$(date)] Bắt đầu backup -> ${FILEPATH}"

# --user postgres của container, gọi qua docker compose exec để không cần
# cài postgresql-client trên host
cd "$COMPOSE_DIR"
docker compose exec -T db pg_dump -U ketoan ketoan_db | gzip > "$FILEPATH"

SIZE=$(du -h "$FILEPATH" | cut -f1)
echo "[$(date)] Backup xong, kích thước: ${SIZE}"

# Xoá backup cũ hơn KEEP_DAYS ngày
find "$BACKUP_DIR" -name "ketoan_*.sql.gz" -mtime "+${KEEP_DAYS}" -delete
echo "[$(date)] Đã dọn backup cũ hơn ${KEEP_DAYS} ngày"

# Đẩy lên lưu trữ ngoài nếu đã cấu hình S3_BUCKET
if [ -n "${S3_BUCKET:-}" ]; then
  if ! command -v aws >/dev/null 2>&1; then
    echo "[$(date)] CẢNH BÁO: đã đặt S3_BUCKET nhưng chưa cài awscli — bỏ qua bước upload. Cài bằng: pip install awscli"
  else
    aws s3 cp "$FILEPATH" "s3://${S3_BUCKET}/${FILENAME}" ${S3_ENDPOINT_URL:+--endpoint-url "$S3_ENDPOINT_URL"}
    echo "[$(date)] Đã đẩy lên s3://${S3_BUCKET}/${FILENAME}"
  fi
else
  echo "[$(date)] CHƯA cấu hình S3_BUCKET -> backup chỉ nằm trên VPS này, KHÔNG chống được rủi ro mất cả VPS."
fi
