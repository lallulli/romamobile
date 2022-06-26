# coding: utf-8

#
#    Copyright 2013-2016 Roma servizi per la mobilità srl
#    Developed by Luca Allulli and Damiano Morosi
#
#    This file is part of Roma mobile.
#
#    Roma mobile is free software: you can redistribute it
#    and/or modify it under the terms of the GNU General Public License as
#    published by the Free Software Foundation, version 2.
#
#    Roma mobile is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
#    or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License
#    for more details.
#
#    You should have received a copy of the GNU General Public License along with
#    Roma mobile. If not, see http://www.gnu.org/licenses/.
#

from django.core.management.base import BaseCommand, CommandError
from optparse import make_option
import settings
import os, subprocess, signal
from datetime import date, time, datetime, timedelta
from servizi.utils import datetime2time, transaction
from django.db.models import Q
from mercury.models import *
import csv
from servizi import infopoint
from parcheggi import models as parcheggi
from risorse import models as risorse
from django.contrib.gis.geos import Point, GEOSGeometry, LineString
from pprint import pprint
from paline import geomath
from servizi.unicode_csv import UnicodeLazyDictWriter, UnicodeDictReader
import traceback

config = {
	'allow_public_attrs': True,
}

def esercizio_commerciale(row, geom):
	t = row['Specializzazione'].capitalize()
	if t != 'Altro':
		risorse.risorsa(t)
		risorse.EsercizioCommerciale(
			nome_luogo=t,
			tipo=risorse.TipoRisorsa.objects.get_or_create(nome=t),
			indirizzo="%s, %s" % (row['Via'], row['Civico']),
			geom=geom,
		).save()

def farmacia_comunale(row, geom):
	risorse.Farmacia(
		nome_luogo=row['FARMACIE '],
		indirizzo=row['INDIRIZZO'],
		telefono=row['TELEFONO'],
		geom=geom,
	).save()

def farmacia_non_comunale(row, geom):
	tel = row['TELEFONO/FAX'].strip()
	if tel[0] == '6':
		tel = '0' + tel
	risorse.Farmacia(
		nome_luogo=row['FARMACIA'],
		indirizzo=row['INDIRIZZO'],
		telefono=tel,
		geom=geom,
	).save()
	
def carsharing(row, geom):
	risorse.CarSharing(
		nome_luogo=row['nome'],
		geom=geom,
	).save()

	
def autorimessa(row, geom):
	print row['nome']
	telefono = row['telefono'].strip()
	indirizzo = "%s %s, %s" % (row['via'], row['civico'], row['comune'])
	if len(telefono) > 0 and telefono[0] == '6':
		telefono = '0' + telefono
	parcheggi.Autorimessa(
		nome_luogo=row['nome'],
		telefono=telefono,
		indirizzo=indirizzo,
		geom=geom,
	).save()
	
def parcheggio_scambio(row, geom):
	posti = row['POSTI_AUTO']
	indirizzo = row['LOCALIZZAZ']
	parcheggi.ParcheggioScambio(
		nome_luogo=row['nome'],
		posti=posti,
		indirizzo=indirizzo,
		geom=geom,
	).save()

def biblioteca(row, geom):
	risorse.Biblioteca(
		nome_luogo=row['nome'],
		municipio=row['municipio'],
		indirizzo=row['indirizzo'],
		cap=row['cap'],
		zona=row['zona'],
		url_scheda=row['url_scheda'],
		url_cerca=row['url_cerca'],
		accessibilita=row['accessibilita'],
		email=row['email'],
		tel=row['tel'],
		tipo_biblio=row['tipo'],
		geom=geom,
	).save()

