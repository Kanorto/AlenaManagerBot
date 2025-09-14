# AI Changes Log

## [Unreleased]
- Removed duplicated `admin/openapi/openapi.json` and pointed admin type generation at root `openapi.json`.
- Generated frontend types from root specification.
- Generated bot types (`bot_types.gen.py`) from root specification.
- Documented specification update process in `README.md`.
- Implemented structured API error handling and updated bot handlers to send friendly fallback messages.
