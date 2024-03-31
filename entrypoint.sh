#!/bin/sh

if [ "$DATABASE" = "postgres" ]
then
    echo "Waiting for postgres..."

    while ! nc -z $SQL_HOST $SQL_PORT; do
      sleep 0.1
    done

    echo "PostgreSQL started"
fi

# python manage.py compilemessages -l fa_IR
# python manage.py collectstatic --no-input --clear
# python manage.py flush --no-input
# python manage.py migrate
# python -m pip install -r requirements-dev.txt

exec "$@"