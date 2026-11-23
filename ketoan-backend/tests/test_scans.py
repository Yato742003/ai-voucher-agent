from unittest.mock import patch

from tests.conftest import auth_headers


def test_validate_flags_arithmetic_mismatch(db_session):
    from app.services.scan_extraction_service import validate_extracted_rows

    rows = [{"ten_nguoi_ban": "Ai Đó", "so_luong": 184, "don_gia": 13798, "tong_gia_thanh_toan": 1849000}]
    result = validate_extracted_rows(db_session, rows)
    assert result[0]["canh_bao_phep_nhan"] is True


def test_validate_accepts_matching_arithmetic_within_tolerance(db_session):
    from app.services.scan_extraction_service import validate_extracted_rows

    # làm tròn nhẹ, lệch < 3% -> KHÔNG cảnh báo
    rows = [{"ten_nguoi_ban": "Ai Đó", "so_luong": 54, "don_gia": 16296, "tong_gia_thanh_toan": 880000}]
    result = validate_extracted_rows(db_session, rows)
    assert result[0]["canh_bao_phep_nhan"] is False


def test_validate_flags_unmatched_seller_name(client, giam_doc_user, db_session):
    from app.services.scan_extraction_service import validate_extracted_rows

    headers = auth_headers(client, "director_test")
    client.post("/sellers/", headers=headers, json={"name": "Nguyễn Văn Kiếm"})

    rows = [{"ten_nguoi_ban": "Người Hoàn Toàn Mới", "so_luong": 10, "don_gia": 1000, "tong_gia_thanh_toan": 10000}]
    result = validate_extracted_rows(db_session, rows)
    assert result[0]["canh_bao_ten_khong_khop"] is True
    assert result[0]["seller_id_goi_y"] is None


def test_validate_matches_existing_seller_despite_diacritics(client, giam_doc_user, db_session):
    from app.services.scan_extraction_service import validate_extracted_rows

    headers = auth_headers(client, "director_test")
    seller = client.post("/sellers/", headers=headers, json={"name": "Nguyễn Văn Kiếm"}).json()

    rows = [{"ten_nguoi_ban": "Nguyễn Văn Kiếm", "so_luong": 10, "don_gia": 1000, "tong_gia_thanh_toan": 10000}]
    result = validate_extracted_rows(db_session, rows)
    assert result[0]["canh_bao_ten_khong_khop"] is False
    assert result[0]["seller_id_goi_y"] == seller["id"]


def test_extract_endpoint_returns_502_without_api_key(client, giam_doc_user, tmp_path, monkeypatch):
    """Chưa cấu hình ANTHROPIC_API_KEY -> báo lỗi rõ ràng, không crash mập mờ."""
    from app.config import settings
    monkeypatch.setattr(settings, "scan_provider", "claude")
    monkeypatch.setattr(settings, "scan_extraction_provider", "claude")
    monkeypatch.setattr(settings, "anthropic_api_key", "")

    headers = auth_headers(client, "director_test")
    fake_image = tmp_path / "test.jpg"
    fake_image.write_bytes(b"fake-jpeg-bytes")

    with open(fake_image, "rb") as f:
        resp = client.post("/scans/extract", headers=headers, files={"file": ("test.jpg", f, "image/jpeg")})

    # môi trường test không có API key thật -> phải trả lỗi rõ ràng (502), không phải 500 mập mờ
    assert resp.status_code == 502
    assert "ANTHROPIC_API_KEY" in resp.json()["detail"]


