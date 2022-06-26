# coding: utf-8

from __future__ import print_function
from collections import defaultdict
from constance import config

from django.contrib.gis.gdal.geometries import LineString

from paline.models import *
from django.contrib.gis.geos import Point, LineString
from datetime import date, time, datetime, timedelta
from contextlib import contextmanager
from django import db
from django.db import transaction
import requests
from servizi import utils
from paline import geomath
from paline import geolinestring
import settings
from pprint import pprint
import traceback
import json
import cPickle as pickle
import os
import csv


STATIC_GTFS_URL = 'https://romamobilita.it/sites/default/files/rome_static_gtfs.zip'
MAPPING_FILE = os.path.join(settings.TROVALINEA_PATH_RETE, 'mapping_gtfs.dat')
LIMIT = None
MAX_TIMETABLE_DAYS = 14


@contextmanager
def work_on_gtfs(url=STATIC_GTFS_URL, last_update=None, remap_only=False):
	"""
	Temporarily download and decompress static GTFS files

	If there is no update, don't download the whole thing

	:param url: url of GTFS
	:yield: zip_dir, last_update_string
	- zip_dir: temporary dir where zip file is saved, or None (no update)
	"""
	done = False

	if remap_only:
		last_update = config.GIANO_DATA_MAPPING_RETE

	if last_update is not None:
		lu = requests.head(url, verify=False).headers['Last-Modified']
		try:
			lu_dt = utils.parse_http_datetime(lu)
		except:
			lu_dt = None

		if lu_dt is not None and lu_dt <= last_update:
			yield None, last_update
			done = True

	if not done:
		with utils.temp_dir() as path:
			print("Downloading")
			zip_path = os.path.join(path, 'gtfs.zip')
			res = requests.get(url, verify=False)
			lu = res.headers['Last-Modified']
			lu_dt = utils.parse_http_datetime(lu)
			cnt = res.content
			with open(zip_path, 'wb') as w:
				w.write(cnt)
			print("Uncompressing")
			with utils.uncompress_zip(zip_path) as zip_dir:
				yield zip_dir, lu_dt


class Operator(object):
	def __init__(self, name):
		self.name = name


class Stop(object):
	def __init__(self, stop_id, stop_code, name, desc, x, y, parent_sid):
		self.stop_id = stop_id
		self.stop_code = stop_code if stop_code.strip() != "" else self.create_id(x, y)
		self.name = name
		self.desc = desc
		self.x = x
		self.y = y
		self.parent_sid = parent_sid if parent_sid != "" else None
		self.instance = None

	def create_id(self, x, y):
		xs = "%03.0f" % (x,)
		ys = "%03.0f" % (y,)
		return "C" + xs[-3:] + ys[-3:]

	def similar(self, s):
		if self.name != "":
			return self.name.lower() == s.name.lower()
		return self.stop_code == s.stop_code

	def similar_any(self, stops):
		for s in stops:
			if self.similar(s):
				return True
		return False


class Line(object):
	def __init__(self, id, name, typ, operator, desc):
		self.id = id
		self.name = name
		# 0: Tram o Roma Giardinetti, 1: Metro, 2: FL, 3: Bus, 106: FC, 109: FC
		self.desc = desc
		self.typ = typ
		self.routes = {}
		self.routes_by_direction = defaultdict(list)
		self.operator = operator

	def sort_routes_by_trips(self):
		"""
		Sort routes by number of trips and determine trip type

		:return:
		"""
		routes_with_stops = [r for r in self.routes.values() if len(r.stop_seq) > 0]
		routes_by_trips = sorted(routes_with_stops, key=lambda r: len(r.trips), reverse=True)
		for r in routes_by_trips:
			self.routes_by_direction[r.direction].append(r)
		for routes in self.routes_by_direction.values():
			num = defaultdict(int)
			r0 = routes[0]
			for r in routes[1:]:
				at = r.infer_alt_type(r0)
				r.alt_num = num[at]
				num[at] += 1

	def __unicode__(self):
		print(u"<Line {} [{}]>".format(self.name, self.id))


