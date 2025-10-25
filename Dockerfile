FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

# OS deps (bcrypt/cffi etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libffi-dev curl ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Install deps first (cache-friendly)
COPY requirements*.txt* pyproject.toml* ./
RUN python -m pip install --upgrade pip && \
    if [ -f requirements.txt ]; then pip install -r requirements.txt; fi

# Copy app
COPY src ./src
COPY frontend ./frontend

ENV PORT=3000
EXPOSE 3000

# FastAPI app is src/index.py with "app"
CMD ["python", "-m", "uvicorn", "src.index:app", "--host", "0.0.0.0", "--port", "3000"]