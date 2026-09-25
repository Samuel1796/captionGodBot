FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Render injects its own $PORT; this is only the local default.
ENV PORT=10000
EXPOSE 10000

RUN useradd --create-home --uid 10001 botuser && chown -R botuser /app
USER botuser

CMD ["python", "main.py"]