class Trip(object):
	def __init__(self, id):
		self.id = id
		self.departure = None
		self.route = None
		self.service = None
		# Each stop_time is a tuple (stop, time)
		self.stop_times = {}
		self.stop_time_seq = []
		self.departure_mm = utils.MinMaxValueData()

	def sort_stop_times(self):
		a = list(self.stop_times.items())
		a.sort()
		self.stop_time_seq = [x[1] for x in a]
		self.departure = self.departure_mm.data['dep_time']

	def __unicode__(self):
		return "Trip {}".format(self.id)


class Route(object):
	def __init__(self):
		self.id = None
		self.route_id = None
		self.line = None
		# Map stop fid to stop count
		self.stops = defaultdict(int)
		self.stop_seq = []
		self.dist_seq = []
		self.trips = []
		self.direction = None
		self.destination = None
		self.alt_type = None
		self.alt_num = 0
		# Map seq to (x, y)
		self.coord = {}
		# List of 2-tuples: (x, y)
		self.coord_seq = []

	# def _sort_stop_seq_dist(self):
	# 	l = list(self.stops)
	# 	l.sort(key=lambda s: s[1])
	# 	self.stop_seq = [s[0] for s in l]
	# 	self.dist_seq = [s[1] for s in l]
	#
	# def _sort_stop_seq_topo(self):
	# 	dep = defaultdict(set)
	# 	for t in self.trips:
	# 		old_stop = None
	# 		for stop, time in t.stop_time_seq:
	# 			if old_stop is not None:
	# 				dep[stop].add(old_stop)
	# 			old_stop = stop
	# 	for s in toposort(dep):
	# 		if len(s) > 1 and len(self.stop_seq) > 0:
	# 			print("Ambiguous ({}) topological sort for route {}, guessing order geometrically".format(len(s), self))
	# 			s0 = self.stop_seq[-1]
	# 			s = list(s)
	# 			s.sort(key=lambda s1: geomath.distance((s0.x, s0.y), (s1.x, s1.y)))
	# 		elif len(s) > 2:
	# 			print("Ambiguous topological sort for route {} from the beginning, savagely guessing order".format(self))
	# 		for p in s:
	# 			self.stop_seq.append(p)
	# 	self.dist_seq = [None for x in self.stop_seq]
	#
	# def sort_stop_seq(self):
	# 	if self.line.typ != '2':
	# 		self._sort_stop_seq_dist()
	# 	else:
	# 		self._sort_stop_seq_topo()

	def infer_alt_type(self, other):
		ss = self.stop_seq[0]
		st = self.stop_seq[-1]
		os = other.stop_seq[0]
		ot = other.stop_seq[-1]
		if ss.similar(os) and st.similar(ot):
			self.alt_type = 'D'
		elif ss.similar(os):
			if st.similar_any(other.stop_seq):
				self.alt_type = 'L'
			elif ot.similar_any(self.stop_seq):
				self.alt_type = 'P'
			else:
				self.alt_type = 'D'
		elif st.similar(ot):
			if ss.similar_any(other.stop_seq):
				self.alt_type = 'L'
			elif ot.similar_any(self.stop_seq):
				self.alt_type = 'P'
			else:
				self.alt_type = 'D'
		else:
			self.alt_type = 'D'
		return self.alt_type

	def __str__(self):
		return "<Route {}, {}>".format(self.line.name, self.id)

	def process_coord(self, net):
		if len(self.stop_seq) < 2:
			print("Route {}: not enough coord points".format(self))
			return

		for i, subseq in enumerate(geolinestring.distance_split(self.coord_seq, self.dist_seq)):
			if 0 < i < len(self.stop_seq):
				s = self.stop_seq[i - 1]
				t = self.stop_seq[i]
				key = (s, t)
				if key not in net.segments:
					net.segments[key] = Segment(s, t, subseq, self.line.typ)

	def finalize_shapes_and_stops(self, net):
		cs = self.coord.items()
		cs.sort()
		self.coord_seq = [x[1] for x in cs]
		if len(self.coord_seq) < 2:
			print("Trip without shape: ", self.line, self.route_id)
			return

		# sl = geolinestring.SplittableLinestring(self.coord_seq)
		stops_with_multiplicity = [(net.stops[fid], n) for fid, n in self.stops.items()]
		# ss = sl.project_and_sort(stops_with_multiplicity, point_extractor=lambda s: (s.x, s.y))
		ss = geolinestring.project_and_sort_multi(self.coord_seq, stops_with_multiplicity, point_extractor=lambda s: (s.x, s.y))
		self.stop_seq = [s[1] for s in ss]
		self.dist_seq = [s[0] for s in ss]


