from tests.conftest import auth_headers


def test_dashboard_summary_computes_correct_totals(client, giam_doc_user):
    headers = auth_headers(client, "director_test")
    s1 = client.post(
        "/sellers/", headers=headers,
        json={"name": "Nguyễn Văn A", "id_card_number": "079090001234", "phone": "0909123456", "address": "Bình Phước"},
    ).json()
    s2 = client.post("/sellers/", headers=headers, json={"name": "Trần Thị B"}).json()

    client.post(
        "/vouchers/", headers=headers,
        json={"ngay": "2026-07-05", "seller_id": s1["id"], "ly_do_chi": "t", "so_tien": 1_000_000, "so_luong": 50.5},
    )
    client.post(
        "/vouchers/", headers=headers,
        json={"ngay": "2026-07-06", "seller_id": s1["id"], "ly_do_chi": "t", "so_tien": 2_000_000, "so_luong": 100.25},
    )
    client.post("/vouchers/", headers=headers, json={"ngay": "2026-07-07", "seller_id": s2["id"], "ly_do_chi": "t", "so_tien": 500_000})
    # tháng khác -> không tính vào
    client.post("/vouchers/", headers=headers, json={"ngay": "2026-08-01", "seller_id": s1["id"], "ly_do_chi": "t", "so_tien": 9_999_999})

    resp = client.get("/reports/dashboard", headers=headers, params={"month": 7, "year": 2026})
    assert resp.status_code == 200
    body = resp.json()
    assert body["tong_chi_thang_nay"] == 3_500_000
    assert body["so_phieu_thang_nay"] == 3
    assert body["so_phieu_cho_duyet"] == 4  # tất cả đều đang draft, kể cả phiếu tháng 8
    assert body["top_nguoi_ban"][0]["seller_name"] == "Nguyễn Văn A"
    assert body["top_nguoi_ban"][0]["tong_tien"] == 3_000_000
    assert body["top_nguoi_ban"][0]["tong_so_luong"] == 150.75
    assert body["top_nguoi_ban"][0]["id_card_number"] == "079090001234"
    assert body["top_nguoi_ban"][0]["phone"] == "0909123456"
    assert body["top_nguoi_ban"][1]["seller_name"] == "Trần Thị B"
    assert body["top_nguoi_ban"][1]["tong_so_luong"] == 0.0


def test_dashboard_excludes_void_vouchers(client, giam_doc_user):
    headers = auth_headers(client, "director_test")
    seller = client.post("/sellers/", headers=headers, json={"name": "Nguyễn Văn A"}).json()
    v = client.post("/vouchers/", headers=headers, json={"ngay": "2026-07-05", "seller_id": seller["id"], "ly_do_chi": "t", "so_tien": 500_000}).json()
    client.post(f"/vouchers/{v['id']}/void", headers=headers, json={"ly_do_huy": "test"})

    resp = client.get("/reports/dashboard", headers=headers, params={"month": 7, "year": 2026})
    assert resp.json()["tong_chi_thang_nay"] == 0
    assert resp.json()["so_phieu_thang_nay"] == 0


def test_dashboard_warns_overdue_pending_signature(client, giam_doc_user, db_session):
    from datetime import datetime, timedelta, timezone
    from app.models.voucher import Voucher, VoucherStatus

    headers = auth_headers(client, "director_test")
    seller = client.post("/sellers/", headers=headers, json={"name": "Nguyễn Văn A"}).json()
    v = client.post("/vouchers/", headers=headers, json={"ngay": "2026-07-05", "seller_id": seller["id"], "ly_do_chi": "t", "so_tien": 500_000}).json()
    client.post(f"/vouchers/{v['id']}/approve", headers=headers)

    # giả lập đã duyệt từ 10 ngày trước (quá hạn cảnh báo 5 ngày)
    voucher_row = db_session.get(Voucher, v["id"])
    voucher_row.approved_at = datetime.now(timezone.utc) - timedelta(days=10)
    db_session.commit()

    resp = client.get("/reports/dashboard", headers=headers, params={"month": 7, "year": 2026})
    assert resp.json()["so_phieu_cho_ky_qua_han"] == 1


