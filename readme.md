# Roma mobile

Welcome to the repository of [Roma mobile](https://romamobile.it).

Roma mobile is an open source web application providing realtime information and services about public and private transport.

In particular, the following services are available for Rome:

- Public transport network: route search, timetables, real-time bus waiting times, news
- Real-time journey planner
- Weather

The main input of Roma mobile consists of several GTFS feeds:

- a static GTFS feed with the description of routes, timetabling etc.
- a realtime GTFS feed of Vehicle Positions
- a realtime GTFS feed with Service Alerts (news)

Roma mobile has been forked from the open source project _Muoversi a Roma_ (formely _Atac mobile_), which used to be developed by [Roma servizi per la mobilità](https://romamobilita.it).

## Running a development server

__Requirements:__ Docker and Docker Compose V2.

__Warning:__ currently the dockerized environment for Roma mobile is only suitable for development purpose.

Start and init your database:

```bash
docker compose up -d postgis
docker compose run giano sh -c 'python manage.py wait_for_database && python manage.py syncdb'
```

You will be prompted to create a superuser account. Create one if you wish to access the Django admin interface. Then load the fixtures:

```bash
docker compose run giano python manage.py loaddata servizi mercury paline carteggi aree
```

Load public transport network; this command will take several minutes 

```bash
docker compose run giano python manage.py scarica_dati_tpl
```

All done! We are now ready to start the full application stack:

```bash
docker compose up -d
```

You can visit the home page at [http://localhost:8000](http://localhost:8000).  After a minute, you will be able to use services (bus waiting times, route planner).