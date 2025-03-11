FROM python:3.12-slim-bullseye

WORKDIR /app
RUN pip install --no-cache-dir cryptography websockets

COPY server/ /app/server/
RUN mkdir -p /app/keys

WORKDIR /app/server
CMD ["python", "mainApp.py"]
