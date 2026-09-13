"""Run the standalone local authentication service."""

import uvicorn

from .app import create_app
from .configuration import AccountSettings


def main() -> None:
    settings = AccountSettings()
    uvicorn.run(
        create_app(settings),
        host=settings.auth_host,
        port=settings.auth_port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
