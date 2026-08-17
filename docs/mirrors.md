# Package mirrors (apt and PyPI)

If you cannot reach public package repositories while building Docker images, point the build at a local or regional mirror.

## PyPI

PyPI is not configured from an env file. If you have a problem accessing PyPI, add a mirror link to the Dockerfile before installing pip requirements:

```
# Set the environment variable to use the mirror PyPI URL
ENV PIP_INDEX_URL=https://mirrors.sustech.edu.cn/pypi/web/simple
```

## APT (Debian)

`docker-compose.yml` passes `APT_MIRROR` into the image build. You can set it in `.env.prod` (the file used with `docker compose --env-file .env.prod`) instead of exporting it in your shell:

```
APT_MIRROR=https://mirror.example.com/debian
```

Then build as usual:

```
docker compose --env-file .env.prod up --build -d
```

A project-root `.env` file also works for Compose interpolation if you are not passing `--env-file`.

You can still export the variable in the shell if you prefer not to store it in a file:

```
export APT_MIRROR=https://mirror.example.com/debian
docker compose --env-file .env.prod up --build -d
```

A value in the shell overrides the same key in the env file.

Note: SSL certificate verification is automatically disabled for the mirror to support self-signed certificates.
