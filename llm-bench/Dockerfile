FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# System deps for lm-evaluation-harness (some tasks compile native deps)
RUN apt-get update && apt-get install -y --no-install-recommends \
      git build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY src/ ./src/

# Install bench + lm-eval together (heavyweight; ~600MB image)
RUN pip install -e ".[lm-eval]"

# Default: serve the dashboard. Orchestration via `docker exec llm-bench bench run …`.
EXPOSE 15600
CMD ["streamlit", "run", "src/bench/dashboard/app.py", \
     "--server.port", "15600", "--server.address", "0.0.0.0", \
     "--server.headless", "true"]
