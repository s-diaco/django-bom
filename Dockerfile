# For more information, please refer to https://aka.ms/vscode-docker-python
FROM python:3.12-slim

EXPOSE 8000

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE=1

# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED=1

# install system dependencies. required for "entrypoint.sh"
RUN apt-get update && apt-get install -y netcat-openbsd gettext

# Set the environment variable to use the mirror PyPI URL
# ENV PIP_INDEX_URL=https://mirrors.sustech.edu.cn/pypi/web/simple

# Install pip requirements
COPY requirements.lock .
RUN sed '/-e/d' requirements.lock > requirements.txt
RUN pip install -r requirements.txt

# TODO: don't copy everything 
WORKDIR /app
COPY . /app

# create the appropriate directories
RUN mkdir /app/staticfiles
RUN mkdir /app/log

# Creates a non-root user with an explicit UID and adds permission to access the /app folder
# For more info, please refer to https://aka.ms/vscode-docker-python-configure-containers
RUN adduser -u 5678 --disabled-password --gecos "" appuser && chown -R appuser /app
USER appuser

# During debugging, this entry point will be overridden. For more information, please refer to https://aka.ms/vscode-docker-python-debug
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "bom.wsgi"]
