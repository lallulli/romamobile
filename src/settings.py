# coding: utf-8

#
#    Copyright 2013-2016 Roma servizi per la mobilità srl
#    Developed by Luca Allulli and Damiano Morosi
#
#    This file is part of Muoversi a Roma for Developers.
#
#    Muoversi a Roma for Developers is free software: you can redistribute it
#    and/or modify it under the terms of the GNU General Public License as
#    published by the Free Software Foundation, version 2.
#
#    Muoversi a Roma for Developers is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
#    or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License
#    for more details.
#
#    You should have received a copy of the GNU General Public License along with
#    Muoversi a Roma for Developers. If not, see http://www.gnu.org/licenses/.
#

import os, os.path
from pickle import INST
from django.conf.global_settings import SESSION_COOKIE_NAME
from datetime import date, time, datetime, timedelta
import json

# 0: pro, 1: pre (beta), 2: test, 3: localhost
TEST_LEVEL = 3

ID_SITO = [1, 7, 1, 1][TEST_LEVEL]
DEBUG = [False, False, True, True][TEST_LEVEL]
TEMPLATE_DEBUG = DEBUG

MONGO_ENABLED = False

INFOTP_TIMEOUT = 3 #seconds
INFOPOINT_TIMEOUT = 8 # seconds

ADMINS = (
	('Your Name', 'your.name@your.domain.com'),
)

with open('secrets/settings.json') as r:
	secrets = json.load(r)

MANAGERS = ADMINS

MERCURY_WEB = 'web'
MERCURY_WEB_CL = 'web' #'web-cl'
MERCURY_GIANO = 'giano'
MERCURY_GIANO_PERCORSI = 'giano_percorsi'
MERCURY_CL = 'cl'
MERCURY_CPD = 'cpd'
MERCURY_CARICA_RETE = 'carica_rete'
LOCAL_IP = secrets['giano']['local_ip']
MERCURY_FILE_STORE_PATH = '/data/rete/store'

WS_BASE_URL = 'http://muovi.roma.it'
# DEVELOPER_KEY = Not used anymore
GTFS_ST_URL = 'https://romamobilita.it/sites/default/files/rome_static_gtfs.zip'
GTFS_RT_URL = 'https://romamobilita.it/sites/default/files/rome_rtgtfs_vehicle_positions_feed.pb'
GTFS_SA_URL = 'https://romamobilita.it/sites/default/files/rome_rtgtfs_service_alerts_feed.pb'
GTFS_ST_CHECK_FOR_UPDATES = False

TROVALINEA_PATH_RETE = 'paline/rete'
TROVALINEA_RETE_SPECIALE = os.path.join(TROVALINEA_PATH_RETE, 'special')

dbsecrets = secrets['database']

DATABASES = {
	'default': {
		'ENGINE': 'django.contrib.gis.db.backends.postgis',
		'HOST': dbsecrets['host'],
		'NAME': dbsecrets['name'],
		'USER': dbsecrets['user'],
		'PASSWORD': dbsecrets['password'],
		'OPTIONS': {'autocommit': True,}
	},
}


DATABASE_APPS_MAPPING = {
	'admin': 'default',
	'auth': 'default',
	'carpooling': 'default',
	'constance': 'default',
	'contenttypes': 'default',
	'database': 'default', #constance
	'sessions': 'default',
	'sites': 'default',
	'messages': 'default',
	'staticfiles': 'default',
	'autenticazione': 'default',
	'gis': 'gis',
	'lingua': 'servizi',
	'log_servizi': 'default',
	'mercury': 'default',
	'meteo': 'default',
	'metro': 'default',
	'news': 'default',
	'paline': 'default',
	'parcheggi': 'default',
	'percorso': 'default',
	'redirect': 'default',
	'risorse': 'default',
	'servizi': 'default',
	'telegram_channel': 'default',
	'xhtml': 'default',
	'ztl': 'default',
}

