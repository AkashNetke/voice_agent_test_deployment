# voice-agent

## Structure

Self explanatory, `src` contains source code, `test` contains tests. `pyproject.toml` is the build definition

## Project setup for development

Have latest Python installed in the machine

Use terminal to do the next steps in Mac, Linux or Windows

1. Create a virtual environment in the project folder

```sh
python -m venv venv
```

2. Always activate your virtual environment before doing anything

Mac / Linux
```sh
source venv/bin/activate
```

Windows
```sh
venv/Scripts/activate.bat
```

3. Install the dependencies via pip

```sh
pip install -e .[dev]
```

4. Run the service

```sh
uvicorn src.server:app --reload
```

5. Run tests

```sh
pytest
```

6. Format code:

```sh
black src tests
isort src tests
```

7. Lint code:

```sh
ruff src tests
mypy src
```

8. Secrets

We should NOT commit any API keys into github. This project uses a simple tool dotenv to make that possible:

- make a duplicate of `.env.example` and call that `.env`
- do not change anything in `.env.example` itself
- ask for API keys and URLs in the team or just look it up in azure
- `.env` is added into `.gitignore` so you never commit it

9. Sample Requests

Sample requests are in `sample-requests.http` this can be run from within vscode when running the local server. (Or by changing the base URL to run in the azure)
