from tests.conftest import auth_headers


def test_sales_invoice_total_matches_sample_invoice(client, giam_doc_user):
    """Đối chiếu số liệu hoá đơn bán ra mẫu (21/07/2026)."""
    headers = auth_headers(client, "director_test")
    customer = client.post(
        "/customers/", headers=headers,
        json={"company_name": "CÔNG TY TNHH ĐỐI TÁC MẪU A", "tax_code": "0100000001"},
    ).json()

    resp = client.post(
        "/sales-invoices/", headers=headers,
        json={
            "ngay": "2026-07-21",
            "customer_id": customer["id"],
            "ten_hang": "Mủ cao su nguyên liệu tạp",
            "so_luong": 2080,
            "don_gia": 31800,
            "thue_suat": "KKKNT",
            "payment_method": "chuyen_khoan",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert float(body["tong_tien"]) == 66_144_000.0
    assert body["trang_thai"] == "draft"


def test_mark_issued_updates_status_and_invoice_number(client, giam_doc_user):
    headers = auth_headers(client, "director_test")
    customer = client.post("/customers/", headers=headers, json={"company_name": "Test Co"}).json()
    invoice = client.post(
        "/sales-invoices/", headers=headers,
        json={"ngay": "2026-07-21", "customer_id": customer["id"], "ten_hang": "Mủ cao su", "so_luong": 100, "don_gia": 30000},
    ).json()
    assert invoice["trang_thai"] == "draft"

    resp = client.post(
        f"/sales-invoices/{invoice['id']}/mark-issued", headers=headers,
        json={"so_hoa_don": "0000123", "ky_hieu": "C26TLC"},
    )
    assert resp.status_code == 200
    assert resp.json()["trang_thai"] == "issued"
    assert resp.json()["so_hoa_don"] == "0000123"


def test_mark_paid_sets_paid_at_and_rejects_double_mark(client, giam_doc_user):
    headers = auth_headers(client, "director_test")
    customer = client.post("/customers/", headers=headers, json={"company_name": "Test Co"}).json()
    invoice = client.post(
        "/sales-invoices/", headers=headers,
        json={"ngay": "2026-07-21", "customer_id": customer["id"], "ten_hang": "Mủ cao su", "so_luong": 100, "don_gia": 30000},
    ).json()
    assert invoice["paid_at"] is None

    resp = client.post(f"/sales-invoices/{invoice['id']}/mark-paid", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["paid_at"] is not None

    resp = client.post(f"/sales-invoices/{invoice['id']}/mark-paid", headers=headers)
    assert resp.status_code == 409
