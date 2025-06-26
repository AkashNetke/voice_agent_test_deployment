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
uvicorn src.main:app --reload
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