DATABASE_ROUTERS = ['dbrouters.DatabaseAppsRouter']

CACHES = {
	'default': {
		'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
		'LOCATION': 'atacmobile'
	}
}

SESSION_ENGINE = 'django.contrib.sessions.backends.db'

CONSTANCE_BACKEND = 'constance.backends.database.DatabaseBackend'

TEMPLATE_CONTEXT_PROCESSORS = (
	'django.core.context_processors.request',
	'django.contrib.auth.context_processors.auth',
)

AUTHENTICATION_BACKENDS = (
	'django.contrib.auth.backends.ModelBackend',
	'autenticazione.backends.MuoversiaromaBackend',
	'autenticazione.backends.LocalizzazioneBackend',
	'autenticazione.backends.ServiziBackend',
)

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# On Unix systems, a value of None will cause Django to use the same
# timezone as the operating system.
# If running in a Windows environment this must be set to the same as your
# system time zone.
TIME_ZONE = 'Europe/Rome'

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'it'

LANGUAGES = (
  ('it', 'Italiano'),
  ('en', 'English'),
)

SITE_ID = 1

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# If you set this to False, Django will not format dates, numbers and
# calendars according to the current locale
USE_L10N = True

ROOT = os.path.dirname(__file__)

# Absolute filesystem path to the directory that will hold user-uploaded files.
# Example: "/home/media/media.lawrence.com/media/"
MEDIA_ROOT = os.path.join(os.path.dirname(__file__), 'xhtml', 'static')

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash.
# Examples: "http://media.lawrence.com/media/", "http://example.com/media/"
MEDIA_URL = '/media/'

# Absolute path to the directory static files should be collected to.
# Don't put anything in this directory yourself; store your static files
# in apps' "static/" subdirectories and in STATICFILES_DIRS.
# Example: "/home/media/media.lawrence.com/static/"
STATIC_ROOT = ''

# URL prefix for static files.
# Example: "http://media.lawrence.com/static/"
STATIC_URL = '/static/'

# URL prefix for admin static files -- CSS, JavaScript and images.
# Make sure to use a trailing slash.
# Examples: "http://foo.com/static/admin/", "/static/admin/".
ADMIN_MEDIA_PREFIX = '/static/admin/'

# Additional locations of static files
STATICFILES_DIRS = (
	# Put strings here, like "/home/html/static" or "C:/www/django/static".
	# Always use forward slashes, even on Windows.
	# Don't forget to use absolute paths, not relative paths.
)

# List of finder classes that know how to find static files in
# various locations.
STATICFILES_FINDERS = (
	'django.contrib.staticfiles.finders.FileSystemFinder',
	'django.contrib.staticfiles.finders.AppDirectoriesFinder',
#	'django.contrib.staticfiles.finders.DefaultStorageFinder',
)

# Make this unique, and don't share it with anybody.
SECRET_KEY = secrets['secret_key']

# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
	'django.template.loaders.filesystem.Loader',
	'django.template.loaders.app_directories.Loader',
#	 'django.template.loaders.eggs.Loader',
)


SESSION_COOKIE_NAME = 'sessionid'


MIDDLEWARE_CLASSES = (
	# 'django.middleware.gzip.GZipMiddleware',
	'xhtml.middleware.SessionCookieMiddleware',
	'django.contrib.sessions.middleware.SessionMiddleware',
	'django.middleware.locale.LocaleMiddleware',
	'django.middleware.common.CommonMiddleware',
	'django.middleware.csrf.CsrfViewMiddleware',
	'django.contrib.auth.middleware.AuthenticationMiddleware',
	'django.contrib.messages.middleware.MessageMiddleware',
	'xhtml.middleware.Middleware',
)

ROOT_URLCONF = 'urls'
HOST_MIDDLEWARE_URLCONF_MAP = {
}


# Applicazioni che erogano servizi web
WS_APPS = [
	'autenticazione',
	'lingua',
	'news',
	'paline',
	'parcheggi',
	'percorso',
	'risorse',
	'servizi',
	'ztl',
]


