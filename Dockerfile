FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 10000

CMD uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-10000}
