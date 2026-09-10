FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=7860

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# 构建时在线拉取题库（失败则回退到内置 7 道，不影响启动）
RUN python import_bank.py || true

EXPOSE 7860

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-7860}"]
