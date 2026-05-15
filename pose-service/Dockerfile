# ── Stage 1: builder ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build
COPY requirements.txt .

RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc libglib2.0-0 libgl1 \
    && pip install --no-cache-dir --prefix=/install -r requirements.txt \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# ── Stage 2: runtime ──────────────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        libglib2.0-0 libgl1 wget \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Copia dependências do builder
COPY --from=builder /install /usr/local

# Copia código da aplicação
COPY . .

# Usuário não-root
RUN addgroup --system gymvision && adduser --system --ingroup gymvision gymvision
USER gymvision

EXPOSE 8083

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD wget -q --spider http://localhost:8083/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8083", "--workers", "2"]
