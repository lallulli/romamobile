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

#import psyco
#psyco.full()
import datetime
import traceback
import pyximport; pyximport.install()
#from shapely.geometry import LineString, Point, MultiPoint
#from IPython.Shell import IPShellEmbed
import codecs
from grafo import Nodo, Arco, Grafo
from geomath import wgs84_to_gbfe
import shapereader
import cPickle as pickle
import geomath
import math
from tratto import TrattoRoot, TrattoPiedi, TrattoPiediArco, TrattoBici, TrattoBiciArco, TrattoAutoAttesaZTL
from tratto import TrattoAuto, TrattoAutoArco
import raggiungibilita
from django.contrib.gis.geos import Point
from ztl.models import ZTL
from gis.models import Multipoligono
from pprint import pprint
from paline.models import *
from gis.models import punti2linestring
from xml.etree import ElementTree as ET
from servizi.utils import model2contenttype, transaction
from paline.caricamento_rete.dbf import Dbf
from django import db

class Repository(object):
	def __init__(self):
		object.__init__(self)
		self.d = {}
		self.s = []

	def __getitem__(self, s):
		if s not in self.d:
			n = len(self.s)
			self.d[s] = n
			self.s.append(s)
			return n
		return self.d[s]
	
	def inverse_search(self, i):
		return self.s[i]


	#def __iter__(self):
	#	for k in self.d:
	#		yield k


	def __in__(self, k):
		return k in self.d

types = {
		'car': 1,
		'walk': 2,
	}

car_coeff = [1, 1, 0.9, 0.85, 0.75, 0.7, 0.7, 0.7, 0.7]
car_coeff = [0.6 * x for x in car_coeff]
car_ztl_coeff = 0.01
bike_coeff = [0.001, 0.1, 0.5, 0.7, 1, 1, 1, 1, 1]
bike_ztl_coeff = 0.4
walk_coeff = [0.001, 0.5, 0.9, 1, 1, 1, 1, 1, 1]

highways = Repository()
streets = Repository()


class NodoTomTom(Nodo):
	tipo_nodi = 11
	def __init__(self, id, x, y, special_type_id=11):
		Nodo.__init__(self, (special_type_id, id))
		self.x = x
		self.y = y
		
	def __unicode__(self):
		return self.id
	
	def serialize(self):
		return {
			'id': self.id,
			'x': self.x,
			'y': self.y,
		}
		
	def get_coordinate(self):
		return [(self.x, self.y)]
	
					
	@classmethod
	def deserialize(cls, grafo, res):
		n = NodoTomTom(
				res['id'][1],
				res['x'],
				res['y'],
			)
		grafo.add_nodo(n)
		
		