class Command(BaseCommand):
	args = "modello csv"
	help = """
		Carica i dati del csv in un modello
	"""
	option_list = BaseCommand.option_list + (
		make_option(
			'-d',
			'--delete',
	    action='store_true',
	    dest='delete',
	    default=False,
	    help='Cancella tutte le istanze del modello prima di caricare i dati',
	   ),
		make_option(
			'-g',
			'--geocode',
	    action='store_true',
	    dest='geocode',
	    default=False,
	    help='Si limita a geocodificare gli indirizzi, fornendo un csv con le coordinate',
	   ),
		make_option(
			'-w',
			'--wgs84',
	    action='store_true',
	    dest='wgs84',
	    default=False,
	    help='Interpreta le coordinate come wgs84 invece che gbfe (x per longitudine, y per latitudine)',
	   ),	
	)
	
	def handle(self, *args, **options):
		encoding = 'iso-8859-1'
		cb_modello = args[0]
		csvfile = args[1]
		name, ext = os.path.splitext(csvfile)
		csverrfile = name + "-err" + ext
		csvgeofile = name + "-geo" + ext
		# Ogni elemento è una terna (funzione, campo_geocoding, modello_da_svuotare); questi ultimi possono valere None
		modelli = {
			'autorimessa': [autorimessa, 'indirizzo', parcheggi.Autorimessa],
			'biblioteca': [biblioteca, None, risorse.Biblioteca],
			'parcheggio_scambio': [parcheggio_scambio, None, parcheggi.ParcheggioScambio],
			'esercizio_commerciale': [esercizio_commerciale, ['Via', 'Civico'], risorse.EsercizioCommerciale],
			'farmacia_comunale': [farmacia_comunale, 'INDIRIZZO', risorse.Farmacia],
			'farmacia_non_comunale': [farmacia_non_comunale, 'INDIRIZZO', risorse.Farmacia],
			'carsharing': [carsharing, None, risorse.CarSharing],
		}
		funz, geo, modello = modelli[cb_modello]
		if geo is not None and type(geo) != list:
			geo = [geo]
		i = 0
		with transaction(debug=True):
			if modello is not None and options['delete']:
				print "Elimino vecchie istanze"
				for o in modello.objects.all():
					o.delete()
			print "Importo nuove istanze"
			headers = None
			if options['geocode']:
				with open(csvfile, 'r') as f:
					with open(csvgeofile, 'a') as fg:
						with open(csverrfile, 'w') as fw:
							reader = UnicodeDictReader(f, delimiter=';', encoding=encoding)
							geo_writer = UnicodeLazyDictWriter(fg, delimiter=';', encoding=encoding)
							err_writer = UnicodeLazyDictWriter(fw, delimiter=';', encoding=encoding)
							for row in reader:
								row = {k: row[k].strip() for k in row}
								i += 1
								print "Riga #%d" % i
								error = False
								try:
									if geo is not None:
										indirizzo = " ".join([row[g] for g in geo])
									else:
										indirizzo = row['indirizzo']
									res = infopoint.geocode_place(None, indirizzo)
									if res['stato'] != 'OK':
										pprint(res)
										print "Errore di geocoding"
										error = True
									else:
										row.update({'x': str(res['x']), 'y': str(res['y'])})
										geo_writer.writerow(row)
								except Exception, e:
									print "Eccezione"
									traceback.print_exc()
									error = True
								if error:
									err_writer.writerow(row)
									pprint(row)
			else:
				with open(csvfile, 'r') as f:
					with open(csverrfile, 'w') as fw:
						reader = UnicodeDictReader(f, delimiter=';', encoding=encoding)
						err_writer = UnicodeLazyDictWriter(fw, delimiter=';', encoding=encoding)
						writer = None
						for row in reader:
							row = {k: row[k].strip() for k in row}
							i += 1
							print "Riga #%d" % i
							error = False
							try:
								if options['wgs84']:
									lng, lat = float(row['lng']), float(row['lat'])
									x, y = geomath.wgs84_to_gbfe(lng, lat)
								else:
									x, y = float(row['x']), float(row['y'])
								geom = Point(x, y, srid=3004)
								funz(row, geom)									
							except Exception, e:
								traceback.print_exc()
								error = True
							if error:
								if writer is None:
									err_writer.writerow(row)
									pprint(row)	

