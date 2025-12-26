# AGENTS.md

This file provides guidelines and commands for agents working on this Python datalogger codebase. Follow these to maintain consistency, quality, and efficiency.

## Overview
The codebase is a Flask-based web application for configuring and running a datalogger that fetches sensor data from an HTML page and sends it to an ODAMS server. It includes a web admin interface and a background logger thread.

Key files:
- `datalogger_app.py`: Main application with Flask routes and logger thread.
- `config.json`: Configuration file for settings and sensors.
- `datapage.html`: Sample HTML page with sensor data (for testing).

## Build Commands

### Running the Application
- **Development**: `python datalogger_app.py` - Runs the Flask app on port 9999 with the logger thread.
- **Production**: Use a WSGI server like Gunicorn: `gunicorn -w 4 datalogger_app:app` (ensure config.json is set for production URLs).

### Dependencies
- Install: `pip install -r requirements.txt` (create if needed: requests, beautifulsoup4, pycryptodome, pytz, flask).
- Update: `pip freeze > requirements.txt`.

### Packaging
- Create wheel: `python setup.py bdist_wheel` (add setup.py if needed).
- Docker: `docker build -t datalogger .` (add Dockerfile).

## Lint Commands

### Code Quality
- **Lint**: `flake8 datalogger_app.py --max-line-length=100 --extend-ignore=E203,W503`
  - Checks for PEP8 violations, unused imports, etc.
- **Format**: `black datalogger_app.py --line-length=100`
  - Auto-formats code to Black style.
- **Type Check**: `mypy datalogger_app.py --ignore-missing-imports`
  - Enforces type hints.

### Pre-commit Hooks
- Install: `pre-commit install`
- Run: `pre-commit run --all-files`
- Config: Add .pre-commit-config.yaml with hooks for black, flake8, mypy.

## Test Commands

### Running Tests
- **All Tests**: `pytest` - Runs all tests in tests/ directory.
- **Single Test**: `pytest tests/test_logger.py::test_fetch_data -v`
  - Use -v for verbose, -s for stdout capture.
- **Coverage**: `pytest --cov=datalogger_app --cov-report=html`
  - Generates coverage report.

### Test Structure
- Tests in `tests/` directory.
- Use `pytest` fixtures for setup (e.g., mock config, HTML responses).
- Example: `def test_send_to_server(client, mocker):`
- Mock external calls: `mocker.patch('datalogger_app.requests.post')`.

### Adding Tests
- For functions: Unit tests with mock data.
- For web routes: Use Flask test client.
- Integration: Test full fetch-send cycle with mock server.

## Code Style Guidelines

### General Principles
- Follow PEP8 with Black formatting.
- Write readable, maintainable code.
- Use type hints for all functions and variables.
- Prefer functional programming where possible, avoid global state.
- Document complex logic with comments.

### Imports
- Standard library first: `import os, json`
- Third-party: `import requests, flask`
- Local: `from .utils import helper`
- Group with blank lines.
- Use absolute imports.

### Naming Conventions
- **Functions/Methods**: `snake_case` (e.g., `fetch_sensor_data`).
- **Variables**: `snake_case` (e.g., `config_data`).
- **Classes**: `PascalCase` (e.g., `SensorConfig`).
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `CONFIG_FILE = 'config.json'`).
- **Files**: `snake_case.py` (e.g., `datalogger_app.py`).

### Formatting
- Line length: 100 characters.
- Indentation: 4 spaces.
- Use Black for auto-formatting.
- Consistent quotes: Double for strings, single for chars.

### Types and Annotations
- Use `typing` module: `from typing import Dict, List`
- Annotate all functions: `def func(param: str) -> Dict[str, Any]:`
- For complex types: `Optional[List[Sensor]]`
- Enforce with mypy.

### Error Handling
- Use specific exceptions: `except requests.RequestException as e:`
- Avoid bare `except:`.
- Log errors: `print(f"Error: {e}")` or use logging module.
- Fail fast: Raise exceptions for critical errors.
- Handle config load failures gracefully.

### Functions and Classes
- Keep functions <50 lines, classes <200 lines.
- Use docstrings: `"""Brief description."""`
- Parameters: Limit to 5-7 per function.
- Return early: `if not data: return {}`

### Security
- No hardcoded secrets: Use config.json.
- Validate inputs: Check types, sanitize.
- HTTPS for external requests.
- Limit sensitive logging.

### Performance
- Avoid blocking operations in threads.
- Use efficient data structures (dicts over lists).
- Cache config loads if needed.

### Flask-Specific
- Routes: `@app.route('/path', methods=['GET'])`
- Templates: Use `render_template_string` for simple, or Jinja2 files.
- Threading: Use daemon threads, avoid shared state.
- Config: Reload from file, not global vars.

### Threading and Concurrency
- Use `threading` for background tasks.
- Protect shared resources with locks if needed.
- Daemon threads: `thread = threading.Thread(target=func, daemon=True)`

### Configuration
- Use JSON for config.
- Validate on load: Check required fields.
- Default values: `config.get('key', default)`

### Testing Best Practices
- Mock external deps.
- Test edge cases: Empty data, network failures.
- Fixtures for setup/teardown.
- Assert on return values, side effects.

### Git and Version Control
- Commit often with descriptive messages.
- Branches: `feature/`, `bugfix/`.
- PRs: Require reviews, CI checks.

### Deployment
- Environment variables for secrets.
- Logging: Use `logging` module, not print.
- Monitoring: Add health checks.

## Cursor Rules (if any)
None found in .cursor/rules/ or .cursorrules.

## Copilot Rules (if any)
None found in .github/copilot-instructions.md.

## Additional Notes
- Keep dependencies minimal.
- Document APIs in code.
- For new features, add tests first.
- Use virtualenv for isolation.
- Backup config.json before changes.

This guide ensures consistent contributions. Update as needed.