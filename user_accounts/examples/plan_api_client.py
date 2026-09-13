"""Fictional local API walkthrough using cookies and CSRF protection."""

import httpx


BASE_URL = "http://127.0.0.1:8001"


with httpx.Client(base_url=BASE_URL, follow_redirects=False) as client:
    csrf = client.get("/api/auth/csrf").json()["csrf_token"]
    registration = client.post(
        "/api/auth/register",
        headers={"X-CSRF-Token": csrf, "Origin": BASE_URL},
        json={
            "email": "fictional.developer@example.com",
            "password": "fictional-pass-123",
            "password_confirmation": "fictional-pass-123",
        },
    )
    registration.raise_for_status()
    print(registration.json()["redirect_url"])

    current = client.get("/api/plans/current")
    current.raise_for_status()
    print(current.json())
