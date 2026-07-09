FROM python:3.12-slim

WORKDIR /app
COPY . /app
ENV MEMORY_HOME=/memory

ENTRYPOINT ["python", "-m", "memoryos.cli"]
