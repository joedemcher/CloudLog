FROM --platform=linux/amd64 python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY metrics.py .
COPY models.py .
COPY parser.py .

CMD ["python", "app.py"]
