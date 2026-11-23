import openpyxl
from io import BytesIO

from tests.conftest import auth_headers


def test_export_grouped_by_seller_produces_valid_file_with_correct_grouping(client, giam_doc_user):
    headers = auth_headers(client, "director_test")

    s1 = client.post("/sellers/", headers=headers, json={"name": "Nguyễn Văn A"}).json()
    s2 = client.post("/sellers/", headers=headers, json={"name": "Trần Thị B"}).json()

    for seller, amount in [(s1, 100000), (s1, 200000), (s2, 300000)]:
        client.post(
            "/vouchers/", headers=headers,
            json={"ngay": "2026-07-05", "seller_id": seller["id"], "ly_do_chi": "test", "so_tien": amount},
        )

    resp = client.get("/export/grouped-by-seller", headers=headers, params={"month": 7, "year": 2026})
    assert resp.status_code == 200, resp.json()
    assert resp.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    wb = openpyxl.load_workbook(BytesIO(resp.content), data_only=True)
    ws = wb.active
    group_headers = [
        ws.cell(row=r, column=1).value
        for r in range(1, ws.max_row + 1)
        if ws.cell(row=r, column=1).value and str(ws.cell(row=r, column=1).value).startswith("NGƯỜI BÁN")
    ]
    assert len(group_headers) == 2
    # Alphabet: "Nguyễn Văn A" phải đứng trước "Trần Thị B" (N < T)
    assert "Nguyễn Văn A" in group_headers[0]
    assert "(Số phiếu: 2)" in group_headers[0]
    assert "Trần Thị B" in group_headers[1]
    assert "(Số phiếu: 1)" in group_headers[1]


def test_export_grouped_by_seller_uses_template_layout(client, giam_doc_user):
    headers = auth_headers(client, "director_test")

    seller = client.post("/sellers/", headers=headers, json={"name": "Nguyễn Văn A"}).json()
    client.post(
        "/vouchers/",
        headers=headers,
        json={"ngay": "2026-07-05", "seller_id": seller["id"], "ly_do_chi": "test", "so_tien": 100000},
    )

    resp = client.get("/export/grouped-by-seller", headers=headers, params={"month": 7, "year": 2026})
    assert resp.status_code == 200

    wb = openpyxl.load_workbook(BytesIO(resp.content), data_only=False)
    ws = wb.active

    assert ws.max_column == 62
    merged_ranges = {str(rng) for rng in ws.merged_cells.ranges}
    assert "A2:AI2" in merged_ranges
    assert "T5:AJ5" in merged_ranges
    assert ws["T5"].value == "PHIẾU CHI "
    assert ws["T5"].font.name == "Times New Roman"
    assert ws["T5"].font.size == 16
    assert ws["F12"].number_format == "#,##0_);[Red](#,##0)"
    assert ws.row_dimensions[5].height == 20.25
    assert ws.row_dimensions[6].height == 15.75


def test_export_bang_ke_total_matches_sum_of_vouchers(client, giam_doc_user):
    headers = auth_headers(client, "director_test")
    seller = client.post("/sellers/", headers=headers, json={"name": "Nguyễn Văn A"}).json()

    amounts = [1_000_000, 2_500_000, 3_144_000]
    for amount in amounts:
        client.post(
            "/vouchers/", headers=headers,
            json={"ngay": "2026-07-05", "seller_id": seller["id"], "ly_do_chi": "test", "so_tien": amount},
        )

    resp = client.get("/export/bang-ke-02-tndn", headers=headers, params={"month": 7, "year": 2026})
    assert resp.status_code == 200

    wb = openpyxl.load_workbook(BytesIO(resp.content), data_only=True)
    ws = wb.active
    found_total = None
    for row in ws.iter_rows():
        for cell in row:
            if cell.value == "Tổng giá trị hàng hóa, dịch vụ mua vào:":
                found_total = ws.cell(row=cell.row, column=9).value
    assert found_total == sum(amounts)


def test_export_excludes_void_vouchers(client, giam_doc_user):
    headers = auth_headers(client, "director_test")
    seller = client.post("/sellers/", headers=headers, json={"name": "Nguyễn Văn A"}).json()

    v = client.post(
        "/vouchers/", headers=headers,
        json={"ngay": "2026-07-05", "seller_id": seller["id"], "ly_do_chi": "test", "so_tien": 500000},
    ).json()
    client.post(f"/vouchers/{v['id']}/void", headers=headers, json={"ly_do_huy": "test"})

    resp = client.get("/export/grouped-by-seller", headers=headers, params={"month": 7, "year": 2026})
    wb = openpyxl.load_workbook(BytesIO(resp.content), data_only=True)
    ws = wb.active
    all_values = [c.value for row in ws.iter_rows() for c in row if c.value]
    assert not any("NGƯỜI BÁN" in str(v) for v in all_values)  # không nhóm nào được tạo vì phiếu duy nhất đã bị huỷ