class Segment(object):
	def __init__(self, stop_s, stop_t, points, typ):
		self.stop_s = stop_s
		self.stop_t = stop_t
		self.points = points
		self.typ = typ


class Service(object):
	def __init__(self, sid, from_date, to_date, days):
		self.sid = sid
		self.from_date = from_date
		self.to_date = to_date
		# List of booleans; 0 = Monday
		self.days = days
		# Map dates to: 1 --> added, 2 --> removed
		self.exception_dates = {}

	def active_on(self, dt, prev_day=False):
		if prev_day:
			dt -= timedelta(days=1)
		d = dt.date()
		if d in self.exception_dates:
			return self.exception_dates[d] == 1
		return self.days[d.weekday()]


class GtfsNetwork(object):
	def __init__(self):
		self.operators = {}
		self.stops = {}
		self.lines = {}
		self.trips = {}
		self.routes = defaultdict(Route)
		self.services = {}
		# Map (stop_s, stop_t) to Segment
		self.segments = {}


def correct_railway_activation_days(net):
	print("Checking railway activation days")
	r_services = set()
	for t in net.trips.values():
		if t.route.line.typ == '2':
			r_services.add(t.service)
	d0 = 0
	d6 = 0
	for s in r_services:
		if s.days[0]:
			d0 += 1
		if s.days[6]:
			d6 += 1
	if d6 > d0:
		print("Correcting railway activation days")
		# There are more trips on sunday than monday:
		# apply an offset of 1 day by right-shifting lists days
		for s in r_services:
			s.days = s.days[1:] + s.days[:1]


def recover_route_ids(net):
	print("Recovering ids for routes")
	print("Loading network")
	ps = Percorso.objects.by_date().filter(soppresso=False)
	fermate_to_percorso = {}
	for p in ps:
		fs = Fermata.objects.by_date().filter(percorso=p).order_by('progressiva')
		fermate_tuple = tuple(f.palina.id_palina for f in fs)
		fermate_to_percorso[fermate_tuple] = p.id_percorso

	print("Mapping routes")
	found = 0
	not_found = 0
	routes_not_found = []
	for route in net.routes.values():
		t = tuple(s.stop_code for s in route.stop_seq)
		if t in fermate_to_percorso:
			route.route_id = fermate_to_percorso[t]
			del fermate_to_percorso[t]
			found += 1
		else:
			not_found += 1
			routes_not_found.append(route)

	left_t_sets = set()
	recovered = 0
	for t in fermate_to_percorso:
		left_t_sets.add(t)

	i = MaxIdPercorso.get_max_id_percorso()

	for route in routes_not_found:
		t_route = set(s.stop_code for s in route.stop_seq)
		min_dist = None
		min_t = None
		for t in left_t_sets:
			t_set = set(t)
			dist = len(t_set.union(t_route)) - len(t_set.intersection(t_route))
			if dist <= 6:
				if min_dist is None or dist < min_dist:
					min_dist = dist
					min_t = t
		if min_t is not None:
			route_id = fermate_to_percorso[min_t]
			del fermate_to_percorso[min_t]
			left_t_sets.remove(min_t)
			recovered += 1
		else:
			i += 1
			route_id = "RM{}".format(i)
		route.route_id = route_id

	MaxIdPercorso.set_max_id_percorso(i)

	print("  {} found, {} not found, {} recovered".format(found, not_found, recovered))
	print("Recovering ids for routes done")


