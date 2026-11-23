from tests.conftest import auth_headers


def _create_seller(client, headers, name="Nguyễn Văn Test"):
    return client.post("/sellers/", headers=headers, json={"name": name}).json()


def test_voucher_gets_sequential_number_per_month(client, giam_doc_user):
    headers = auth_headers(client, "director_test")
    seller = _create_seller(client, headers)

    v1 = client.post(
        "/vouchers/", headers=headers,
        json={"ngay": "2026-07-01", "seller_id": seller["id"], "ly_do_chi": "test", "so_tien": 100000},
    ).json()
    v2 = client.post(
        "/vouchers/", headers=headers,
        json={"ngay": "2026-07-15", "seller_id": seller["id"], "ly_do_chi": "test", "so_tien": 200000},
    ).json()
    # tháng khác -> số bắt đầu lại từ 001
    v3 = client.post(
        "/vouchers/", headers=headers,
        json={"ngay": "2026-08-01", "seller_id": seller["id"], "ly_do_chi": "test", "so_tien": 300000},
    ).json()

    assert v1["so_phieu"] == "001/07"
    assert v2["so_phieu"] == "002/07"
    assert v3["so_phieu"] == "001/08"


def test_voucher_amount_must_be_positive(client, giam_doc_user):
    headers = auth_headers(client, "director_test")
    seller = _create_seller(client, headers)
    resp = client.post(
        "/vouchers/", headers=headers,
        json={"ngay": "2026-07-01", "seller_id": seller["id"], "ly_do_chi": "test", "so_tien": -100},
    )
    assert resp.status_code == 422


def test_update_allowed_while_draft(client, giam_doc_user):
    headers = auth_headers(client, "director_test")
    seller = _create_seller(client, headers)
    v = client.post(
        "/vouchers/", headers=headers,
        json={"ngay": "2026-07-01", "seller_id": seller["id"], "ly_do_chi": "test", "so_tien": 100000},
    ).json()

    resp = client.patch(f"/vouchers/{v['id']}", headers=headers, json={"so_tien": 150000})
    assert resp.status_code == 200
    assert resp.json()["so_tien"] == "150000.00"


def test_update_blocked_after_approve(client, giam_doc_user):
    headers = auth_headers(client, "director_test")
    seller = _create_seller(client, headers)
    v = client.post(
        "/vouchers/", headers=headers,
        json={"ngay": "2026-07-01", "seller_id": seller["id"], "ly_do_chi": "test", "so_tien": 100000},
    ).json()

    approve_resp = client.post(f"/vouchers/{v['id']}/approve", headers=headers)
    assert approve_resp.status_code == 200
    assert approve_resp.json()["trang_thai"] == "pending_signature"

    update_resp = client.patch(f"/vouchers/{v['id']}", headers=headers, json={"so_tien": 999})
    assert update_resp.status_code == 409


def test_only_giam_doc_can_approve(client, giam_doc_user, ke_toan_user):
    giam_doc_headers = auth_headers(client, "director_test")
    ke_toan_headers = auth_headers(client, "accountant_test")

    seller = _create_seller(client, giam_doc_headers)
    # kế toán được phép TẠO phiếu
    v = client.post(
        "/vouchers/", headers=ke_toan_headers,
        json={"ngay": "2026-07-01", "seller_id": seller["id"], "ly_do_chi": "test", "so_tien": 100000},
    ).json()

    # nhưng KHÔNG được duyệt
    resp = client.post(f"/vouchers/{v['id']}/approve", headers=ke_toan_headers)
    assert resp.status_code == 403

    # giám đốc thì duyệt được
    resp = client.post(f"/vouchers/{v['id']}/approve", headers=giam_doc_headers)
    assert resp.status_code == 200


def test_only_giam_doc_can_void_and_reason_is_required(client, giam_doc_user, ke_toan_user):
    giam_doc_headers = auth_headers(client, "director_test")
    ke_toan_headers = auth_headers(client, "accountant_test")
    seller = _create_seller(client, giam_doc_headers)
    v = client.post(
        "/vouchers/", headers=giam_doc_headers,
        json={"ngay": "2026-07-01", "seller_id": seller["id"], "ly_do_chi": "test", "so_tien": 100000},
    ).json()

    # kế toán không được huỷ
    resp = client.post(f"/vouchers/{v['id']}/void", headers=ke_toan_headers, json={"ly_do_huy": "test"})
    assert resp.status_code == 403

    # thiếu lý do -> bị từ chối
    resp = client.post(f"/vouchers/{v['id']}/void", headers=giam_doc_headers, json={"ly_do_huy": "  "})
    assert resp.status_code == 422

    # giám đốc + có lý do -> huỷ thành công, KHÔNG xoá bản ghi
    resp = client.post(f"/vouchers/{v['id']}/void", headers=giam_doc_headers, json={"ly_do_huy": "Ghi nhầm số tiền"})
    assert resp.status_code == 200
    assert resp.json()["trang_thai"] == "void"

    still_there = client.get(f"/vouchers/{v['id']}", headers=giam_doc_headers)
    assert still_there.status_code == 200


