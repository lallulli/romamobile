FROM python:2.7.18-buster

WORKDIR /app

# Install required packages
RUN apt-get update
RUN apt-get -y install build-essential mercurial postgis python-dev python-psycopg2 p7zip-full libffi-dev git binutils libproj-dev gdal-bin vim

COPY ./src .
COPY ./requirements.txt .

# Install required Python libraries
RUN pip install --no-cache-dir -r requirements.txt

# Workaround for GeoDjango-GEOS bug
# https://stackoverflow.com/a/18721622
RUN sed -i "s/ver = geos_version().decode()/ver = geos_version().decode().split(' ')[0]/g" /usr/local/lib/python2.7/site-packages/django/contrib/gis/geos/libgeos.py


# Extra temporary dependencies, to be moved to pyproject.toml
# RUN pip install django-rest-framework

# Copy Django app

EXPOSE 8000
WORKDIR /app
CMD [ "python", "manage.py", "runserver", "0.0.0.0:8000" ]