# Jack Butler — Guitar Pro Music Theory Analyzer

## Project structure

- `src/jackbutler/` — Python package (FastAPI app, parsing, analysis)
- `src/jackbutler/static/` — Frontend (HTML, JS, CSS)
- `tests/` — pytest test suite
- `tabs/` — Guitar Pro demo files

## Testing conventions

- Framework: **pytest** (`python -m pytest`)
- Test files live in `tests/`, named `test_<module>.py`
- Fixtures go in `tests/conftest.py` (shared) or as local fixtures in the test file
- Use `scope="module"` fixtures for expensive operations (parsing GP files, running analysis)
- Real tablature files in `tabs/` can be used for integration tests (skip with `pytest.skip()` if not available)
- For frontend JS logic, reimplement the relevant functions in Python and test the logic directly (see `tests/test_accidentals.py` for the pattern)

## Dev server

```bash
bash dev.sh   # starts uvicorn with --reload on port 8000
```

## Code style

- Python: type hints, Pydantic models, no docstrings on obvious code
- Keep changes minimal — don't refactor surrounding code unless asked
- Frontend JS lives in `src/jackbutler/static/app.js` (single file)
