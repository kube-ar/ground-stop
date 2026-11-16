# Todos en tierra: everything runs in Python, so the image only needs Python and uv.
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.9.9 /uv /uvx /bin/
ENV UV_PROJECT_ENVIRONMENT=/opt/venv UV_LINK_MODE=copy GROUND_STOP_LANG=es
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen
COPY . .
ENV UV_NO_SYNC=1
ENTRYPOINT ["uv", "run", "--frozen", "ground-stop"]
CMD ["replay"]
