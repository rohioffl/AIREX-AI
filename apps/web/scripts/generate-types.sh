#!/usr/bin/env bash
# Generate TypeScript types from the FastAPI OpenAPI spec.
#
# Prerequisites:
#   npm install -g openapi-typescript (or npx)
#   Backend running at localhost:8000
#
# Usage:
#   bash frontend/scripts/generate-types.sh

set -euo pipefail

API_URL="${API_URL:-http://localhost:8000}"
OUTPUT="src/types/api.d.ts"

echo "Fetching OpenAPI spec from ${API_URL}/openapi.json..."
mkdir -p src/types

npx openapi-typescript "${API_URL}/openapi.json" -o "${OUTPUT}"

echo "Types written to ${OUTPUT}"
echo "Import with: import type { paths, components } from './types/api'"
