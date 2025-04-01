# BOM

BOM is a simple Django app to manage a bill of materials. It supports multiple part numbering schemes, tracking component sourcing information, estimates costs, and contains Google Drive for part file management. BOM is written in Python 3 and Django 5.

BOM can be added to an existing (or new) Django project, or stand alone on its own, which can be more convenient if you're interested in tweaking the tool. 

If you already have a django project, you can skip to [Add Django Bom To Your App](#add-django-bom-to-your-app), otherwise [Start From Scratch: Add to new Django project](#start-from-scratch-add-to-a-new-django-project) to add it to a new django project, or [Start From Scratch: Use as standalone Django project](#start-from-scratch-use-as-a-standalone-django-project).

## Table of contents
   * [Start From Scratch: Add to new Django project](#start-from-scratch-add-to-a-new-django-project)
   * [Add Django Bom To Your App](#add-django-bom-to-your-app)
   * [Start From Scratch: Use as standalone Django project](#start-from-scratch-use-as-a-standalone-django-project)
   * [Start from docker](#start-from-docker-recommended)
   * [Backup and restore database](#backup-and-restore-database-if-using-docker-compose-and-postgres)
   * [Customize Base Template](#customize-base-template)
   * [Integrations](#integrations)
   * [Contributing](#contributing)
   * [Installation pitfalls](#installation-pitfalls)
   
## Start From Scratch: Add to a new Django project
1. To start from scratch we recommend setting up a virtual environment using Python 3.8.13
```
virtualenv -p python3 mysite
cd mysite
source bin/activate
```

2. From here install django, and set up your project.
```
pip install django
django-admin startproject mysite
cd mysite
python manage.py migrate
python manage.py createsuperuser # make a user for your development environment
```

3. Continue on to [Add Django Bom To Your App](#add-django-bom-to-your-app).

## Add Django Bom To Your App
django-bom is a [reusable django application](https://docs.djangoproject.com/en/1.11/intro/reusable-apps/). If you don't already have a django project, you can follow some quick steps below to get up and running, or read about creating your first django app [here](https://docs.djangoproject.com/en/1.11/intro/tutorial01/).

```
pip install django-bom
```

1. Add "bom" to your INSTALLED_APPS setting like this::

```
INSTALLED_APPS = [
    ...
    'bom',
    'social_django', # to enable google drive sync in bom
    'djmoney', # for currency
    'djmoney.contrib.exchange', # for currency
    'materializecssform',
]
```

2. Update your URLconf in your project urls.py like this::

```
path('bom/', include('bom.urls')),
```

And don't forget to import include:

```
from django.conf.urls import include
```

3. Update your settings.py to add the bom context processor `'bom.context_processors.bom_config',` to your TEMPLATES variable, and create a new empty dictionary BOM_CONFIG.

```
TEMPLATES = [
    {
        ...
        'OPTIONS': {
            'context_processors': [
                ...
                'bom.context_processors.bom_config',
            ],
        },
    },
]
```

and

```
BOM_CONFIG = {}
```

4. Run `python manage.py migrate` to create the bom models.

5. Start the development server `python manage.py runserver` and visit http://127.0.0.1:8000/admin/
   to manage the bom (you'll need the Admin app enabled).

6. Visit http://127.0.0.1:8000/bom/ to begin.

   
## Start From Scratch: Use as a standalone Django project
1. To start from scratch we recommend setting up a virtual environment
```
virtualenv -p python3 .env
source .env/bin/activate
```

2. From here install django, and set up your project.
```
git clone https://github.com/mpkasp/django-bom.git
sudo apt-get install python3-dev (not always needed)
cp bom/local_settings.py.example bom/local_settings.py
pipenv install
pipenv shell
python manage.py migrate
python manage.py runserver
```
## Start from docker (Recommended)
1.1. create .env and .env.db files or use example files (just rename them).

1.2. If you have a problem accessing pypi (like I do) add a mirror link to Dockerfile before install pip requirements:
```
# Set the environment variable to use the mirror PyPI URL
ENV PIP_INDEX_URL=https://mirrors.sustech.edu.cn/pypi/web/simple
```
1.3. Go to project dir
```
cd project_dir
```
2. Build and run the containers
```
docker compose up --build
```
3. Compile the translations
```
python manage.py compilemessages -l fa_IR
```
4. Run entrypoint to check if database connection is OK
```
sh entrypoint.sh
```
5. Make the migrations
```
docker compose exec djangobom python manage.py makemigrations --noinput
```
6. Run the migrations
```
docker compose exec djangobom python manage.py migrate --noinput
```
7. Place static files in the docker volume
```
docker compose exec djangobom python manage.py collectstatic --noinput
```
8. Create a superuser (if it's first time)
```
docker compose exec -it python manage.py createsuperuser
```

## Backup and restore database (If using docker-compose and postgres)
Backup bom_db:
```
docker exec -t lithium_bom-db-1 pg_dump -c -U bom_user bom_db | gzip > ./dump_bom_db_$(date +"%Y-%m-%d_%H_%Ma_%S").sql.gz
```
Backup all:
```
docker exec -t lithium_bom-db-1 pg_dumpall -c -U bom_user | gzip > ./dump_all_bom_db_$(date +"%Y-%m-%d_%H_%Ma_%S").sql.gz
```
Restore bom_db:
```
gunzip < dump_file.sql.gz | docker exec -i lithium_bom-db-1 psql -U bom_user -d bom_db
```

## Customize Base Template
The base template can be customized to your pleasing. Just add the following configuration to your settings.py:

```
BOM_CONFIG = {
    'base_template': 'base.html',
}
```

where `base.html` is your base template.

## Integrations

### Google Drive Integration
Make sure to add the following to your settings.py:
```
AUTHENTICATION_BACKENDS = (
    'social_core.backends.google.GoogleOpenId',
    'social_core.backends.google.GoogleOAuth2',
    'social_core.backends.google.GoogleOAuth',
    'django.contrib.auth.backends.ModelBackend',
)

SOCIAL_AUTH_GOOGLE_OAUTH2_SCOPE = ['email', 'profile', 'https://www.googleapis.com/auth/drive', 'https://www.googleapis.com/auth/plus.login']
SOCIAL_AUTH_GOOGLE_OAUTH2_AUTH_EXTRA_ARGUMENTS = {
    'access_type': 'offline',
    'approval_prompt': 'auto'
}
``` 
And if you're using https on production add:
```
SOCIAL_AUTH_REDIRECT_IS_HTTPS = not DEBUG
```

### FIXER
Fixer.io is used to handle exchange rate calculations. This is helpful if you may be purchasing parts from another currency (especially via Mouser) and you still need to estimate your part costs.

To set this up you just need to add your API key to local_settings.py as shown in the example.

To update rates, migrate and run `python manage.py update_rates`. Some day we will need to add a (celerybeat?) task to update rates on a schedule. Explained more [here](https://github.com/django-money/django-money#working-with-exchange-rates).

## Contributing

Contributions welcome! Before contributing your work please read the [contributing readme](https://github.com/mpkasp/django-bom/blob/master/CONTRIBUTING.md).

Also reach out to mike@indabom.com to discuss features, and join our slack channel.

## Installation Pitfalls

### Windows
#### Sqlite
You may get an error during your `pip install -r requirements.txt` related to sqlite. This may be fixed by installing Visual C++ for python...

#### Cryptography
Sometimes you'll have issues installing cryptography, if this is the case you may just need to set up some environment variables. This [stackoverflow](https://stackoverflow.com/questions/46288737/error-while-installing-sqlite-using-pip-on-python-2-7-13) may help.
