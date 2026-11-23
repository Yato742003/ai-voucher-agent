from tests.conftest import auth_headers


def test_login_success(client, giam_doc_user):
    resp = client.post("/auth/login", data={"username": "director_test", "password": "test12345"})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


def test_login_wrong_password(client, giam_doc_user):
    resp = client.post("/auth/login", data={"username": "director_test", "password": "sai"})
    assert resp.status_code == 401


def test_login_rate_limit_locks_after_max_attempts(client, giam_doc_user):
    from app.api.auth import MAX_ATTEMPTS

    # Đúng MAX_ATTEMPTS lần sai đầu tiên đều được coi là lần thử hợp lệ (401,
    # không bị chặn) — rate limit chỉ chặn khi đã CÓ SẴN >= MAX_ATTEMPTS lần
    # thất bại gần đây, tức là chặn từ lần thử thứ (MAX_ATTEMPTS + 1) trở đi.
    for _ in range(MAX_ATTEMPTS):
        resp = client.post("/auth/login", data={"username": "director_test", "password": "sai"})
        assert resp.status_code == 401

    resp = client.post("/auth/login", data={"username": "director_test", "password": "sai"})
    assert resp.status_code == 429

    # Kể cả gõ ĐÚNG mật khẩu lúc này cũng vẫn bị khoá (đang trong thời gian khoá)
    resp = client.post("/auth/login", data={"username": "director_test", "password": "test12345"})
    assert resp.status_code == 429


def test_change_password(client, giam_doc_user):
    headers = auth_headers(client, "director_test")

    resp = client.post(
        "/auth/change-password",
        headers=headers,
        json={"current_password": "test12345", "new_password": "matkhaumoi123"},
    )
    assert resp.status_code == 200

    # mật khẩu cũ không còn dùng được
    resp = client.post("/auth/login", data={"username": "director_test", "password": "test12345"})
    assert resp.status_code == 401

    # mật khẩu mới dùng được
    resp = client.post("/auth/login", data={"username": "director_test", "password": "matkhaumoi123"})
    assert resp.status_code == 200


def test_change_password_wrong_current(client, giam_doc_user):
    headers = auth_headers(client, "director_test")
    resp = client.post(
        "/auth/change-password",
        headers=headers,
        json={"current_password": "sai_mat_khau_hien_tai", "new_password": "matkhaumoi123"},
    )
    assert resp.status_code == 400


def test_access_without_token_rejected(client):
    resp = client.get("/sellers/")
    assert resp.status_code == 401
