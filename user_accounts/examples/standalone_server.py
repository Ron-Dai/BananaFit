"""Run the account component without changing SexyBanana's existing server.py."""

import uvicorn

from sexybanana_accounts import AccountSettings, create_app


settings = AccountSettings()
app = create_app(settings)


if __name__ == "__main__":
    uvicorn.run(app, host=settings.auth_host, port=settings.auth_port)
