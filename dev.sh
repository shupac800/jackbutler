#!/usr/bin/env bash
cd "$(dirname "$0")"
python -m uvicorn jackbutler.app:app --reload --port 8000
