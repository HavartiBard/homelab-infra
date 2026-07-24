FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY hister_client.py server.py ./

EXPOSE 3000
CMD ["python", "server.py"]
