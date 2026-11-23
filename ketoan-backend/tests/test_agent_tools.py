from tests.conftest import auth_headers


def test_handle_search_seller_finds_exact_and_fuzzy_match(client, giam_doc_user, db_session):
    from app.agent.tools import handle_search_seller

    headers = auth_headers(client, "director_test")
    client.post("/sellers/", headers=headers, json={"name": "Nguyễn Văn Kiếm"})

    result = handle_search_seller(db_session, query="nguyen van kiem")
    assert result["found"] is True
    assert result["sellers"][0]["name"] == "Nguyễn Văn Kiếm"


def test_handle_search_seller_falls_back_to_partial_match(client, giam_doc_user, db_session):
    """Gõ 1 phần tên, không đủ giống 85% để fuzzy match -> vẫn tìm được nhờ fallback ILIKE."""
    from app.agent.tools import handle_search_seller

    headers = auth_headers(client, "director_test")
    client.post("/sellers/", headers=headers, json={"name": "Nguyễn Văn Kiếm"})

    result = handle_search_seller(db_session, query="Kiếm")
    assert result["found"] is True
    assert any(s["name"] == "Nguyễn Văn Kiếm" for s in result["sellers"])


def test_handle_search_seller_no_match(db_session):
    from app.agent.tools import handle_search_seller

    result = handle_search_seller(db_session, query="Không Ai Tên Vậy Cả")
    assert result["found"] is False


def test_handle_search_seller_strips_honorific_without_false_prefix_match(client, giam_doc_user, db_session):
    from app.agent.tools import handle_search_seller, _resolve_seller_by_name

    headers = auth_headers(client, "director_test")
    client.post("/sellers/", headers=headers, json={"name": "Nguyễn Văn Bảo"})
    ba = client.post("/sellers/", headers=headers, json={"name": "Trần Văn Ba"}).json()

    assert handle_search_seller(db_session, query="   ")["found"] is False
    resolved = _resolve_seller_by_name(db_session, "chú Ba")
    assert resolved is not None and str(resolved.id) == ba["id"]
    search = handle_search_seller(db_session, query="chú Ba")
    assert [s["name"] for s in search["sellers"]] == ["Trần Văn Ba"]


def test_handle_get_monthly_summary_total_company(client, giam_doc_user, db_session):
    from app.agent.tools import handle_get_monthly_summary

    headers = auth_headers(client, "director_test")
    s1 = client.post("/sellers/", headers=headers, json={"name": "Người A"}).json()
    s2 = client.post("/sellers/", headers=headers, json={"name": "Người B"}).json()
    client.post("/vouchers/", headers=headers, json={"ngay": "2026-07-05", "seller_id": s1["id"], "ly_do_chi": "t", "so_tien": 1000000})
    client.post("/vouchers/", headers=headers, json={"ngay": "2026-07-06", "seller_id": s2["id"], "ly_do_chi": "t", "so_tien": 2000000})

    result = handle_get_monthly_summary(db_session, month=7, year=2026)
    assert result["tong_so_tien"] == 3000000
    assert result["so_luong_phieu"] == 2
    assert result["nguoi_ban"] is None


def test_handle_get_monthly_summary_filtered_by_seller(client, giam_doc_user, db_session):
    from app.agent.tools import handle_get_monthly_summary

    headers = auth_headers(client, "director_test")
    s1 = client.post("/sellers/", headers=headers, json={"name": "Nguyễn Văn Kiếm"}).json()
    s2 = client.post("/sellers/", headers=headers, json={"name": "Người Khác"}).json()
    client.post("/vouchers/", headers=headers, json={"ngay": "2026-07-05", "seller_id": s1["id"], "ly_do_chi": "t", "so_tien": 1000000})
    client.post("/vouchers/", headers=headers, json={"ngay": "2026-07-06", "seller_id": s2["id"], "ly_do_chi": "t", "so_tien": 9999999})

    result = handle_get_monthly_summary(db_session, month=7, year=2026, seller_name="kiem")
    assert result["tong_so_tien"] == 1000000
    assert result["so_luong_phieu"] == 1
    assert result["nguoi_ban"] == "Nguyễn Văn Kiếm"


