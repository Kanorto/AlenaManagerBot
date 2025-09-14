# AI Changes Log

## [Unreleased]
- Removed duplicated `admin/openapi/openapi.json` and pointed admin type generation at root `openapi.json`.
- Generated frontend types from root specification.
- Generated bot types (`bot_types.gen.py`) from root specification.
- Documented specification update process in `README.md`.
- Enhanced `RoleGuard` to redirect unauthorised users to `/login` while
  displaying "Access denied" message and notification.
- Added unit test for `RoleGuard` and testing dependency
  `@testing-library/react`.