# Applicazioni che erogano servizi di front-end (xhtml)
XHTML_APPS = [
	'carpooling',
	'lingua',
	'meteo',
	'metro',
	'news',
	'pages',
	'paline',
	'parcheggi',
	'percorso',
	'redirect',
	'risorse',
	'servizi',
	'xhtml',
	'ztl',
]

# Applicazioni ausiliarie
AUX_APPS = [
	'log_servizi',
	'gis',
	'mercury',
	'servizi',
	'telegram_channel',
]

LOCAL_APPS = list(set(AUX_APPS + WS_APPS + XHTML_APPS))

INSTALLED_APPS = [
	#'django_cpserver',
	'constance.backends.database',
	'constance',
	'django.contrib.auth',
	'django.contrib.contenttypes',
	'django.contrib.sessions',
	'django.contrib.sites',
	'django.contrib.messages',
	'django.contrib.staticfiles',
	# Uncomment the next line to enable the admin:
	'django.contrib.admin',
	'django.contrib.gis',
	'jsonrpc',

	# Uncomment the next line to enable admin documentation:
	# 'django.contrib.admindocs',
] + LOCAL_APPS



TEMPLATE_DIRS = [
	# Put strings here, like "/home/html/django_templates" or "C:/www/django/templates".
	# Always use forward slashes, even on Windows.
	# Don't forget to use absolute paths, not relative paths.
] + [os.path.join(os.path.dirname(__file__), x, 'templates') for x in XHTML_APPS]


# A sample logging configuration. The only tangible logging
# performed by this configuration is to send an email to
# the site admins on every HTTP 500 error.
# See http://docs.djangoproject.com/en/dev/topics/logging for
# more details on how to customize your logging configuration.
LOGGING = {
	'version': 1,
	'disable_existing_loggers': False,
	'formatters': {
			'verbose': {
					'format': '%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(message)s'
			},
			'simple': {
					'format': '%(levelname)s %(message)s'
			},
	},
	# Da aggiungere in Django 1.5:
	'filters': {
		'require_debug_false': {
			'()': 'django.utils.log.RequireDebugFalse'
		}
	},	
	'handlers': {
		'mail_admins': {
			'level': 'ERROR',
			'class': 'django.utils.log.AdminEmailHandler',
			# Da aggiungere in Django 1.5:
			'filters': ['require_debug_false'],
		},
		'log-file': {
			'level': 'DEBUG',
			'class': 'logging.FileHandler',
			'formatter': 'verbose',
			#consider: 'filename': '/var/log/<myapp>/app.log',
			#will need perms at location below:
			'filename': 'atacmobile.log',
			'mode': 'a', #append+create
			#'maxBytes': 100*1024,
			#'backupCount': 5,
		},		
	},
	'loggers': {
		'django.request': {
			'handlers': [], #'mail_admins'],
			'level': 'ERROR',
			'propagate': True,
		},
		'standard': {
			'handlers': ['log-file'],
			'level': 'ERROR',
			'propagate': True,
		},
		'': {
			'handlers': ['log-file'],
			'level': 'ERROR',
			'propagate': True,
		},					
	}
}

# Indirizzi email ecc.
DESTINATARI_MAIL_CARICA_RETE = []

# Calcola percorso dinamico

CPD_LOG_PER_STATISTICHE = False

