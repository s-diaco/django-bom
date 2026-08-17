# Package mirrors (apt and PyPI)

If you cannot reach public package repositories while building Docker images, point the build at a local or regional mirror.

## PyPI

If you have a problem accessing PyPI, add a mirror link to the Dockerfile before installing pip requirements:

```
# Set the environment variable to use the mirror PyPI URL
ENV PIP_INDEX_URL=https://mirrors.sustech.edu.cn/pypi/web/simple
```

## APT (Debian)

If you have a problem accessing Debian package repositories during image build, export `APT_MIRROR` before running Compose:

```
export APT_MIRROR=https://mirror.example.com/debian
docker compose --env-file .env.prod up --build -d
```

Note: SSL certificate verification is automatically disabled for the mirror to support self-signed certificates.
