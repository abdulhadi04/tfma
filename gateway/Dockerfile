FROM python:3.12-slim

WORKDIR /app

COPY gateway/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY gateway/main.py .

COPY frontend/ /app/frontend/

EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
