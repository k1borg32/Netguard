# One Dockerfile for every Python service. Build context = repo root.
#   docker build -f services/python.Dockerfile --build-arg SERVICE=processor .
FROM python:3.12-slim

ARG SERVICE
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 SERVICE=${SERVICE}
WORKDIR /app

# Non-root user (security requirement)
RUN useradd --create-home --uid 10001 netguard

# Shared lib first (changes rarely -> cached layer)
COPY libs/common /tmp/common
RUN pip install --no-cache-dir "/tmp/common[kafka]" && rm -rf /tmp/common

COPY services/${SERVICE}/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY services/${SERVICE}/ /app/
COPY config/ /app/config/

USER netguard
# Each service's compose entry sets `command:`