def test_signed_scan_upload_transitions_to_signed(client, giam_doc_user):
    headers = auth_headers(client, "director_test")
    seller = _create_seller(client, headers)
    v = client.post(
        "/vouchers/", headers=headers,
        json={"ngay": "2026-07-01", "seller_id": seller["id"], "ly_do_chi": "test", "so_tien": 100000},
    ).json()

    # chưa duyệt -> chưa nhận ảnh ký
    resp = client.post(f"/vouchers/{v['id']}/signed-scan", headers=headers, files={"file": ("scan.jpg", b"fake", "image/jpeg")})
    assert resp.status_code == 409

    client.post(f"/vouchers/{v['id']}/approve", headers=headers)

    resp = client.post(f"/vouchers/{v['id']}/signed-scan", headers=headers, files={"file": ("scan.jpg", b"fake", "image/jpeg")})
    assert resp.status_code == 201
    assert resp.json()["voucher_status"] == "signed"

    detail = client.get(f"/vouchers/{v['id']}", headers=headers).json()
    assert detail["trang_thai"] == "signed"

    # Test downloading the uploaded scan
    download_resp = client.get(f"/vouchers/{v['id']}/signed-scan", headers=headers)
    assert download_resp.status_code == 200
    assert download_resp.content == b"fake"


def test_import_vouchers_from_excel(client, giam_doc_user):
    headers = auth_headers(client, "director_test")
    import os
    from pathlib import Path
    template_path = Path(__file__).resolve().parents[1] / "app" / "resources" / "template_voucher.xlsx"

    with open(template_path, "rb") as f:
        resp = client.post(
            "/vouchers/import-excel",
            headers=headers,
            files={"file": ("template_voucher.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        )
    assert resp.status_code == 400
    assert "Không tìm đủ" in resp.json()["detail"]


def test_delete_voucher_draft_succeeds(client, giam_doc_user, ke_toan_user):
    ke_toan_headers = auth_headers(client, "accountant_test")
    seller = _create_seller(client, ke_toan_headers)
    v = client.post(
        "/vouchers/", headers=ke_toan_headers,
        json={"ngay": "2026-07-01", "seller_id": seller["id"], "ly_do_chi": "test", "so_tien": 100000},
    ).json()

    # Kế toán được phép xoá phiếu DRAFT
    resp = client.delete(f"/vouchers/{v['id']}", headers=ke_toan_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == v["id"]

    # Phiếu đã bị xoá khỏi DB
    get_resp = client.get(f"/vouchers/{v['id']}", headers=ke_toan_headers)
    assert get_resp.status_code == 404


def test_ke_toan_cannot_delete_approved_voucher_but_giam_doc_can(client, giam_doc_user, ke_toan_user):
    giam_doc_headers = auth_headers(client, "director_test")
    ke_toan_headers = auth_headers(client, "accountant_test")
    seller = _create_seller(client, giam_doc_headers)
    v = client.post(
        "/vouchers/", headers=giam_doc_headers,
        json={"ngay": "2026-07-01", "seller_id": seller["id"], "ly_do_chi": "test", "so_tien": 100000},
    ).json()

    # Duyệt phiếu -> chuyển sang PENDING_SIGNATURE
    client.post(f"/vouchers/{v['id']}/approve", headers=giam_doc_headers)

    # Kế toán thử xoá phiếu đã duyệt -> 409 Conflict
    resp_kt = client.delete(f"/vouchers/{v['id']}", headers=ke_toan_headers)
    assert resp_kt.status_code == 409
    assert "chỉ được xoá phiếu ở trạng thái nháp" in resp_kt.json()["detail"]

    # Giám đốc xoá phiếu -> thành công
    resp_gd = client.delete(f"/vouchers/{v['id']}", headers=giam_doc_headers)
    assert resp_gd.status_code == 200

    # Phiếu không còn trong DB
    get_resp = client.get(f"/vouchers/{v['id']}", headers=giam_doc_headers)
    assert get_resp.status_code == 404

