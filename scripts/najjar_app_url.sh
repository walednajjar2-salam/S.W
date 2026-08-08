#!/usr/bin/env bash
# Canonical launch URL for NAJJAR native shells (Android WebView + Windows launcher).
NAJJAR_PRODUCTION="${LQ_PRODUCTION_URL:-https://web-production-08d73.up.railway.app}"
NAJJAR_BASE_PATH="${LQ_NAJJAR_BASE:-/najjar-al-samoom-used-imported-cars}"
export NAJJAR_APP_URL="${LQ_APP_URL:-${NAJJAR_PRODUCTION}${NAJJAR_BASE_PATH}/login.html}"
