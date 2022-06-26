# coding: utf-8

#
#    Copyright 2015-2016 Roma servizi per la mobilità srl
#    Developed by Luca Allulli
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

from servizi.unicode_csv import UnicodeDictWriter, UnicodeDictReader
import os, os.path
from paline import tpl
from paline.geomath import gbfe_to_wgs84, distance
from paline.models import *
from datetime import date, time, datetime, timedelta
import csv
import traceback
import os, os.path, zipfile, shutil, tempfile

AGENCY_ID = 'MOBILITA'
STATION_FIRST_ID = 50000


def agency(path):
	fn = os.path.join(path, 'agency.txt')
	with open(fn, 'w') as f:
		fieldnames = ['agency_id', 'agency_name', 'agency_url' ,'agency_timezone', 'agency_lang', 'agency_phone', 'agency_fare_url']
		writer = UnicodeDictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_MINIMAL, lineterminator='\n')
		writer.writeheader()
		writer.writerow({
			'agency_id': AGENCY_ID,
			'agency_name': u'Roma Servizi per la Mobilità',
			'agency_url': "http://www.agenziamobilita.roma.it",
			'agency_timezone': "Europe/Rome",
			'agency_lang': 'it',
			'agency_phone': '06 57003',
		})


def stops(path, rete):
	fn = os.path.join(path, 'stops.txt')
	with open(fn, 'w') as f:
		fieldnames = ['stop_id', 'stop_code', 'stop_name', 'stop_desc', 'stop_lat', 'stop_lon', 'zone_id', 'location_type', 'parent_station', 'stop_timezone', 'stop_url', 'wheelchair_boarding']
		writer = UnicodeDictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_MINIMAL, lineterminator='\n')
		writer.writeheader()

		stations = {}
		i = STATION_FIRST_ID

		for id_palina in rete.paline:
			p = rete.paline[id_palina]
			palina = Palina.objects.by_date().get(id_palina=id_palina)
			lon, lat = gbfe_to_wgs84(p.x, p.y)
			parent = ''
			if p.ferroviaria:
				if p.nome not in stations:
					stations[p.nome] = {
						'stop_id': str(i),
						'stop_lat': str(lat),
						'stop_lon': str(lon),
						'nome_ricapitalizzato': palina.nome_ricapitalizzato(),
					}
					i += 1
				parent = stations[p.nome]['stop_id']
			writer.writerow({
				'stop_id': id_palina,
				'stop_code': id_palina,
				'stop_name': palina.nome_ricapitalizzato(),
				'stop_desc': palina.descrizione,
				'stop_lat': str(lat),
				'stop_lon': str(lon),
				'location_type': '0',
				'parent_station': parent,
				'stop_url': 'http://muovi.roma.it/percorso/js?query=%s&cl=1' % id_palina,
			})

		for nome in stations:
			s = stations[nome]
			id_palina = s['stop_id']
			writer.writerow({
				'stop_id': id_palina,
				'stop_name': s['nome_ricapitalizzato'],
				'stop_lat': s['stop_lat'],
				'stop_lon': s['stop_lon'],
				'location_type': '1',
				'parent_station': '',
				'stop_url': '',
			})



def routes(path, rete):
	fn = os.path.join(path, 'routes.txt')
	with open(fn, 'w') as f:
		fieldnames = ['route_id', 'agency_id', 'route_short_name', 'route_long_name', 'route_desc', 'route_type', 'route_url', 'route_color', 'route_text_color', 'route_text_color']
		writer = UnicodeDictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_MINIMAL, lineterminator='\n')
		writer.writeheader()

		linee = set()

		for id_percorso in rete.percorsi:
			p = rete.percorsi[id_percorso]
			id_linea = p.id_linea
			if id_linea not in linee and not p.soppresso:
				linee.add(id_linea)
				route_color = '822433'
				if p.tipo == 'BU':
					route_type = 3
				elif p.tipo == 'ME':
					route_type = 1
					try:
						route_color = {
							'MEA': 'FF0000',
							'MEB': '0000FF',
							'MEC': '57B947',
						}[id_linea[:3]]
					except:
						print "Routes: linea non trovata", id_linea
						print p.id_linea
				elif p.tipo == 'TR':
					route_type = 0
				else:
					route_type = 2
					route_color = '000000'
				writer.writerow({
					'route_id': id_linea,
					'agency_id': AGENCY_ID,
					'route_short_name': id_linea,
					'route_long_name': p.descrizione,
					'route_type': str(route_type),
					'route_color': route_color,
					'route_text_color': '000000',
					'route_url': 'http://muovi.roma.it/percorso/js?query=%s&cl=1' % id_linea,
				})