def test_confirm_creates_draft_vouchers_and_saves_training_data(client, giam_doc_user, db_session):
    """Mock bước gọi Claude để test riêng phần confirm (tạo phiếu + lưu dữ liệu train), không phụ thuộc API thật."""
    import uuid
    from app.models.scan_import import ScanImport, ScanImportStatus

    headers = auth_headers(client, "director_test")

    # tạo sẵn 1 ScanImport ở trạng thái pending, giống như sau bước /extract
    scan = ScanImport(
        image_path="/tmp/fake.jpg",
        raw_extraction=[{"ten_nguoi_ban": "Nguyễn Văn Mới", "so_luong": 100, "don_gia": 15000, "tong_gia_thanh_toan": 1500000}],
        status=ScanImportStatus.PENDING,
        uploaded_by=giam_doc_user.id,
    )
    db_session.add(scan)
    db_session.commit()
    db_session.refresh(scan)

    resp = client.post(
        f"/scans/{scan.id}/confirm", headers=headers,
        json={"rows": [{
            "ten_nguoi_ban": "Nguyễn Văn Mới", "seller_id": None, "ten_hang_hoa": "Mủ nước",
            "so_luong": 100, "don_gia": 15000, "tong_gia_thanh_toan": 1500000, "ngay": "2026-07-25",
        }]},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["so_phieu_da_tao"] == 1

    # phiếu tạo ra phải ở trạng thái draft, đúng nguyên tắc "agent đề xuất, người xác nhận"
    voucher_resp = client.get(f"/vouchers/{body['voucher_ids'][0]}", headers=headers)
    assert voucher_resp.json()["trang_thai"] == "draft"
    assert voucher_resp.json()["so_luong"] == "100.000"

    # đã tự tạo người bán mới vì seller_id=None
    sellers = client.get("/sellers/", headers=headers).json()
    assert any(s["name"] == "Nguyễn Văn Mới" for s in sellers)

    # dữ liệu đã sửa/xác nhận phải được lưu lại làm dữ liệu train sau này
    db_session.refresh(scan)
    assert scan.status == "confirmed"
    assert scan.confirmed_extraction is not None
    assert len(scan.confirmed_extraction) == 1


def test_confirm_rejects_already_confirmed_scan(client, giam_doc_user, db_session):
    import uuid
    from app.models.scan_import import ScanImport, ScanImportStatus

    headers = auth_headers(client, "director_test")
    scan = ScanImport(
        image_path="/tmp/fake.jpg", raw_extraction=[], status=ScanImportStatus.CONFIRMED,
        uploaded_by=giam_doc_user.id,
    )
    db_session.add(scan)
    db_session.commit()
    db_session.refresh(scan)

    resp = client.post(f"/scans/{scan.id}/confirm", headers=headers, json={"rows": []})
    assert resp.status_code == 409


def test_extract_dispatches_to_ollama_when_configured(monkeypatch):
    """Không cần Ollama thật đang chạy — chỉ kiểm tra dispatcher gọi đúng hàm và parse đúng response."""
    from app.config import settings
    from app.services import scan_extraction_service as svc

    monkeypatch.setattr(settings, "scan_extraction_provider", "ollama")
    monkeypatch.setattr(settings, "ollama_vision_model", "gemma3:4b")

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "message": {
                    "content": '{"rows": [{"ten_nguoi_ban": "Nguyễn Văn A", "so_luong": 100, "don_gia": 1000, "tong_gia_thanh_toan": 100000}]}'
                }
            }

    def fake_post(url, json, timeout):
        assert "gemma3:4b" == json["model"]
        assert url.endswith("/api/chat")
        return FakeResponse()

    monkeypatch.setattr(svc.httpx, "post", fake_post)

    rows, provider, model = svc.extract_bang_ke_from_image(b"fake-image-bytes", "test.jpg")
    assert provider == "ollama"
    assert model == "gemma3:4b"
    assert rows[0]["ten_nguoi_ban"] == "Nguyễn Văn A"


def test_extract_ollama_connection_error_gives_clear_message(monkeypatch):
    from app.config import settings
    from app.services import scan_extraction_service as svc
    import httpx

    monkeypatch.setattr(settings, "scan_extraction_provider", "ollama")

    def fake_post(url, json, timeout):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(svc.httpx, "post", fake_post)

    try:
        svc.extract_bang_ke_from_image(b"fake", "test.jpg")
        assert False, "phải raise RuntimeError"
    except RuntimeError as e:
        assert "Ollama" in str(e)
        assert "ollama pull" in str(e)


def test_extract_ollama_malformed_json_gives_clear_message(monkeypatch):
    from app.config import settings
    from app.services import scan_extraction_service as svc

    monkeypatch.setattr(settings, "scan_extraction_provider", "ollama")

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"message": {"content": "không phải JSON, model local trả lung tung"}}

    monkeypatch.setattr(svc.httpx, "post", lambda url, json, timeout: FakeResponse())

    try:
        svc.extract_bang_ke_from_image(b"fake", "test.jpg")
        assert False, "phải raise RuntimeError"
    except RuntimeError as e:
        assert "JSON" in str(e)


def test_invalid_provider_config_raises_clear_error(monkeypatch):
    from app.config import settings
    from app.services import scan_extraction_service as svc

    monkeypatch.setattr(settings, "scan_extraction_provider", "some_typo_provider")
    try:
        svc.extract_bang_ke_from_image(b"fake", "test.jpg")
        assert False, "phải raise RuntimeError"
    except RuntimeError as e:
        assert "some_typo_provider" in str(e)