def build_network_structure(path, from_date=None):
	"""
	Parse static GTFS and build network structure

	- each shape_id is a route, and is mapped to its line
	- for each shape_id, we record the sequence of its stops
	- for each shape_id, we count trips (and record their departure times)
	- for each line, we order shape_id's by trip count:
	  - if the first shape is circular, line is circular
	  - otherwise, the first two shapes are the main routes
	  - for each subsequent shape, if it shares enough stops
	    with one of the main routes, it is deemed a variant of it;
	    otherwise it is an outlier

	To be done next:
	- determine which kind of variants routes are (limited, prolonged, etc.)
	- build geospatial representation of route segments

	:param path: path to uncompressed GTFS files
	:param shape_id_to_percorso: map each shape_id to the (old or new) id_percorso
	:return: GtfsNetwork instance
	"""
	# 0. Mapping stop_ids to stop_codes
	net = GtfsNetwork()

	if from_date is None:
		now = datetime.now()
		from_date = datetime(now.year, now.month, now.day)
	to_date = from_date + timedelta(days=7)

	print("Loading operators")
	with open(os.path.join(path, 'agency.txt')) as f:
		r = csv.DictReader(f, delimiter=',', lineterminator='\n')
		for row in r:
			net.operators[row['agency_id']] = Operator(row['agency_name'])

	print("Loading stop codes")
	with open(os.path.join(path, 'stops.txt')) as f:
		r = csv.DictReader(f, delimiter=',', lineterminator='\n')
		for row in r:
			lon = float(row['stop_lon'])
			lat = float(row['stop_lat'])
			x, y = geomath.wgs84_to_gbfe(lon, lat)
			fid = row['stop_id']
			sc = row['stop_code']
			parent_sid = row['parent_station']
			s = Stop(fid, sc, row['stop_name'], row['stop_desc'], x, y, parent_sid)
			net.stops[fid] = s

	print("Collapsing stops")
	for fid in net.stops:
		s = net.stops[fid]
		if s.parent_sid is not None:
			net.stops[fid] = net.stops[s.parent_sid]

	print("Deduplicating stops")
	stops_by_code = {}
	for fid in net.stops:
		s = net.stops[fid]
		if s.stop_code in stops_by_code:
			print("Duplicate stop code: {}".format(s.stop_code))
			net.stops[fid] = stops_by_code[s.stop_code]
		else:
			stops_by_code[s.stop_code] = s

	# 1. Load services
	print("Loading services")
	with open(os.path.join(path, 'calendar.txt')) as f:
		r = csv.DictReader(f, delimiter=',', lineterminator='\n')
		for row in r:
			sid = row['service_id']
			net.services[sid] = Service(
				sid,
				datetime.strptime(row['start_date'], "%Y%m%d"),
				datetime.strptime(row['end_date'], "%Y%m%d"),
				[
					row['monday'] == '1',
					row['tuesday'] == '1',
					row['wednesday'] == '1',
					row['thursday'] == '1',
					row['friday'] == '1',
					row['saturday'] == '1',
					row['sunday'] == '1',
				],
			)

	print("Loading service exceptions")
	no_days = [False] * 7
	with open(os.path.join(path, 'calendar_dates.txt')) as f:
		r = csv.DictReader(f, delimiter=',', lineterminator='\n')
		for row in r:
			sid = row['service_id']
			d = datetime.strptime(row['date'], "%Y%m%d").date()
			if sid not in net.services:
				net.services[sid] = Service(sid, from_date, to_date, no_days)
			net.services[sid].exception_dates[d] = int(row['exception_type'])

	# 2. Map id --> objects
	print("Loading lines")
	with open(os.path.join(path, 'routes.txt')) as f:
		r = csv.DictReader(f, delimiter=',', lineterminator='\n')
		for row in r:
			rid = row['route_id']
			name = row['route_short_name']
			operator = net.operators[row['agency_id']]
			net.lines[rid] = Line(rid, name, row['route_type'], operator, row['route_long_name'])

	print("Loading trips")
	with open(os.path.join(path, 'trips.txt')) as f:
		r = csv.DictReader(f, delimiter=',', lineterminator='\n')
		for row in r:
			if True: # row.get('exceptional', '0') != '1':
				tid = row['trip_id']
				sid = row['shape_id']
				r = net.routes[sid]
				r.id = sid
				r.line = net.lines[row['route_id']]
				r.destination = row['trip_headsign']
				r.direction = row['direction_id']
				r.line.routes[sid] = r
				t = Trip(tid)
				net.trips[tid] = t
				t.route = r
				t.service = net.services[row['service_id']]
				r.trips.append(t)

	# 5. Load shapes
	print("Loading shapes")
	with open(os.path.join(path, 'shapes.txt')) as f:
		r = csv.DictReader(f, delimiter=',', lineterminator='\n')
		for row in utils.limiter(r, LIMIT):
			sid = row['shape_id']
			if sid not in net.routes:
				print("Not found route:", sid)
			else:
				r = net.routes[sid]
				lon = float(row['shape_pt_lon'])
				lat = float(row['shape_pt_lat'])
				seq = int(row['shape_pt_sequence'])
				# dist = float(row['shape_dist_traveled']) if r.line.typ != '2' else None
				x, y = geomath.wgs84_to_gbfe(lon, lat)
				r.coord[seq] = (x, y)

	print("Loading stop sequences")
	# 3. Map each shape_id to the sequence of stops
	with open(os.path.join(path, 'stop_times.txt')) as f:
		r = csv.DictReader(f, delimiter=',', lineterminator='\n')
		for row in utils.limiter(r, LIMIT):
			tid = row['trip_id']
			if tid in net.trips:
				t = net.trips[tid]
				p = t.route
				ss = int(row['stop_sequence'])
				fid = row['stop_id']
				stop = net.stops[fid]
				dep_time = row['departure_time']
				t.departure_mm.add(ss, dep_time=dep_time)
				if t == p.trips[0]:
					p.stops[fid] += 1
				# try:
				# 	dist = float(row['shape_dist_traveled'])
				# 	p.stops.add((stop, dist))
				# except ValueError:
				# 	# p.stops[ss] = (net.stops[fid], None)
				# 	dist = row['shape_dist_traveled']
				# 	print("Could not convert to float: ", dist)
				# 	print("Route: ", p)
				# 	# print("Number of trips: ", len(p.trips))
				if p.line.typ == '2':
					t.stop_times[ss] = (stop, dep_time)

	print("Finalizing shapes and stops")
	for r in net.routes.values():
		# print(r.line)
		r.finalize_shapes_and_stops(net)

	print("Sorting stop times")
	for t in net.trips.values():
		t.sort_stop_times()

	# print("Sorting stops")
	# for r in net.routes.values():
	# 	r.sort_stop_seq()

	# 4. For each line, sort routes by number of trips
	print("Sorting routes by trips")
	for l in net.lines.values():
		l.sort_routes_by_trips()

	# 6. Computing segments
	print("Computing segments")
	for r in net.routes.values():
		r.process_coord(net)
	print("Loading predefined segments (railways)")
	# load_predefined_segments(net)

	# 7. Correcting railway activation days
	correct_railway_activation_days(net)

	return net