class ArcoTomTom(Arco):
	tipo_archi = 12
	def __init__(
			self,
			eid,
			count,
			s,
			t,
			nome,
			auto,
			velocita,
			lunghezza,
			punti,
			tipo,
			ztl,
			special_type_id=12,
			tpl=False,
		):
		Arco.__init__(self, s, t, (special_type_id, eid, count))
		self.name = streets[nome]
		self.auto = auto
		self.velocita = velocita
		self.w = lunghezza
		self.punti = punti
		self.tipo = tipo
		self.ztl = ztl
		self.tpl = tpl

	def get_nome(self):
		return streets.inverse_search(self.name)
	
	def attraversabile_vicini(self, opzioni):
		return True	

	def get_distanza(self):
		return self.w

	def serialize(self):
		return {
			'id': self.id,
			'sid': self.s.id,
			'tid': self.t.id,
			'nome': self.get_nome(),
			'velocita': self.velocita,
			'auto': self.auto,
			'lunghezza': self.w,
			'punti': self.punti,
			'tipo': self.tipo,
			'ztl': self.ztl,
			'tpl': self.tpl,
		}
		
	def to_model(self):
		#pprint(self.serialize())
		return StradaTomtom(
			eid=self.id[1],
			count=self.id[2],
			sid=self.s.id[1],
			tid=self.t.id[1],
			nome_luogo=self.get_nome(),
			velocita=self.velocita,
			auto=self.auto,
			lunghezza=self.w,
			geom=punti2linestring(self.punti),
			tipo=self.tipo,
			ztl=self.ztl,
			tpl=self.tpl,
		)

		
	@classmethod
	def deserialize(cls, grafo, res):
		e = ArcoTomTom(
			res['id'][1],
			res['id'][2],
			grafo.nodi[res['sid']],
			grafo.nodi[res['tid']],
			res['nome'],
			res['auto'],
			res['velocita'],
			res['lunghezza'],
			res['punti'],
			res['tipo'],
			res['ztl'],
			tpl=res['tpl'] if 'tpl' in res else False,
		)
		grafo.add_arco(e)
	

	def get_coordinate(self):
		"""
		Restituisce una lista di coppie: le coordinate dei punti. Oppure None
		"""				
		return self.punti
	
	def get_distanza(self):
		return self.w

	def get_attesa_ztl(self, t, opz):
		ztl_wait = 0
		if len(self.ztl) > 0:
			non_auth = self.ztl - opz['ztl']
			rete = opz['rete']
			if rete is not None:
				# Se non ho informazioni sulla rete, considero tutte le ZTL percorribili
				for z in non_auth:
					w = rete.ztl[z].attesa(t, opz['rev'])
					if w is not None:
						ztl_wait = w
						break
		return ztl_wait

	
	def get_tempo(self, t, opz):
		if opz['auto']:
			s = self.velocita * car_coeff[self.tipo]
			if s > 0 and self.auto and (not self.tpl or opz['tpl']):
				s = self.velocita * car_coeff[self.tipo]
				tempo = 3.6 * self.w / s + self.get_attesa_ztl(t, opz)
				return (tempo / opz['penalizzazione_auto'], tempo)
			else:
				return (-1, -1)
		else:
			context = self.s.get_context(opz)
			if not opz['primo_tratto_bici']:
				bici = False
			else:
				if context['primo_tratto_bici'] and context['max_distanza_bici'] - self.get_distanza() > 0:
					bici = True
				else:
					bici = False
			if bici:
				if self.auto:
					ztl = 1 if not self.ztl else bike_ztl_coeff
					n = self.get_nome()
					cambio_strada = 1 if (n != '' and self.name != context['nome_strada']) else 0
					tempo = 3.6 * self.w / opz['v_bici'] + cambio_strada * opz['t_bici_cambio_strada']
					return (tempo / (ztl * bike_coeff[self.tipo]), tempo)
				return (-1, -1)
			else:
				tempo = 3.6 * self.w / (opz['v_piedi'])
				return (tempo * (opz['penal_pedonale_0'] + opz['penal_pedonale_1'] * math.pow(context['distanza_piedi'], opz['penal_pedonale_exp'])) / walk_coeff[self.tipo], tempo)
			return (-1, -1)
		
	def costruisci_percorso(self, t, opzioni):
		vars = self.s.get_vars(opzioni)
		context_s = self.s.get_context(opzioni)
		context_t = self.t.get_context(opzioni)
		if opzioni['auto']:
			ztl_wait = self.get_attesa_ztl(vars.time, opzioni)
			if type(t) != TrattoAuto or ztl_wait > 0:
				t = TrattoAuto(t.parent, vars.time, opzioni['carsharing'])
			if ztl_wait > 0:
				TrattoAutoAttesaZTL(t, vars.time, ztl_wait)
			TrattoAutoArco(t, vars.time, self, 3.6 * self.w / (self.velocita * car_coeff[self.tipo]))
		elif not context_s['primo_tratto_bici']:
			if type(t) != TrattoPiedi:
				t = TrattoPiedi(t.parent, vars.time)
			TrattoPiediArco(t, vars.time, self, 3.6 * self.w / opzioni['v_piedi'])
		elif context_t['primo_tratto_bici']:
			TrattoBiciArco(t, vars.time, self, 3.6 * self.w / opzioni['v_bici'])
		else:
			t = TrattoPiedi(t.parent, vars.time)
			TrattoPiediArco(t, vars.time, self, 3.6 * self.w / opzioni['v_bici'])
		return t

	def aggiorna_contesto(self, opz, rev=False):
		context = self.duplica_contesto(opz, rev)
		if context['primo_tratto_bici']:
			d = context['max_distanza_bici']  
			d -= self.get_distanza()
			if d < 0:
				d = 0
				context['primo_tratto_bici'] = False
			context['max_distanza_bici'] = d
			if self.get_nome() != '':
				context['nome_strada'] = self.name
		else:
			context['distanza_piedi'] += self.get_distanza()

	
def get_or_create_nodo(graph, id, x, y):
	if (11, id) in graph.nodi:
		return graph.nodi[(11, id)]
	n = NodoTomTom(id, x, y)
	graph.add_nodo(n)
	return n

reset_count = [0]

