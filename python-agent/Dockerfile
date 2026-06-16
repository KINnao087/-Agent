FROM python:3.11-slim

WORKDIR /app

# 系统依赖（PaddleOCR 需要）
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx libglib2.0-0 libsm6 libxext6 libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

# Python 依赖
COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[dev]" \
    && pip install paddlepaddle  # CPU 版

# 源码
COPY . .

EXPOSE 8000
CMD ["python", "-m", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
