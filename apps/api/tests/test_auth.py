from fastapi.testclient import TestClient

from hakim_api.main import app


def test_admin_login_and_list_users() -> None:
    client = TestClient(app)
    response = client.post(
        "/v1/auth/login",
        json={"identifier": "admin", "password": "admin1234"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["user"]["role"] == "admin"
    assert body["user"]["username"] == "admin"
    token = body["token"]
    listed = client.get("/v1/auth/users", headers={"Authorization": f"Bearer {token}"})
    assert listed.status_code == 200
    names = {row["username"] for row in listed.json()["users"]}
    assert "admin" in names


def test_login_rejects_wrong_password() -> None:
    client = TestClient(app)
    response = client.post(
        "/v1/auth/login",
        json={"identifier": "admin", "password": "wrong-pass"},
    )
    assert response.status_code == 401


def test_register_requires_verification() -> None:
    client = TestClient(app)
    created = client.post(
        "/v1/auth/register",
        json={
            "username": "avukat1",
            "email": "avukat1@example.com",
            "password": "avukat12",
            "display_name": "Avukat",
        },
    )
    assert created.status_code == 200
    body = created.json()
    assert body["status"] == "pending_verification"
    assert body.get("preview_code")
    blocked = client.post(
        "/v1/auth/login",
        json={"identifier": "avukat1", "password": "avukat12"},
    )
    assert blocked.status_code == 403
    verified = client.post(
        "/v1/auth/verify",
        json={"identifier": "avukat1", "code": body["preview_code"]},
    )
    assert verified.status_code == 200
    user_token = verified.json()["token"]
    client.post(
        "/v1/islem",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"text": "Bankadan dolandırıldım, paramı aldılar. Savcılığa şikayet etmek istiyorum."},
    )
    admin = client.post(
        "/v1/auth/login",
        json={"identifier": "admin", "password": "admin1234"},
    ).json()
    activity = client.get(
        "/v1/auth/activity",
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert activity.status_code == 200
    kinds = {row["kind"] for row in activity.json()["activity"]}
    assert "islem" in kinds
    names = {row["username"] for row in activity.json()["activity"]}
    assert "avukat1" in names


def test_user_cannot_list_accounts() -> None:
    client = TestClient(app)
    created = client.post(
        "/v1/auth/register",
        json={
            "username": "okur1",
            "email": "okur1@example.com",
            "password": "okur123",
            "display_name": "Okur",
        },
    )
    verified = client.post(
        "/v1/auth/verify",
        json={"identifier": "okur1", "code": created.json()["preview_code"]},
    )
    token = verified.json()["token"]
    response = client.get("/v1/auth/users", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


def test_admin_creates_user() -> None:
    client = TestClient(app)
    admin = client.post(
        "/v1/auth/login",
        json={"identifier": "admin", "password": "admin1234"},
    ).json()
    response = client.post(
        "/v1/auth/users",
        headers={"Authorization": f"Bearer {admin['token']}"},
        json={
            "username": "stajyer1",
            "email": "stajyer1@example.com",
            "password": "stajyer1",
            "display_name": "Stajyer",
            "role": "user",
        },
    )
    assert response.status_code == 200
    assert response.json()["user"]["username"] == "stajyer1"
    login = client.post(
        "/v1/auth/login",
        json={"identifier": "stajyer1", "password": "stajyer1"},
    )
    assert login.status_code == 200


def test_forgot_password_reset() -> None:
    client = TestClient(app)
    created = client.post(
        "/v1/auth/register",
        json={
            "username": "reset1",
            "email": "reset1@example.com",
            "password": "eski123",
            "display_name": "Reset",
        },
    )
    assert created.status_code == 200
    verify = client.post(
        "/v1/auth/verify",
        json={"identifier": "reset1", "code": created.json()["preview_code"]},
    )
    assert verify.status_code == 200
    forgot = client.post("/v1/auth/forgot", json={"identifier": "reset1"})
    assert forgot.status_code == 200
    code = forgot.json().get("preview_code")
    assert code
    bad = client.post(
        "/v1/auth/reset",
        json={"identifier": "reset1", "code": "000000", "password": "yeni1234"},
    )
    assert bad.status_code == 401
    reset = client.post(
        "/v1/auth/reset",
        json={"identifier": "reset1", "code": code, "password": "yeni1234"},
    )
    assert reset.status_code == 200
    old = client.post(
        "/v1/auth/login",
        json={"identifier": "reset1", "password": "eski123"},
    )
    assert old.status_code == 401
    fresh = client.post(
        "/v1/auth/login",
        json={"identifier": "reset1", "password": "yeni1234"},
    )
    assert fresh.status_code == 200