def get_ztl(x, y):
	p = Point(x, y, srid=3004)
	zs = Multipoligono.objects.filter(geom__contains=p, parent_type=model2contenttype(ZTL))
	reset_count[0] += 1
	if reset_count[0] == 100:
		reset_count[0] = 0
		db.reset_queries()
	return set([ZTL.objects.get(pk=z.parent_id).codice for z in zs])


def load_restrictions(file_name):
	# VT:
	# 11: Veicoli privati
	# 12: Veicoli residenziali, per esempio ZTL
	# 17: Bus

	# DIR_POS:
	# 1: Both
	# 2: Positive
	# 3: Negative
	dirs = {
		1: (True, True),
		2: (True, False),
		3: (False, True),
	}
	chrono()
	print "Loading traffic restrictions"
	dbf = Dbf()
	dbf.openFile(file_name)
	rs = {}
	for row in dbf:
		if row['RESTRTYP'] != 'LY' or row['FEATTYP'] != 4110:
			continue
		id = row['ID']
		vt = int(row['VT'])
		if vt in {11, 12, 17}:
			if not id in rs:
				rs[id] = {}
			rs[id][vt] = dirs[row['DIR_POS']]
	chrono()
	return rs

def load_from_shp(grafo, file_name, restrictions):
	chrono()
	print "Reading shapefile"
	sr = shapereader.ShapeReader(file_name)
	chrono()
	print "Building graph"
	for e in sr:
		punti, attr = e
		eid = attr['ID']
		sid = attr['F_JNCTID']
		tid = attr['T_JNCTID']
		lunghezza = attr['METERS']
		nome = attr['NAME'].decode('iso-8859-1')
		verso = attr['ONEWAY']
		velocita = attr['KPH']
		tipo = attr['FRC']
		if tipo != -1 and attr['FEATTYP'] == 4110:
			punti = [wgs84_to_gbfe(*p) for p in punti]
			ps = punti[0]
			pt = punti[-1]
			s = get_or_create_nodo(grafo, sid, *ps)
			t = get_or_create_nodo(grafo, tid, *pt)
			ztl = get_ztl(*ps)
			ztl.update(get_ztl(*pt))
			fw = True
			bw = True
			tpl = False
			if verso == 'N':
				fw = False
				bw = False
				if eid in restrictions:
					rest = restrictions[eid]
					if 11 in rest:
						fw, bw = rest[11]
					elif 12 in rest:
						fw, bw = rest[12]
					elif 17 in rest:
						fw, bw = rest[17]
						tpl = True
			elif verso == 'FT':
				bw = False
			elif verso == 'TF':
				fw = False
			e1 = ArcoTomTom(
				eid,
				0,
				s,
				t,
				nome,
				fw,
				velocita,
				lunghezza,
				punti,
				tipo,
				ztl,
				tpl=tpl
			)
			e2 = ArcoTomTom(
				eid,
				1,
				t,
				s,
				nome,
				bw,
				velocita,
				lunghezza,
				list(reversed(punti)),
				tipo,
				ztl,
				tpl=tpl
			)
			grafo.add_arco(e1)
			grafo.add_arco(e2)
	print "Graph built"
	chrono()


chrono_old = None
def chrono():
	global chrono_old
	now = datetime.now()
	if chrono_old is not None:
		print "Elapsed: %s" % (str(now - chrono_old),)
	chrono_old = now
	
id_via_ostiense = (11, 13800207392955L)
id_via_vasi_old = (11, 13800207577174L)
id_via_vasi = (11, 13800205535178L)
id_raggiungibilita_osm = (11, 306048898) #(11, 246164532)

def prepara_autocompletamento(cancella=False):
	if cancella:
		IndirizzoAutocompl.objects.all().delete()
	with transaction():
		for i in streets.s:
			IndirizzoAutocompl.objects.get_or_create(indirizzo=i)

def shapefile_to_pickle(retina=False):
	g = Grafo()
	#rest = load_restrictions('C:\\Users\\allulll\\Desktop\\grafo\\cpd\\RM_rs.dbf')
	rest = load_restrictions('paline/tomtom/RM_rs.dbf')
	# rest = {}
	#load_from_shp(g, 'C:\\Users\\allulll\\Desktop\\grafo\\cpd\\RM_nw%s' % ('_mini' if retina else ''), rest)
	load_from_shp(g, 'paline/tomtom/RM_nw%s' % ('_mini' if retina else ''), rest)
	raggiungibilita.rendi_fortemente_connesso(g,  id_via_vasi_old if retina else id_via_vasi)
	g.serialize('tomtom%s.v3.dat' % ('_mini' if retina else ''))
	
	
