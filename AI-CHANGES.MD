# AI Changes Log

## [Unreleased]
- Removed duplicated `admin/openapi/openapi.json` and pointed admin type generation at root `openapi.json`.
- Generated frontend types from root specification.
- Generated bot types (`bot_types.gen.py`) from root specification.
- Documented specification update process in `README.md`.
- Combined menu prompt and keyboard into a single sendMessage call by adding optional `reply_markup` to `_send_message` and simplifying `_send_main_menu`.
