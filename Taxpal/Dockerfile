# syntax=docker/dockerfile:1
FROM python:3.12-slim

WORKDIR /app

COPY src/requirements.bot.txt .

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip && \
    pip install -r requirements.bot.txt

COPY src/ .

ENV PORT=3978

EXPOSE 3978

CMD ["python", "app.py"]