def test(retina=False):
	g = Grafo()
	load_from_shp(g, 'C:\\Users\\allulll\\Desktop\\grafo\\cpd\\RM_nw%s' % ('_mini' if retina else ''))
	return g

# Compatibilità OSM
# Map: osm_type: (tomtom_type, max_speed, car)
osm_type_map = {
	'motorway': (0, 130, True),
	'motorway_link': (8, 40, True),
	'trunk': (1, 110, True),
	'trunk_link': (8, 40, True),
	'primary': (2, 90, True),
	'primary_link': (8, 40, True),
	'secondary': (3, 70, True),
	'secondary_link': (8, 40, True),
	'tertiary': (4, 60, True),
	'tertiary_link': (8, 40, True),
	'unclassified': (5, 50, True),
	'road': (6, 40, True),
	'residential': (6, 40, True),
	'living_street': (7, 30, True),
	'service': (8, 10, True),
	# Pedestrian only
	'steps': (8, 1, False),
	'track': (8, 5, False),
	'path': (8, 5, False),
	'footway': (8, 5, False),
	'bridleway': (8, 5, False),
	'byway': (8, 5, False),
	'pedestrian': (8, 5, False),
}


def parse_osm(graph, mini=False):
	dupn = 0
	dupe = 0
	if mini:
		rows = 16
		path = "paline/osm/small/map-%d.osm"
	else:
		rows = 45
		path = "paline/osm/map-%d.osm"		
	
	for i_for in range(1, rows + 1):
		print "Parsing tree: i=%d" % i_for
		tree = ET.parse(path % i_for)
		print "Done"
		
		print "Loading map"
		root = tree.getroot()
		
		for k in root:
			if k.tag == 'node':
				id = int(k.attrib['id'])
				if (11, id) in graph.nodi:
					dupn += 1
				else:
					lat = float(k.attrib['lat'])
					lon = float(k.attrib['lon'])
					x, y = wgs84_to_gbfe(lon, lat)
					ts = False
					"""
					for i in k:
						if i.tag == 'tag' and i.attrib['k'] == 'highway' and i.attrib['v'] == 'traffic_signals':
							ts = True
					"""
					n = NodoTomTom(id, x, y)
					graph.add_nodo(n)
			elif k.tag == 'way':
				eid = int(k.attrib['id'])
				if (12, eid, 0) in graph.archi:
					dupe += 1
				else:
					s = None
					name = ""
					forward = True
					backward = True
					hw = ""
					for i in k:
						if i.tag == 'tag' and i.attrib['k'] == 'name':
							name = i.attrib['v']
						elif i.tag == 'tag' and i.attrib['k'] == 'oneway':
							dir = i.attrib['v']
							if dir == 'yes' or dir == 'true' or dir == '1':
								backward = False
							elif dir == '-1':
								forward = False
						elif i.tag == 'tag' and i.attrib['k'] == 'highway':
							hw = i.attrib['v']					
					if hw in osm_type_map:
						count = 0
						for i in k:
							if i.tag == 'nd':
								t = graph.nodi[(11, int(i.attrib['ref']))]
								if s is not None:
									ps = s.get_coordinate()[0]
									pt = t.get_coordinate()[0]
									punti = [ps, pt]
									lunghezza = geomath.distance(ps, pt)
									
									tipo, velocita, auto = osm_type_map[hw]
									
									e = ArcoTomTom(  #eid, count, s, t, name, hw, ftype)	
										eid,
										count,
										s,
										t,
										name,
										forward and auto,
										velocita,
										lunghezza,
										punti,
										tipo,
										set(), # Oppure determinare le ZTL
										tpl=False, # Oppure determinare se corsia preferenziala
									)
									count += 1
									graph.add_arco(e)
									punti = [pt, ps]
									e = ArcoTomTom( #eid, count, t, s, name, hw, btype)
										eid,
										count,
										t,
										s,
										name,
										backward and auto,
										velocita,
										lunghezza,
										punti,
										tipo,
										set(), # Oppure determinare le ZTL
										tpl=False, # Oppure determinare se corsia preferenziala
									)
									count += 1
									graph.add_arco(e)
								s = t
			print "Done: %d nodes (%d duplicates), %d edges (%d duplicates)" % (len(graph.nodi), dupn, len(graph.archi), dupe)


def osm_to_pickle(retina=False):
	g = Grafo()
	parse_osm(g, retina)
	raggiungibilita.rendi_fortemente_connesso(g,  id_raggiungibilita_osm)
	g.serialize('osm%s.v3.dat' % ('_mini' if retina else ''))
	
