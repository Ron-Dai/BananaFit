def test_login_page_uses_established_english_style(client):
    response = client.get("/login")
    assert response.status_code == 200
    assert 'lang="en"' in response.text
    assert "Welcome back" in response.text
    assert "ForgeFit" in response.text
    assert "Ron Forge" not in response.text
    css = client.get("/auth-static/auth.css").text
    assert "#ed7048" in css
    assert "#f4f4f6" in css
    assert "Sora" in css and "Manrope" in css


def test_registration_page_is_accessible_and_english(client):
    response = client.get("/register")
    assert response.status_code == 200
    assert "Create your account" in response.text
    assert 'autocomplete="new-password"' in response.text
    assert 'role="alert"' in response.text
    assert "登录" not in response.text


def test_security_headers_are_present(client):
    response = client.get("/login")
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["cache-control"] == "no-store"
