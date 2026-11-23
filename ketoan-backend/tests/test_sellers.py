from tests.conftest import auth_headers


def test_create_seller(client, giam_doc_user):
    headers = auth_headers(client, "director_test")
    resp = client.post("/sellers/", headers=headers, json={"name": "Nguyễn Văn A", "phone": "0900000000"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Nguyễn Văn A"
    assert body["alias_of_seller_id"] is None


def test_create_seller_blank_name_rejected(client, giam_doc_user):
    headers = auth_headers(client, "director_test")
    resp = client.post("/sellers/", headers=headers, json={"name": "   "})
    assert resp.status_code == 422


def test_duplicate_detection_finds_similar_name_ignoring_case_and_diacritics(client, giam_doc_user):
    headers = auth_headers(client, "director_test")
    client.post("/sellers/", headers=headers, json={"name": "Nguyễn Văn Kiếm"})

    resp = client.get("/sellers/check-duplicate", headers=headers, params={"name": "nguyen van kiem"})
    assert resp.status_code == 200
    candidates = resp.json()
    assert len(candidates) == 1
    assert candidates[0]["similarity_score"] == 100.0
    assert candidates[0]["seller"]["name"] == "Nguyễn Văn Kiếm"


def test_duplicate_detection_no_match_for_unrelated_name(client, giam_doc_user):
    headers = auth_headers(client, "director_test")
    client.post("/sellers/", headers=headers, json={"name": "Nguyễn Văn Kiếm"})

    resp = client.get("/sellers/check-duplicate", headers=headers, params={"name": "Trần Thị Hoa"})
    assert resp.status_code == 200
    assert resp.json() == []


def test_merge_seller_keeps_both_records_but_marks_alias(client, giam_doc_user):
    headers = auth_headers(client, "director_test")
    s1 = client.post("/sellers/", headers=headers, json={"name": "Nguyen Van Kiem (viet khong dau)"}).json()
    s2 = client.post("/sellers/", headers=headers, json={"name": "Nguyễn Văn Kiếm"}).json()

    resp = client.post(f"/sellers/{s1['id']}/merge-into/{s2['id']}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["alias_of_seller_id"] == s2["id"]

    # Bản ghi gộp không còn xuất hiện trong danh sách chính (đã lọc alias_of_seller_id IS NULL)
    listed = client.get("/sellers/", headers=headers).json()
    ids = [s["id"] for s in listed]
    assert s1["id"] not in ids
    assert s2["id"] in ids
