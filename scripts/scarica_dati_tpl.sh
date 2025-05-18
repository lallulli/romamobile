#!/bin/sh

docker compose run giano python manage.py scarica_dati_tpl
docker compose restart giano web
