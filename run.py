"""Unified entry point for the Telegram bot and admin panel.

This script launches both the Telegram bot and the FastAPI admin panel
concurrently. It is intended to be executed from the project root,
for example under Pterodactyl or Docker, where you only specify a
single Python file to run.

Configuration such as BOT_TOKEN, database URL, admin credentials and
proxy settings should be placed in a `.env` file in the same
directory. See `tg_bot_project/.env.example` for a list of supported
variables.

Usage:
    python run.py
"""
import asyncio
import logging
import os
from uvicorn import Config, Server

# Import the bot and admin panel from the package. We rely on the fact
# that `tg_bot_project` is a package in this repository and contains
# subpackages `bot` and `admin`.
from tg_bot_project.bot.main import main as bot_main
from tg_bot_project.admin.admin_panel import app as admin_app


async def run_admin() -> None:
    """Start the admin panel using Uvicorn.

    Host and port are read from environment variables `ADMIN_HOST` and
    `ADMIN_PORT`. Defaults are `0.0.0.0` and `8000`.
    """
    admin_host = os.getenv("ADMIN_HOST", "0.0.0.0")
    admin_port = int(os.getenv("ADMIN_PORT", "8000"))
    config = Config(app=admin_app, host=admin_host, port=admin_port, reload=False, log_level="info")
    server = Server(config)
    await server.serve()


async def run_bot() -> None:
    """Launch the Telegram bot."""
    await bot_main()


async def main() -> None:
    """Run both the bot and the admin panel concurrently."""
    logging.basicConfig(level=logging.INFO)
    tasks = [asyncio.create_task(run_admin()), asyncio.create_task(run_bot())]
    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)
    for task in done:
        if exception := task.exception():
            logging.exception("Exception in service", exc_info=exception)
    for task in pending:
        task.cancel()
    await asyncio.gather(*pending, return_exceptions=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass