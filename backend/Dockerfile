# ── STAGE 1: crispembed native library builder ──────────────────────────────
FROM python:3.12-slim-bookworm AS crispembed-builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    ca-certificates \
    cmake \
    build-essential \
    ninja-build \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt
RUN git clone --recursive https://github.com/CrispStrobe/CrispEmbed.git

WORKDIR /opt/CrispEmbed
RUN cmake -S . -B build -G Ninja \
        -DCMAKE_BUILD_TYPE=Release \
        -DCRISPEMBED_BUILD_SHARED=ON \
    && cmake --build build -j"$(nproc)" \
    && find build -type f \( -name '*.o' -name '*.a' \) -delete \
    && find build -type d -name CMakeFiles -exec rm -rf {} + 2>/dev/null || true \
    && strip --strip-unneeded build/*.so* 2>/dev/null || true

# ── STAGE 2: Python dependency builder ─────────────────────────────────────
FROM python:3.12-slim-bookworm AS venv-builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
COPY pyproject.toml uv.lock .python-version ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv venv /app/.venv && \
    uv sync --frozen --no-dev --python /app/.venv/bin/python

# ── STAGE 3: runtime ────────────────────────────────────────────────────────
FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:${PATH}" \
    VIRTUAL_ENV=/app/.venv \
    HF_HOME=/app/cache/huggingface \
    OMP_NUM_THREADS="" \
    OPENBLAS_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    NUMEXPR_NUM_THREADS=1 \
    TOKENIZERS_PARALLELISM=false \
    PYTHONPATH="/opt/CrispEmbed/python:${PYTHONPATH}" \
    LD_LIBRARY_PATH="/opt/CrispEmbed/build:${LD_LIBRARY_PATH}"

# libgomp1 for OpenMP threading (used by crispembed / ggml)
# libpq-dev for asyncpg
# curl for crispembed's GGUF model auto-download
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy venv from stage 2
COPY --from=venv-builder /app/.venv /app/.venv

# Copy crispembed Python wrapper + built libraries from stage 1
COPY --from=crispembed-builder /opt/CrispEmbed/python /opt/CrispEmbed/python
COPY --from=crispembed-builder /opt/CrispEmbed/build /opt/CrispEmbed/build

WORKDIR /app

# Copy application code
COPY start.sh ./
COPY app/ app/

EXPOSE 8000

CMD ["sh", "start.sh"]