def compute_trips(rete, grafo, dt, trips, stop_times, calendar):
	ok = 0
	ko = 0
	domani = dt + timedelta(days=1)
	dow = dt.weekday()
	partenze = PartenzeCapilinea.objects.filter(orario_partenza__gte=dt, orario_partenza__lt=domani).distinct()
	opz = rete.get_opzioni_calcola_percorso(True, True, True, True, 1)
	for p in partenze:
		t = p.orario_partenza
		try:
			id_percorso = p.id_percorso
			percorso = rete.percorsi[id_percorso]
		except:
			# print "Percorso non trovato: %s" % p.id_percorso
			continue
		if not percorso.soppresso:
			id_trip = "%s_%s_%d" % (id_percorso, t.strftime('%H:%M'), dow)
			service_id = '%s_%d' % (id_percorso, dow)
			trips.append({
				'route_id': percorso.id_linea,
				'service_id': service_id,
				'trip_id': id_trip,
				'trip_headsign': percorso.tratti_percorso[-1].t.rete_palina.nome,
				#'direction_id':
				'shape_id': id_percorso,
			})
			calendar[service_id] = dow
			dist = 0
			fermata = percorso.tratti_percorso[0].s
			i = 0
			while fermata is not None:
				hour = t.hour
				min = t.minute
				sec = t.second
				if t.weekday() != dow:
					hour += 24
				formatted_time = "%02d:%02d:%02d" % (hour, min, sec)
				stop_times.append({
					'trip_id': id_trip,
					'arrival_time': formatted_time,
					'departure_time': formatted_time,
					'stop_id': fermata.rete_palina.id_palina,
					'stop_sequence': str(i),
					'shape_dist_traveled': str(dist),
				})

				tp = fermata.tratto_percorso_successivo
				if tp is None:
					fermata = None
				else:
					try:
						a = grafo.archi[(5, tp.s.id_fermata, tp.t.id_fermata)]
						tpen, tempo = a.get_tempo(t, opz)
						if tpen > -1:
							t += timedelta(seconds=tempo)
							# print "TUTTO OK!!!"
							ok += 1
						else:
							print "Tempo -1", tp.s.id_fermata, tp.t.id_fermata
							ko += 1
					except:
						traceback.print_exc()
						print "Non trovato :-(", tp.s.id_fermata, tp.t.id_fermata
						ko += 1
					dist += tp.rete_tratto_percorsi.distanza()
					fermata = tp.t
					i += 1
	print ok, ko



def trips(path, rete, grafo):
	d = date.today()
	trips = []
	stop_times = []
	calendar = {}

	start_date = d

	for i in range(7):
		compute_trips(rete, grafo, d, trips, stop_times, calendar)
		d += timedelta(days=1)

	stop_date = d

	fn = os.path.join(path, 'trips.txt')
	with open(fn, 'w') as f:
		fieldnames = ['route_id', 'service_id', 'trip_id', 'trip_headsign', 'trip_short_name', 'direction_id', 'block_id', 'shape_id', 'wheelchair_accessible', 'bikes_allowed']
		writer = UnicodeDictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_MINIMAL, lineterminator='\n')
		writer.writeheader()
		for t in trips:
			writer.writerow(t)

	fn = os.path.join(path, 'stop_times.txt')
	with open(fn, 'w') as f:
		fieldnames = ['trip_id', 'arrival_time', 'departure_time', 'stop_id', 'stop_sequence', 'stop_headsign', 'pickup_type', 'drop_off_type', 'shape_dist_traveled', 'timepoint']
		writer = UnicodeDictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_MINIMAL, lineterminator='\n')
		writer.writeheader()
		for s in stop_times:
			writer.writerow(s)

	fn = os.path.join(path, 'calendar.txt')
	with open(fn, 'w') as f:
		days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
		fieldnames = ['service_id'] + days + ['start_date', 'end_date']
		writer = UnicodeDictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_MINIMAL, lineterminator='\n')
		writer.writeheader()
		for service_id in calendar:
			dow = calendar[service_id]
			c = {
				'service_id': service_id,
				'start_date': start_date.strftime('%Y%m%d'),
				'end_date': stop_date.strftime('%Y%m%d'),
			}
			for i in range(7):
				c[days[i]] = '1' if dow == i else '0'
			writer.writerow(c)


def shapes(path, rete):
	fn = os.path.join(path, 'shapes.txt')
	with open(fn, 'w') as f:
		fieldnames = ['shape_id', 'shape_pt_lat', 'shape_pt_lon', 'shape_pt_sequence', 'shape_dist_traveled']
		writer = UnicodeDictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_MINIMAL, lineterminator='\n')
		writer.writeheader()
		for id_percorso in rete.percorsi:
			p = rete.percorsi[id_percorso]
			if not p.soppresso:
				i = 0
				dist = 0.0
				ptold = None
				for pt in p.iter_punti():
					if ptold is not None:
						dist += distance(pt, ptold)
					ptold = pt
					lon, lat = gbfe_to_wgs84(pt[0], pt[1])
					writer.writerow({
						'shape_id': p.id_percorso,
						'shape_pt_lat': str(lat),
						'shape_pt_lon': str(lon),
						'shape_pt_sequence': str(i),
						'shape_dist_traveled': str(dist),
					})
					i += 1


def zipdir(path, zip):
	for root, dirs, files in os.walk(path):
		for file in files:
			zip.write(os.path.join(root, file), file)


def _generate_gtfs(path, rete, grafo):
	print "Agenzia"
	agency(path)
	print "Fermate"
	stops(path, rete)
	print "Linee"
	routes(path, rete)
	print "Corse"
	trips(path, rete, grafo)
	print "Shape"
	shapes(path, rete)


def generate_gtfs(filename, rete, grafo):
	gtfs_dir = tempfile.mkdtemp()
	_generate_gtfs(gtfs_dir, rete, grafo)
	print "Compressing"
	zipf = zipfile.ZipFile(filename, 'w', zipfile.ZIP_DEFLATED)
	zipdir(gtfs_dir, zipf)
	shutil.rmtree(gtfs_dir)
