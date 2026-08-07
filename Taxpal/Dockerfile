FROM python:3.12-slim

WORKDIR /app

COPY src/requirements.txt .

RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ .

ENV PORT=3978

EXPOSE 3978

CMD ["python", "app.py"]