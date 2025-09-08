# voice-agent

## Structure

Self explanatory, `src` contains source code, `test` contains tests. `pyproject.toml` is the build definition managed by Poetry.

## Project setup for development

### Prerequisites
- Latest Python (3.9+) installed on your machine
- [Poetry](https://python-poetry.org/docs/#installation) installed globally

### Setup Steps

1. **Install Poetry** (if not already installed):
```sh
# Via pip (recommended)
pip install poetry

# Or via curl (Linux/macOS)
curl -sSL https://install.python-poetry.org | python3 -
```

2. **Install dependencies** (creates virtual environment automatically):
```sh
# Install only runtime dependencies
poetry install --no-root

# Or install with dev dependencies
poetry install --with dev --no-root
```

3. **Run the service**:
```sh
PYTHONPATH=src poetry run uvicorn src.voice_agent.server:app --reload
```

5. **Run tests**:
```sh
poetry run pytest
```

6. **Format code**:
```sh
poetry run black src tests
poetry run isort src tests
```

7. **Lint code**:
```sh
poetry run ruff src tests
poetry run mypy src
```

8. Secrets

We should NOT commit any API keys into github. This project uses a simple tool dotenv to make that possible:

- make a duplicate of `.env.example` and call that `.env`
- do not change anything in `.env.example` itself
- ask for API keys and URLs in the team or just look it up in azure
- `.env` is added into `.gitignore` so you never commit it

9. Sample Requests

Sample requests are in `sample-requests.http` this can be run from within vscode when running the local server. (Or by changing the base URL to run in the azure)
