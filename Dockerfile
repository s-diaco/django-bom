# TODO: Switch to a multi-stage Dockerfile
FROM python:3.12-slim

EXPOSE 8000

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE=1

# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED=1

# Required for "entrypoint.sh, makemessages"
RUN apt-get update && \
    apt-get install -y netcat-openbsd gettext \
    && rm -rf /var/lib/apt/lists/*

# Set the environment variable to use the mirror PyPI URL
# ENV PIP_INDEX_URL=https://mirrors.sustech.edu.cn/pypi/web/simple

# Install pip requirements
ARG REQUIREMENTS_FILE=requirements.lock
COPY ${REQUIREMENTS_FILE} ./
RUN --mount=type=cache,target=/root/.cache/pip pip install -r ${REQUIREMENTS_FILE}
# If caching pip packages is not needed, use this line instead:
# RUN pip install -r requirements.txt

# TODO: don't copy everything 
WORKDIR /app
COPY . /app

RUN mkdir /app/staticfiles
RUN mkdir /app/log

# Compile translation messages
RUN python manage.py compilemessages -l fa_IR

# Creates a non-root user with an explicit UID and adds permission to access the /app folder
# For more info, please refer to https://aka.ms/vscode-docker-python-configure-containers
RUN adduser -u 5678 --disabled-password --gecos "" appuser && chown -R appuser /app
USER appuser

