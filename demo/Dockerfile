FROM python:3.12-slim-bookworm as base
WORKDIR /usr/src/app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
RUN apt-get update && apt-get install -y git && apt-get clean

# Setup project
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-install-project --all-extras

COPY src ./src
RUN uv sync --locked --all-extras
RUN uv sync --group demo

COPY ./demo/demo.py ./src

ENTRYPOINT ["uv", "run", "python", "-m", "src/demo"]
