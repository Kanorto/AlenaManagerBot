# AI Changes Log

## [Unreleased]
- Removed duplicated `admin/openapi/openapi.json` and pointed admin type generation at root `openapi.json`.
- Generated frontend types from root specification.
- Generated bot types (`bot_types.gen.py`) from root specification.
- Documented specification update process in `README.md`.
- Moved social login DB logic into `UserService` with provider whitelist and uniqueness check.
- Added `UserService.social_login` method and updated API endpoint to use it.
