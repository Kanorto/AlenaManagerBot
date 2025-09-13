# AlenaManagerBot

This repository contains the admin panel and Telegram bot for managing events.
The canonical OpenAPI specification is stored at `openapi.json` in the project root.

## Updating the API specification

When the API schema changes:

1. Replace or edit `openapi.json` in the repository root.
2. Regenerate frontend types:
   ```bash
   npm --prefix admin run gen:api
   ```
3. Regenerate bot types:
   ```bash
   datamodel-codegen --input openapi.json --input-file-type json --output bot_types.gen.py
   ```
4. Commit the updated `openapi.json`, `admin/src/api/types.gen.ts` and `bot_types.gen.py` files.

The admin build and the Telegram bot both read the specification from `/openapi.json`.
Removing the now redundant `admin/openapi/openapi.json` prevents the specification
from diverging in the future.