def genera_rete(inizio_validita):
	print("Creazione nuova versione della rete...")
	v = VersionePaline.auto_create(inizio_validita)
	v.save()
	print("Creata versione %d" % v.numero)


def carica_carteggi():
	print("Estendo la validità dei carteggi")
	Carteggio.extend_to_current_version()


def carica_paline(net):
	print("Carico paline")
	for stop in net.stops.values():
		if stop.instance is None:
			id_palina = stop.stop_code
			nome = stop.name
			p = Palina(
				id_palina=id_palina,
				nome=nome,
				descrizione=stop.desc,
				soppressa=False,
				geom = Point(stop.x, stop.y, srid=3004)
			)
			p.save()
			stop.instance = p
			parti = utils.multisplit(nome, [" ", "/"])
			for parte in parti:
				NomePalina(
					parte=parte,
					palina=p
				).save()


def carica_gestori(net):
	print("Carico gestori")
	for g in net.operators.values():
		nome = g.name
		go = Gestore(
			nome=nome,
			descrizione=nome,
		)
		go.save()
		g.instance = go


_TYPES = {
	'0': 'TR',
	'1': 'ME',
	'2': 'FR',
	'3': 'BU',
	'106': 'FC',
	'109': 'FC',
	'BU': 'BU',
	'TR': 'TR',
	'ME': 'ME',
	'FC': 'FC',
	'FR': 'FR',
}


_FC_NAMES = {'RL', 'RMVT', 'RMG'}


def typ_to_tipo(t):
	if t in _TYPES:
		return _TYPES[t]
	print("Unknown line type: {}".format(t))
	return t


def carica_linee(net):
	print("Carico linee")
	for l in net.lines.values():
		tipo = typ_to_tipo(l.typ)
		if l.name in _FC_NAMES:
			tipo = 'FC'
		g = l.operator.instance
		id_linea = l.name
		lo = Linea(
			id_linea=id_linea,
			monitorata=True,
			gestore=g,
			tipo=tipo,
		)
		lo.save()
		l.instance = lo