CONSTANCE_CONFIG = {
	'CPD_PIEDI_0': (2.8, u'Velocità camminatore lento'),
	'CPD_PIEDI_1': (4.4, u'Velocità camminatore medio'),
	'CPD_PIEDI_2': (5.3, u'Velocità camminatore veloce'),
	'CPD_BICI_0': (8.0, u'Velocità ciclista lento'),
	'CPD_BICI_1': (13.0, u'Velocità ciclista medio'),
	'CPD_BICI_2': (16.5, u'Velocità ciclista veloce'),
	'CPD_T_SAL_BUS': (30, u'Tempo di salita bus'),
	'CPD_T_DISC_BUS': (20, u'Tempo di discesa bus'),
	'CPD_T_SAL_METRO': (30, u'Tempo di salita metro'),
	'CPD_T_DISC_METRO': (20, u'Tempo di discesa metro'),
	'CPD_T_SAL_TRENO': (240, u'Buffer di sicurezza per non perdere il treno'),
	'CPD_T_DISC_TRENO': (20, u'Tempo di discesa treno'),
	'CPD_T_SAL_FC': (30, u'Tempo di salita fc'),
	'CPD_T_DISC_FC': (20, u'Tempo di discesa fc'),
	'CPD_T_DISC_BICI': (20, u'Tempo necessario per lasciare la bici'),
	'CPD_T_INTERSCAMBIO': (240, u'Tempo di interscambio dei nodi di scambio'),
	'CPD_PENALIZZAZIONE_AUTO': (0.25, u'Coeff. di penalilzzaz. automobile'),
	'CPD_PENALIZZAZIONE_CAR_SHARING': (2.0, u'Coeff. di penalilzzaz. car sharing'),
	'CPD_PENALIZZAZIONE_BUS': (300, u'Tempo di penalizzazione per l\'uso di un bus'),
	'CPD_PENALIZZAZIONE_METRO': (250, u'Tempo di penalizzazione per l\'uso di una metro'),
	'CPD_PENALIZZAZIONE_FC': (270, u'Tempo di penalizzazione per l\'uso di una ferrovia concessa'),
	'CPD_PENALIZZAZIONE_TRENO': (270, u'Tempo di penalizzazione per l\'uso di un treno'),
	'CPD_INCENTIVO_CAPOLINEA': (240, u'Tempo di incentivo massimo prendere un mezzo al capolinea'),
	'CPD_PENAL_PEDONALE_0_0': (1.8, u'Coeff. di penalilzzaz. iniz. camminatore lento'),
	'CPD_PENAL_PEDONALE_1_0': (2.9, u'Coeff. di penalilzzaz. camminatore lento dopo 1 km'),
	'CPD_PENAL_PEDONALE_EXP_0': (1.0, u'Exp. di penalilzzaz. camminatore lento'),
	'CPD_PENAL_PEDONALE_0_1': (1.6, u'Coeff. di penalilzzaz. iniz. camminatore medio'),
	'CPD_PENAL_PEDONALE_1_1': (2.5, u'Coeff. di penalilzzaz. camminatore medio dopo 1 km'),
	'CPD_PENAL_PEDONALE_EXP_1': (0.85, u'Exp. di penalilzzaz. camminatore medio'),
	'CPD_PENAL_PEDONALE_0_2': (1.4, u'Coeff. di penalilzzaz. iniz. camminatore veloce'),
	'CPD_PENAL_PEDONALE_1_2': (1.7, u'Coeff. di penalilzzaz. camminatore veloce dopo 1 km'),
	'CPD_PENAL_PEDONALE_EXP_2': (0.5, u'Exp. di penalilzzaz. camminatore veloce'),
	'CPD_BICI_CAMBIO_STRADA': (25, u'Tempo di svolta in bicicletta'),
	'CL_SNAP_DIST_CAPOLINEA': (300, u'Distanza di snapping dal capolinea: se minore, veicolo posizionato a capolinea'),
	'CL_INTERPOL_COEFF_VELOCITA': (0.95, u"Coefficiente velocita' tratti per interpolaz. posizione veicoli"),
	'CARPOOLING_COSTO_CHILOMETRICO': (0.166, u"Costo medio per percorrere 1km in automobile"),
	'GIANO_DATA_MAPPING_RETE': (datetime(2020, 1, 1), u"Orario di mapping della rete"),
}

ALLOWED_HOSTS = [
	'*',
]

GRAPH = 'osm'
CPD_GIORNI_LOOKAHEAD = 7