def test_handle_get_monthly_summary_excludes_void(client, giam_doc_user, db_session):
    from app.agent.tools import handle_get_monthly_summary

    headers = auth_headers(client, "director_test")
    seller = client.post("/sellers/", headers=headers, json={"name": "Người A"}).json()
    v = client.post("/vouchers/", headers=headers, json={"ngay": "2026-07-05", "seller_id": seller["id"], "ly_do_chi": "t", "so_tien": 500000}).json()
    client.post(f"/vouchers/{v['id']}/void", headers=headers, json={"ly_do_huy": "test"})

    result = handle_get_monthly_summary(db_session, month=7, year=2026)
    assert result["tong_so_tien"] == 0


def test_handle_get_monthly_summary_unknown_seller(db_session):
    from app.agent.tools import handle_get_monthly_summary

    result = handle_get_monthly_summary(db_session, month=7, year=2026, seller_name="Không Tồn Tại")
    assert "error" in result


def test_handle_get_monthly_summary_invalid_month(db_session):
    from app.agent.tools import handle_get_monthly_summary

    result = handle_get_monthly_summary(db_session, month=13, year=2026)
    assert "error" in result


# ---------------------------------------------------------------------------
# Tool mới: get_receivables / get_price_history / propose_voucher_draft
# ---------------------------------------------------------------------------

def _mk_seller(client, headers, name="Nguyễn Văn Kiếm"):
    return client.post("/sellers/", headers=headers, json={"name": name}).json()


def _mk_voucher(client, headers, seller_id, ngay, so_luong, don_gia):
    return client.post("/vouchers/", headers=headers, json={
        "ngay": str(ngay), "seller_id": seller_id, "ly_do_chi": "Mua mủ",
        "so_luong": so_luong, "don_gia": don_gia, "so_tien": so_luong * don_gia,
    }).json()


def _count_vouchers(db_session):
    from sqlalchemy import select, func
    from app.models.voucher import Voucher

    return db_session.execute(select(func.count()).select_from(Voucher)).scalar_one()


def test_get_receivables_counts_only_issued_unpaid_and_filters_by_customer(client, giam_doc_user, db_session):
    from app.agent.tools import handle_get_receivables

    headers = auth_headers(client, "director_test")
    partner_a = client.post("/customers/", headers=headers, json={"company_name": "Đối Tác A"}).json()
    khac = client.post("/customers/", headers=headers, json={"company_name": "Công ty Khác"}).json()

    def issue(customer, don_gia, so_hd):
        inv = client.post("/sales-invoices/", headers=headers, json={
            "ngay": "2026-01-01", "customer_id": customer["id"], "ten_hang": "Mủ", "so_luong": 10, "don_gia": don_gia,
        }).json()
        client.post(f"/sales-invoices/{inv['id']}/mark-issued", headers=headers, json={"so_hoa_don": so_hd, "ky_hieu": "X"})
        return inv

    issue(partner_a, 2000, "1")
    paid = issue(partner_a, 5000, "2")
    client.post(f"/sales-invoices/{paid['id']}/mark-paid", headers=headers)  # đã thu -> không tính
    issue(khac, 1000, "3")
    # nháp (chưa xuất) -> không tính
    client.post("/sales-invoices/", headers=headers, json={
        "ngay": "2026-01-01", "customer_id": partner_a["id"], "ten_hang": "Mủ", "so_luong": 10, "don_gia": 9999,
    })

    everyone = handle_get_receivables(db_session)
    assert everyone["tong_cong_no"] == 30_000  # 20.000 (Đối Tác A) + 10.000 (Khác)
    assert everyone["so_hoa_don_chua_thu"] == 2

    only_partner_a = handle_get_receivables(db_session, customer_name="đối tác a")
    assert only_partner_a["tong_cong_no"] == 20_000
    assert only_partner_a["theo_khach_hang"][0]["khach_hang"] == "Đối Tác A"


def test_get_receivables_empty_and_unknown_customer(db_session):
    from app.agent.tools import handle_get_receivables

    empty = handle_get_receivables(db_session)
    assert empty["tong_cong_no"] == 0 and empty["so_hoa_don_chua_thu"] == 0 and empty["theo_khach_hang"] == []
    assert "error" in handle_get_receivables(db_session, customer_name="Không Có Công Ty Này")