def test_dashboard_cong_no_phai_thu_only_counts_issued_unpaid(client, giam_doc_user):
    headers = auth_headers(client, "director_test")
    customer = client.post("/customers/", headers=headers, json={"company_name": "Test Co"}).json()

    # nháp -> KHÔNG tính vào công nợ (chưa thật sự xuất hoá đơn)
    client.post("/sales-invoices/", headers=headers, json={
        "ngay": "2026-07-01", "customer_id": customer["id"], "ten_hang": "A", "so_luong": 10, "don_gia": 1000,
    })

    # đã xuất, chưa thu -> tính vào công nợ
    inv2 = client.post("/sales-invoices/", headers=headers, json={
        "ngay": "2026-07-01", "customer_id": customer["id"], "ten_hang": "B", "so_luong": 10, "don_gia": 2000,
    }).json()
    client.post(f"/sales-invoices/{inv2['id']}/mark-issued", headers=headers, json={"so_hoa_don": "1", "ky_hieu": "X"})

    # đã xuất VÀ đã thu -> KHÔNG tính vào công nợ nữa
    inv3 = client.post("/sales-invoices/", headers=headers, json={
        "ngay": "2026-07-01", "customer_id": customer["id"], "ten_hang": "C", "so_luong": 10, "don_gia": 3000,
    }).json()
    client.post(f"/sales-invoices/{inv3['id']}/mark-issued", headers=headers, json={"so_hoa_don": "2", "ky_hieu": "X"})
    client.post(f"/sales-invoices/{inv3['id']}/mark-paid", headers=headers)

    resp = client.get("/reports/dashboard", headers=headers, params={"month": 7, "year": 2026})
    assert resp.json()["cong_no_phai_thu"] == 20_000  # chỉ inv2 (10 * 2000)
    assert resp.json()["so_hoa_don_cho_thu"] == 1


def test_dashboard_multi_month_ranking_across_year_boundary(client, giam_doc_user):
    headers = auth_headers(client, "director_test")
    s1 = client.post("/sellers/", headers=headers, json={"name": "Lê Văn Đa Tháng"}).json()
    s2 = client.post("/sellers/", headers=headers, json={"name": "Phạm Thị Một Tháng"}).json()

    # Tháng 11/2025 -> ngoài khoảng 3 tháng kết thúc ở 02/2026
    client.post("/vouchers/", headers=headers, json={"ngay": "2025-11-15", "seller_id": s1["id"], "ly_do_chi": "t", "so_tien": 9_000_000})
    # Tháng 12/2025, 01/2026, 02/2026 -> nằm trong kỳ 3 tháng (12/2025 - 02/2026)
    client.post("/vouchers/", headers=headers, json={"ngay": "2025-12-10", "seller_id": s1["id"], "ly_do_chi": "t", "so_tien": 1_000_000})
    client.post("/vouchers/", headers=headers, json={"ngay": "2026-01-20", "seller_id": s1["id"], "ly_do_chi": "t", "so_tien": 2_000_000})
    client.post("/vouchers/", headers=headers, json={"ngay": "2026-02-05", "seller_id": s2["id"], "ly_do_chi": "t", "so_tien": 2_500_000})

    resp = client.get("/reports/dashboard", headers=headers, params={"month": 2, "year": 2026, "months": 3})
    assert resp.status_code == 200
    body = resp.json()
    assert body["months"] == 3
    assert body["tu_thang"] == "12/2025"
    assert body["den_thang"] == "02/2026"
    assert body["tong_chi_thang_nay"] == 5_500_000
    assert body["so_phieu_thang_nay"] == 3
    assert body["top_nguoi_ban"][0]["seller_name"] == "Lê Văn Đa Tháng"
    assert body["top_nguoi_ban"][0]["tong_tien"] == 3_000_000
    assert body["top_nguoi_ban"][0]["so_thang_phat_sinh"] == 2
    assert body["top_nguoi_ban"][1]["seller_name"] == "Phạm Thị Một Tháng"
    assert body["top_nguoi_ban"][1]["tong_tien"] == 2_500_000
    assert body["top_nguoi_ban"][1]["so_thang_phat_sinh"] == 1

