# AI Changes Log

## [Unreleased]
- Removed duplicated `admin/openapi/openapi.json` and pointed admin type generation at root `openapi.json`.
- Generated frontend types from root specification.
- Generated bot types (`bot_types.gen.py`) from root specification.
- Documented specification update process in `README.md`.
- Improved API client handling: return `null` for 204 responses, parse JSON error messages when possible and fall back to status text, and updated API modules to account for potential `null` results.