def carica_percorsi(net):
	# Carico percorsi
	print("Carico percorsi e fermate")
	for r in net.routes.values():
		if len(r.stop_seq) == 0:
			print("Percorso {} senza fermate".format(r))
			continue
		if r.direction == '0':
			verso = 'A'
			precart = 'A'
		else:
			verso = 'R'
			precart = 'R'
		id_percorso = r.route_id
		linea = r.line.instance
		partenza = r.stop_seq[0].instance
		arrivo = r.stop_seq[-1].instance
		if partenza == arrivo:
			verso = 'C'
			precart = ''
		carteggio = ''
		if r.alt_type is not None:
			carteggio = r.alt_type
			if r.alt_num > 0:
				carteggio += str(r.alt_num)
		po = Percorso(
			id_percorso=id_percorso,
			linea=linea,
			partenza=partenza,
			arrivo=arrivo,
			verso=verso,
			carteggio=precart + carteggio,
			carteggio_quoz=carteggio,
			descrizione=None if r.line.desc == "" else r.line.desc,
			no_orari=False,
			note_no_orari='',
			soppresso=False,
		)
		po.save()
		for i, stop in enumerate(r.stop_seq):
			Fermata(
				percorso=po,
				palina=stop.instance,
				progressiva=i,
			).save()


def carica_trip(net, last_update):
	print("Carico trip GTFS")
	GtfsTrip.objects.all().delete()
	for tid, t in net.trips.items():
		GtfsTrip(
			trip_id=tid,
			id_percorso=t.route.route_id,
		).save()
	config.GIANO_DATA_MAPPING_RETE = last_update


def carica_tratti_percorsi(net):
	print("Carico tratti percorsi")
	for s in net.segments.values():
		if len(s.points) > 1:
			try:
				tp = TrattoPercorsi(
					palina_s=s.stop_s.instance,
					palina_t=s.stop_t.instance,
					geom=LineString(s.points, srid=3004),
					tipo=typ_to_tipo(s.typ),
				)
				tp.save()
			except:
				traceback.print_exc()
				pprint(s.points)
		else:
			print("Segment with {} points ({}): ({}, {})".format(len(s.points), s.typ, s.stop_s.stop_code, s.stop_t.stop_code))


def carica_orari_partenza(inizio, net):
	print("Carico orari di partenza")
	PartenzeCapilinea.objects.filter(orario_partenza__gte=inizio).delete()
	max_date = inizio + timedelta(days=MAX_TIMETABLE_DAYS)
	one_day = timedelta(days=1)
	for r in net.routes.values():
		rid = r.route_id
		for t in r.trips:
			if t.departure is None:
				print("Trip without departure:", t)
				continue
			s = t.service
			fd = s.from_date
			td = s.to_date + one_day
			hour = int(t.departure[:2])
			minute = int(t.departure[3:5])
			prev_day = False
			if hour >= 24:
				hour -= 24
				prev_day = True
			n = datetime(
				fd.year,
				fd.month,
				fd.day,
				hour,
				minute,
			)
			if prev_day:
				n += one_day
			while n < td and n <= max_date:
				if n >= inizio and s.active_on(n, prev_day):
					pc = PartenzeCapilinea(
						id_percorso=rid,
						orario_partenza=n,
					)
					pc.save()
				n += one_day


def carica_orari_treni(net):
	print("Carico orari treni")
	OrarioTreno.objects.all().delete()
	for t in net.trips.values():
		if len(t.stop_time_seq) > 0:
			for d in [0, 5, 6]:
				if t.service.days[d]:
					ot = OrarioTreno(
						id_percorso=t.route.route_id,
						giorno=d,
						orari=",".join(x[1] for x in t.stop_time_seq),
						id_paline=",".join(x[0].stop_code for x in t.stop_time_seq),
					)
					ot.save()


def attiva_nuova_rete():
	print("Attivazione nuova rete...")
	v = VersionePaline.objects.ultima()
	v.attiva = True
	v.save()


