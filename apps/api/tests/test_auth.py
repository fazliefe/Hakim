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
            "password": "avukat1200",
            "display_name": "Avukat",
        },
    )
    assert created.status_code == 200
    body = created.json()
    assert body["status"] == "pending_verification"
    assert body.get("preview_code")
    blocked = client.post(
        "/v1/auth/login",
        json={"identifier": "avukat1", "password": "avukat1200"},
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
    assert "islem" not in kinds
    assert "evrak" not in kinds
    assert kinds <= {
        "register",
        "login",
        "verify",
        "password_reset_request",
        "password_reset",
        "password_change",
        "email_change_request",
        "email_change",
        "profile_update",
        "session_revoke",
        "admin_create_user",
        "admin_set_role",
        "admin_lock",
        "admin_unlock",
        "admin_delete_user",
        "admin_revoke_sessions",
        "admin_send_password",
    }
    assert "register" in kinds or "login" in kinds or "verify" in kinds
    names = {row["username"] for row in activity.json()["activity"]}
    assert "avukat1" in names


def test_user_cannot_list_accounts() -> None:
    client = TestClient(app)
    created = client.post(
        "/v1/auth/register",
        json={
            "username": "okur1",
            "email": "okur1@example.com",
            "password": "okur123456",
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
            "password": "stajyer100",
            "display_name": "Stajyer",
            "role": "user",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["user"]["username"] == "stajyer1"
    assert body["user"]["email_verified"] is False
    assert body.get("preview_code")
    blocked = client.post(
        "/v1/auth/login",
        json={"identifier": "stajyer1", "password": "stajyer100"},
    )
    assert blocked.status_code == 403
    verified = client.post(
        "/v1/auth/verify",
        json={"identifier": "stajyer1", "code": body["preview_code"]},
    )
    assert verified.status_code == 200
    login = client.post(
        "/v1/auth/login",
        json={"identifier": "stajyer1", "password": "stajyer100"},
    )
    assert login.status_code == 200


def test_forgot_password_reset() -> None:
    client = TestClient(app)
    created = client.post(
        "/v1/auth/register",
        json={
            "username": "reset1",
            "email": "reset1@example.com",
            "password": "eski123456",
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
        json={"identifier": "reset1", "code": "000000", "password": "yeni123456"},
    )
    assert bad.status_code == 401
    reset = client.post(
        "/v1/auth/reset",
        json={"identifier": "reset1", "code": code, "password": "yeni123456"},
    )
    assert reset.status_code == 200
    old = client.post(
        "/v1/auth/login",
        json={"identifier": "reset1", "password": "eski123456"},
    )
    assert old.status_code == 401
    fresh = client.post(
        "/v1/auth/login",
        json={"identifier": "reset1", "password": "yeni123456"},
    )
    assert fresh.status_code == 200


def test_forgot_unknown_account_same_response() -> None:
    client = TestClient(app)
    known = client.post(
        "/v1/auth/register",
        json={
            "username": "reset2",
            "email": "reset2@example.com",
            "password": "eski123456",
            "display_name": "Reset",
        },
    )
    assert known.status_code == 200
    client.post("/v1/auth/verify", json={"identifier": "reset2", "code": known.json()["preview_code"]})
    existing = client.post("/v1/auth/forgot", json={"identifier": "reset2"})
    missing = client.post("/v1/auth/forgot", json={"identifier": "yok_boyle_hesap"})
    assert existing.status_code == 200
    assert missing.status_code == 200
    assert set(existing.json().keys()) == set(missing.json().keys())
    assert existing.json()["message"] == missing.json()["message"]
    assert existing.json()["mailed"] == missing.json()["mailed"]
    assert existing.json()["smtp"] == missing.json()["smtp"]


def test_register_rejects_short_password() -> None:
    client = TestClient(app)
    response = client.post(
        "/v1/auth/register",
        json={
            "username": "kisa1",
            "email": "kisa1@example.com",
            "password": "abc12",
            "display_name": "Kisa",
        },
    )
    assert response.status_code == 422


def _admin_token(client: TestClient) -> str:
    return client.post(
        "/v1/auth/login",
        json={"identifier": "admin", "password": "admin1234"},
    ).json()["token"]


def _register_verified(client: TestClient, username: str, email: str, password: str) -> dict:
    created = client.post(
        "/v1/auth/register",
        json={
            "username": username,
            "email": email,
            "password": password,
            "display_name": username,
        },
    )
    assert created.status_code == 200
    verified = client.post(
        "/v1/auth/verify",
        json={"identifier": username, "code": created.json()["preview_code"]},
    )
    assert verified.status_code == 200
    return verified.json()


def test_admin_lock_role_revoke_and_delete() -> None:
    client = TestClient(app)
    token = _admin_token(client)
    auth = {"Authorization": f"Bearer {token}"}
    created = client.post(
        "/v1/auth/users",
        headers=auth,
        json={
            "username": "kilit1",
            "email": "kilit1@example.com",
            "password": "kilit12345",
            "display_name": "Kilit",
            "role": "user",
        },
    )
    assert created.status_code == 200
    user_id = created.json()["user"]["id"]
    client.post("/v1/auth/verify", json={"identifier": "kilit1", "code": created.json()["preview_code"]})
    locked = client.patch(f"/v1/auth/users/{user_id}", headers=auth, json={"locked": True})
    assert locked.status_code == 200
    assert locked.json()["user"]["locked"] is True
    blocked = client.post("/v1/auth/login", json={"identifier": "kilit1", "password": "kilit12345"})
    assert blocked.status_code == 403
    opened = client.patch(f"/v1/auth/users/{user_id}", headers=auth, json={"locked": False, "role": "admin"})
    assert opened.status_code == 200
    assert opened.json()["user"]["role"] == "admin"
    assert opened.json()["user"]["locked"] is False
    login = client.post("/v1/auth/login", json={"identifier": "kilit1", "password": "kilit12345"})
    assert login.status_code == 200
    revoked = client.post(f"/v1/auth/users/{user_id}/revoke-sessions", headers=auth)
    assert revoked.status_code == 200
    me = client.get("/v1/auth/me", headers={"Authorization": f"Bearer {login.json()['token']}"})
    assert me.status_code == 401
    deleted = client.delete(f"/v1/auth/users/{user_id}", headers=auth)
    assert deleted.status_code == 200
    missing = client.post("/v1/auth/login", json={"identifier": "kilit1", "password": "kilit12345"})
    assert missing.status_code == 401


def test_admin_sends_password_email() -> None:
    client = TestClient(app)
    token = _admin_token(client)
    auth = {"Authorization": f"Bearer {token}"}
    created = client.post(
        "/v1/auth/users",
        headers=auth,
        json={
            "username": "posta1",
            "email": "posta1@example.com",
            "password": "eski123456",
            "display_name": "Posta",
            "role": "user",
        },
    )
    assert created.status_code == 200
    user_id = created.json()["user"]["id"]
    client.post("/v1/auth/verify", json={"identifier": "posta1", "code": created.json()["preview_code"]})
    old = client.post("/v1/auth/login", json={"identifier": "posta1", "password": "eski123456"})
    assert old.status_code == 200
    sent = client.post(f"/v1/auth/users/{user_id}/send-password", headers=auth)
    assert sent.status_code == 200
    body = sent.json()
    assert body["mailed"] is False
    password = body.get("preview_password")
    assert password
    blocked = client.post("/v1/auth/login", json={"identifier": "posta1", "password": "eski123456"})
    assert blocked.status_code == 401
    fresh = client.post("/v1/auth/login", json={"identifier": "posta1", "password": password})
    assert fresh.status_code == 200
    dead = client.get("/v1/auth/me", headers={"Authorization": f"Bearer {old.json()['token']}"})
    assert dead.status_code == 401
    user = _register_verified(client, "posta2", "posta2@example.com", "posta12345")
    denied = client.post(
        f"/v1/auth/users/{user_id}/send-password",
        headers={"Authorization": f"Bearer {user['token']}"},
    )
    assert denied.status_code == 403


def test_cannot_delete_self_or_last_admin() -> None:
    client = TestClient(app)
    admin = client.post("/v1/auth/login", json={"identifier": "admin", "password": "admin1234"}).json()
    auth = {"Authorization": f"Bearer {admin['token']}"}
    admin_id = admin["user"]["id"]
    denied = client.delete(f"/v1/auth/users/{admin_id}", headers=auth)
    assert denied.status_code == 400
    locked = client.patch(f"/v1/auth/users/{admin_id}", headers=auth, json={"locked": True})
    assert locked.status_code == 400
    demote = client.patch(f"/v1/auth/users/{admin_id}", headers=auth, json={"role": "user"})
    assert demote.status_code == 400


def test_password_and_email_settings() -> None:
    client = TestClient(app)
    session = _register_verified(client, "ayar1", "ayar1@example.com", "eski123456")
    headers = {"Authorization": f"Bearer {session['token']}"}
    bad = client.post(
        "/v1/auth/password",
        headers=headers,
        json={"current_password": "wrong", "new_password": "yeni123456"},
    )
    assert bad.status_code == 401
    changed = client.post(
        "/v1/auth/password",
        headers=headers,
        json={"current_password": "eski123456", "new_password": "yeni123456"},
    )
    assert changed.status_code == 200
    old = client.post("/v1/auth/login", json={"identifier": "ayar1", "password": "eski123456"})
    assert old.status_code == 401
    still = client.get("/v1/auth/me", headers=headers)
    assert still.status_code == 200
    email_req = client.post(
        "/v1/auth/email",
        headers=headers,
        json={"password": "yeni123456", "email": "ayar1b@example.com"},
    )
    assert email_req.status_code == 200
    code = email_req.json().get("preview_code")
    assert code
    confirmed = client.post("/v1/auth/email/confirm", headers=headers, json={"code": code})
    assert confirmed.status_code == 200
    assert confirmed.json()["user"]["email"] == "ayar1b@example.com"
    login = client.post("/v1/auth/login", json={"identifier": "ayar1b@example.com", "password": "yeni123456"})
    assert login.status_code == 200


def test_profile_and_own_sessions() -> None:
    client = TestClient(app)
    first = _register_verified(client, "ayar2", "ayar2@example.com", "eski123456")
    headers = {"Authorization": f"Bearer {first['token']}"}
    profile = client.patch("/v1/auth/me", headers=headers, json={"display_name": "Avukat Ayse"})
    assert profile.status_code == 200
    assert profile.json()["user"]["display_name"] == "Avukat Ayse"
    second = client.post("/v1/auth/login", json={"identifier": "ayar2", "password": "eski123456"}).json()
    revoked = client.post("/v1/auth/sessions/revoke", headers=headers)
    assert revoked.status_code == 200
    assert revoked.json()["revoked"] >= 1
    dead = client.get("/v1/auth/me", headers={"Authorization": f"Bearer {second['token']}"})
    assert dead.status_code == 401
    alive = client.get("/v1/auth/me", headers=headers)
    assert alive.status_code == 200