def test_get_price_history_stats(client, giam_doc_user, db_session):
    from datetime import date, timedelta
    from app.agent.tools import handle_get_price_history

    headers = auth_headers(client, "director_test")
    s = _mk_seller(client, headers)
    other = _mk_seller(client, headers, "Người Khác")
    today = date.today()
    for days_ago, price in [(10, 14000), (6, 15000), (2, 16000)]:
        _mk_voucher(client, headers, s["id"], today - timedelta(days=days_ago), 100, price)
    _mk_voucher(client, headers, other["id"], today - timedelta(days=1), 100, 99999)

    r = handle_get_price_history(db_session, seller_name="kiem")
    assert r["nguoi_ban"] == "Nguyễn Văn Kiếm"
    assert r["so_phieu"] == 3
    assert (r["don_gia_thap_nhat"], r["don_gia_trung_vi"], r["don_gia_cao_nhat"]) == (14000, 15000, 16000)
    assert r["don_gia_gan_nhat"] == 16000


def test_get_price_history_no_data_and_bad_input(db_session):
    from app.agent.tools import handle_get_price_history

    assert handle_get_price_history(db_session)["so_phieu"] == 0  # N = 0: trả lời rõ ràng, không lỗi
    assert "error" in handle_get_price_history(db_session, months=0)
    assert "error" in handle_get_price_history(db_session, months=25)
    assert "error" in handle_get_price_history(db_session, seller_name="Không Tồn Tại")


def test_propose_voucher_computes_total_and_never_writes_to_db(client, giam_doc_user, db_session):
    from app.agent.tools import handle_propose_voucher_draft

    headers = auth_headers(client, "director_test")
    s = _mk_seller(client, headers)
    before = _count_vouchers(db_session)

    result = handle_propose_voucher_draft(
        db_session, seller_name="anh kiem", ly_do_chi="Mua mủ nước", so_luong=500, don_gia=15000, ngay="2026-07-05",
    )

    p = result["proposal"]
    assert p["seller_id"] == s["id"]
    assert p["so_tien"] == 7_500_000
    assert p["ngay"] == "2026-07-05"
    assert _count_vouchers(db_session) == before  # ranh giới cứng: đề xuất KHÔNG tạo phiếu


def test_propose_voucher_unknown_seller_leaves_seller_id_empty(db_session):
    from app.agent.tools import handle_propose_voucher_draft

    p = handle_propose_voucher_draft(db_session, seller_name="Người Lạ Hoắc", ly_do_chi="Mua mủ", so_tien=1_000_000)["proposal"]
    assert p["seller_id"] is None
    assert any("Chưa khớp người bán" in w for w in p["warnings"])


def test_propose_voucher_validation_errors(db_session):
    from app.agent.tools import handle_propose_voucher_draft

    assert "error" in handle_propose_voucher_draft(db_session, seller_name="A", ly_do_chi="x")  # thiếu tiền
    assert "error" in handle_propose_voucher_draft(db_session, seller_name="A", ly_do_chi="x", so_luong=10)  # thiếu đơn giá
    assert "error" in handle_propose_voucher_draft(db_session, seller_name="A", ly_do_chi="  ", so_tien=1000)
    assert "error" in handle_propose_voucher_draft(db_session, seller_name="A", ly_do_chi="x", so_tien=1000, ngay="05/07/2026")
    # số 0 là giá trị SAI chứ không phải "thiếu" — không được lọt qua như None
    assert "error" in handle_propose_voucher_draft(db_session, seller_name="A", ly_do_chi="x", so_tien=0)
    assert "error" in handle_propose_voucher_draft(db_session, seller_name="A", ly_do_chi="x", so_luong=0, don_gia=15000)


def test_propose_voucher_warns_on_arithmetic_mismatch_and_price_outlier(client, giam_doc_user, db_session):
    from app.agent.tools import handle_propose_voucher_draft

    headers = auth_headers(client, "director_test")
    s = _mk_seller(client, headers)
    for day in (1, 3, 5):
        _mk_voucher(client, headers, s["id"], f"2026-07-0{day}", 100, 15000)

    mismatch = handle_propose_voucher_draft(
        db_session, seller_name="Kiếm", ly_do_chi="Mua mủ", so_luong=100, don_gia=15000, so_tien=9_000_000, ngay="2026-07-10",
    )["proposal"]
    assert any("không khớp" in w for w in mismatch["warnings"])

    outlier = handle_propose_voucher_draft(
        db_session, seller_name="Kiếm", ly_do_chi="Mua mủ", so_luong=100, don_gia=30000, ngay="2026-07-10",
    )["proposal"]
    assert any("lệch" in w for w in outlier["warnings"])

    normal = handle_propose_voucher_draft(
        db_session, seller_name="Kiếm", ly_do_chi="Mua mủ", so_luong=100, don_gia=15500, ngay="2026-07-10",
    )["proposal"]
    assert not any("lệch" in w for w in normal["warnings"])
