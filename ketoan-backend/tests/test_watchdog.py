from datetime import date

from tests.conftest import auth_headers

TODAY = date(2026, 7, 31)  # đồng hồ giả: kết quả không phụ thuộc ngày chạy test


def _seller(client, headers, name="Nguyễn Văn A", **extra):
    return client.post("/sellers/", headers=headers, json={"name": name, **extra}).json()


def _voucher(client, headers, seller_id, ngay, so_luong, don_gia):
    return client.post("/vouchers/", headers=headers, json={
        "ngay": ngay, "seller_id": seller_id, "ly_do_chi": "Mua mủ",
        "so_luong": so_luong, "don_gia": don_gia, "so_tien": so_luong * don_gia,
    }).json()


def _types(alerts):
    return [a["type"] for a in alerts]


def test_no_data_means_no_alerts(db_session):
    from app.services.watchdog_service import find_alerts

    assert find_alerts(db_session, today=TODAY) == []  # N = 0 phải ra danh sách rỗng, không lỗi


def test_price_deviation_needs_enough_history(client, giam_doc_user, db_session):
    from app.services.watchdog_service import price_deviation, PRICE_MIN_SAMPLES

    headers = auth_headers(client, "director_test")
    s = _seller(client, headers)
    import uuid
    sid = uuid.UUID(s["id"])

    assert price_deviation(db_session, sid, 99999, TODAY) is None  # chưa có phiếu nào
    for day in range(1, PRICE_MIN_SAMPLES):  # thiếu đúng 1 mẫu
        _voucher(client, headers, s["id"], f"2026-07-0{day}", 100, 15000)
    assert price_deviation(db_session, sid, 99999, TODAY) is None  # vẫn chưa đủ cơ sở để kết luận
    _voucher(client, headers, s["id"], "2026-07-05", 100, 15000)
    assert price_deviation(db_session, sid, 99999, TODAY)["lech_pct"] > 0


def test_price_anomaly_flags_only_the_outlier(client, giam_doc_user, db_session):
    from app.services.watchdog_service import find_alerts

    headers = auth_headers(client, "director_test")
    s = _seller(client, headers, id_card_number="079090001234")
    for ngay in ("2026-07-01", "2026-07-05", "2026-07-10"):
        _voucher(client, headers, s["id"], ngay, 100, 15000)
    outlier = _voucher(client, headers, s["id"], "2026-07-20", 100, 30000)

    alerts = [a for a in find_alerts(db_session, today=TODAY) if a["type"] == "price_anomaly"]
    assert len(alerts) == 1
    assert outlier["so_phieu"] in alerts[0]["title"]
    assert "+100.0%" in alerts[0]["title"]


def test_void_vouchers_are_ignored_by_price_alerts(client, giam_doc_user, db_session):
    from app.services.watchdog_service import find_alerts

    headers = auth_headers(client, "director_test")
    s = _seller(client, headers, id_card_number="079090001234")
    for ngay in ("2026-07-01", "2026-07-05", "2026-07-10"):
        _voucher(client, headers, s["id"], ngay, 100, 15000)
    outlier = _voucher(client, headers, s["id"], "2026-07-20", 100, 30000)
    client.post(f"/vouchers/{outlier['id']}/void", headers=headers, json={"ly_do_huy": "nhập nhầm"})

    assert "price_anomaly" not in _types(find_alerts(db_session, today=TODAY))


def test_receivable_overdue_alert(client, giam_doc_user, db_session):
    from app.services.watchdog_service import find_alerts

    headers = auth_headers(client, "director_test")
    customer = client.post("/customers/", headers=headers, json={"company_name": "Đối Tác A"}).json()

    def issued(ngay, so_hd):
        inv = client.post("/sales-invoices/", headers=headers, json={
            "ngay": ngay, "customer_id": customer["id"], "ten_hang": "Mủ", "so_luong": 10, "don_gia": 2000,
        }).json()
        client.post(f"/sales-invoices/{inv['id']}/mark-issued", headers=headers, json={"so_hoa_don": so_hd, "ky_hieu": "X"})

    issued("2026-07-25", "1")  # mới 6 ngày -> chưa quá hạn
    assert "receivable_overdue" not in _types(find_alerts(db_session, today=TODAY))

    issued("2026-05-01", "2")  # 91 ngày -> quá hạn
    alert = next(a for a in find_alerts(db_session, today=TODAY) if a["type"] == "receivable_overdue")
    assert alert["title"].startswith("1 hoá đơn")
    assert "20.000" in alert["detail"]


def test_top_seller_missing_id_card_alert_clears_when_added(client, giam_doc_user, db_session):
    from app.services.watchdog_service import find_alerts

    headers = auth_headers(client, "director_test")
    no_id = _seller(client, headers, "Thiếu Căn Cước")
    has_id = _seller(client, headers, "Đủ Căn Cước", id_card_number="079090001234")
    _voucher(client, headers, no_id["id"], "2026-07-05", 100, 15000)
    _voucher(client, headers, has_id["id"], "2026-07-06", 100, 15000)

    alert = next(a for a in find_alerts(db_session, today=TODAY) if a["type"] == "seller_missing_id")
    assert "Thiếu Căn Cước" in alert["detail"] and "Đủ Căn Cước" not in alert["detail"]

    client.patch(f"/sellers/{no_id['id']}", headers=headers, json={"id_card_number": "079090009999"})
    assert "seller_missing_id" not in _types(find_alerts(db_session, today=TODAY))


def test_alerts_endpoint_requires_auth_and_returns_list(client, giam_doc_user):
    assert client.get("/agent/alerts").status_code == 401
    resp = client.get("/agent/alerts", headers=auth_headers(client, "director_test"))
    assert resp.status_code == 200
    assert resp.json() == []
