# AI Changes Log

## [Unreleased]
- Implemented exponential backoff with jitter and `Retry-After` handling for Telegram API requests.
- Removed duplicated `admin/openapi/openapi.json` and pointed admin type generation at root `openapi.json`.
- Generated frontend types from root specification.
- Generated bot types (`bot_types.gen.py`) from root specification.
- Documented specification update process in `README.md`.