def carica_rete(net, inizio_validita=None):
	try:
		if inizio_validita is None:
			inizio_validita = datetime.now()
		transaction.enter_transaction_management()
		transaction.managed(True)
		genera_rete(inizio_validita)
		carica_carteggi()
		carica_paline(net)
		carica_gestori(net)
		carica_linee(net)
		carica_percorsi(net)
		carica_trip(net, inizio_validita)
		carica_tratti_percorsi(net)
		carica_orari_partenza(inizio_validita, net)
		carica_orari_treni(net)
		# carica_speciale()
		attiva_nuova_rete()
		transaction.commit()
	except BaseException as e:
		transaction.rollback()
		traceback.print_exc()
		raise e
	finally:
		transaction.leave_transaction_management()
	db.reset_queries()


def carica_speciale():
	id_linea = "140"
	desc_linea = "140 Fantastica"
	id_percorso = '140_S_A'
	fermate = [
		"Staz.ne Rodari",
		"Grammatica della fantasia",
		"Maramao al Colosseo",
		"Vado via con i gatti",
		"Campidoglio al pistacchio",
		"Pantheon al limone",
		"Il libro degli errori",
		"Il pianeta degli alberi di Natale",
		"Gelsomino nel paese dei bugiardi",
		"Il treno delle filastrocche",
		"La torta in cielo",
		"Favole al telefono",
		"Il pescatore di ponte Garibaldi",
		"P.za Munari",
		"La freccia azzurra",
		"Sulla spiaggia di Ostia",
		"Il libro dei perché",
		"Il secondo libro delle filastrocche",
		"Novelle fatte a macchina",
		"L.go Andersen",
		"Le avventure di Cipollino",
		"C'era due volte il barone Lamberto",
		"Le favolette di Alice",
		"Piccoli vagabondi",
		"Dieci chili di luna",
		"Il libro dei mesi",
		"Venti storie più una",
		"Esercizi di fantasia",
		"Gli affari del signor Gatto",
		"Filastrocche in cielo e in terra",
		"Cip nel televisore",
		"Fiabe lunghe un sorriso",
		"Il gioco dei quattro cantoni",
		"Fantas(t)i(c)a",
	]
	ps = []
	for i, f in enumerate(fermate):
		p = Palina(
			id_palina="spx_{}".format(i),
			nome=f,
			descrizione=f,
			soppressa=False,
			geom=None
		)
		p.save()
		ps.append(p)

	g = Gestore.objects.by_date().all()[0]
	l = Linea(
		id_linea=id_linea,
		monitorata=True,
		gestore=g,
		tipo='BU',
	)
	l.save()
	po = Percorso(
		id_percorso=id_percorso,
		linea=l,
		partenza=ps[0],
		arrivo=ps[-1],
		verso='A',
		carteggio='A',
		carteggio_quoz='',
		descrizione=desc_linea,
		no_orari=False,
		note_no_orari='',
		soppresso=False,
	)
	po.save()
	for i, p in enumerate(ps):
		Fermata(
			percorso=po,
			palina=p,
			progressiva=i + 1,
		).save()


def rimappa_rete(net, last_update):
	try:
		transaction.enter_transaction_management()
		transaction.managed(True)
		carica_trip(net, last_update)
		transaction.commit()
	except BaseException as e:
		transaction.rollback()
		raise e
	finally:
		transaction.leave_transaction_management()
	# transaction.rollback()
	db.reset_queries()


def download_gtfs_and_build_network_structure():
	with work_on_gtfs(settings.GTFS_ST_URL) as res:
		path, last_update = res
		print(last_update)
		if path is not None:
			net = build_network_structure(path)
			return net


def download_gtfs_and_map(last_update=None, remap_only=False):
	"""
	Load new static GTFS and return mapping, if there is an update

	:param last_update: Timestamp string of previous update, or None
	:return: mapping dictionary, if there is an update, or None
	"""
	with work_on_gtfs(settings.GTFS_ST_URL, last_update, remap_only) as res:
		path, last_update = res
		print(last_update)
		if path is not None:
			net = build_network_structure(path)
			recover_route_ids(net)
			if not remap_only:
				carica_rete(net, last_update)
			else:
				rimappa_rete(net, last_update)
			return last_update
		return None


if __name__ == '__main__':
	# download_gtfs_and_map()
	build_network_structure('/home/luca/Documenti/dev/romamobile/roma-mobile-skeed/paline/gtfs/static')


