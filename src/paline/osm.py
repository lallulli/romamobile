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
import urllib
import urllib2
import traceback
#from shapely.geometry import LineString, Point, MultiPoint
#from IPython.Shell import IPShellEmbed
import codecs
from grafo import Nodo, Arco, Grafo
from geomath import wgs84_to_gbfe
#import raggiungibilita

from xml.etree import ElementTree as ET
#import cPickle as pickle
#import dijkstra
import geomath
#from globals import glb
from tratto import TrattoRoot, TrattoPiedi, TrattoPiediArco, TrattoBici, TrattoBiciArco
from tratto import TrattoAuto, TrattoAutoArco
from copy import copy

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

highways = Repository()
streets = Repository()

speed = {
		types['car']: {
				highways['motorway']: 80,
				highways['motorway_link']: 35,
				highways['trunk']: 60,
				highways['trunk_link']: 30,
				highways['primary']: 45,
				highways['primary_link']: 15,
				highways['secondary']: 32,
				highways['secondary_link']: 14,
				highways['tertiary']: 22,
				highways['unclassified']: 15,
				highways['road']: 15,
				highways['residential']: 13,
				highways['living_street']: 9,
				highways['service']: 1,
				#'': 20,
		},
		types['walk']: {
				highways['trunk']: 0.5,
				highways['trunk_link']: 0.5,
				highways['primary']: 4,
				highways['primary_link']: 2,
				highways['secondary']: 4,
				highways['secondary_link']: 2,
				highways['tertiary']: 4,
				highways['unclassified']: 4,
				highways['road']: 4,
				highways['residential']: 4,
				highways['living_street']: 4,
				highways['service']: 4,
				highways['steps']: 1.5,
				highways['track']: 3.5,
				highways['path']: 2.5,
				highways['footway']: 4,
				highways['bridleway']: 3,
				highways['byway']: 3,
				highways['pedestrian']: 4,
				#'': 20,
		},
	}

pedestrian_highways = [
	'footway',
	'path',
	'pedestrian',
	'primary',
	'primary_link',
	'road',
	'secondary',
	'secondary_link',
	'steps',
	'tertiary',
	'tertiary_link',
	'track',
	'unclassified',
	'residential',
]


class NodoOsm(Nodo):
	def __init__(self, id, x, y, traffic_signals = False):
		Nodo.__init__(self, (11, id))
		self.x = x
		self.y = y
		self.ts = traffic_signals
		
	def __unicode__(self):
		return self.id
	
	def save(self, f):
		f.write("%d\n" % (self.id[1],))
		f.write("%f\n" % (self.x,))
		f.write("%f\n" % (self.y,))
		f.write("%d\n" % (self.ts,))
		
	def get_coordinate(self):
		return [(self.x, self.y)]
	
	def aggiorna_contesto(self, dijkstra, rev=False):
		self.dijkstra = dijkstra
		e = self.pred
		if e is not None:
			self.context_i = e.s.context_i
			context = self.dijkstra.context[self.context_i]
			if e.id[0] != 12 and context['primo_tratto_bici']:
				self.context_i = dijkstra.copy_context(self.context_i)
				self.dijkstra.context[self.context_i]['primo_tratto_bici'] = False
			elif context['primo_tratto_bici']:
				self.context_i = dijkstra.copy_context(self.context_i)
				context = self.dijkstra.context[self.context_i]
				d = context['max_distanza_bici']  
				d -= e.get_distanza()
				if d < 0:
					d = 0
					context['primo_tratto_bici'] = False
				context['max_distanza_bici'] = d
				if e.get_nome() != '':
					context['nome_strada'] = e.name
					
	@classmethod
	def load(cls, grafo, f):
		n = NodoOsm(
				int(f.readline().strip()),
				float(f.readline().strip()),
				float(f.readline().strip()),
				bool(int(f.readline().strip()))
			)
		grafo.add_nodo(n)
		
	def init_percorso(self, opzioni, tr=None):
		"""
		Inizializza il sistema di rappresentazione dei percorsi a partire da questo nodo.
		
		Restituisce una coppia: il tratto radice e il tratto corrente
		"""
		if tr is None:
			tr = TrattoRoot(self.time)
		if opzioni['primo_tratto_bici']:
			t = TrattoBici(tr, self.time)
		elif opzioni['auto']:
			t = TrattoAuto(tr, self.time)
		else:
			t = TrattoPiedi(tr, self.time)
		return (tr, t)
	
		
class ArcoOsm(Arco):
	def __init__(self, eid, count, s, t, name, hw, type):
		Arco.__init__(self, s, t, (12, eid, count))
		self.name = streets[name]
		self.hw = highways[hw]
		self.w = geomath.distance_proj(s.x, s.y, t.x, t.y)
		self.type = type
		#print "hw:", hw, self.hw
		
	def get_nome(self):
		return streets.inverse_search(self.name)
	
	def attraversabile_vicini(self, opzioni):
		return True	

	def get_distanza(self):
		return self.w

	def save(self, f):
		f.write("%d\n" % (self.id[1],))
		f.write("%d\n" % (self.id[2],))		
		f.write("%d\n" % (self.s.id[1],))
		f.write("%d\n" % (self.t.id[1],))
		ise = streets.inverse_search(self.name)
		f.write("%s\n" % ise.encode('utf-8'))
		f.write("%s\n" % (highways.inverse_search(self.hw),))
		f.write("%d\n" % self.type)
		
	@classmethod
	def load(cls, grafo, f):
		eid = int(f.readline().strip())
		count = int(f.readline().strip())		
		s = grafo.nodi[(11, int(f.readline().strip()))]
		t = grafo.nodi[(11, int(f.readline().strip()))]
		name = f.readline().strip()
		hw = f.readline().strip()
		type = int(f.readline().strip())
		e = ArcoOsm(
				eid,
				count,
				s,
				t,
				name,
				hw,
				type
			)
		grafo.add_arco(e)
	
	"""
	def split(self, node, graph):
		"
		Split an edge in two
		
		node: the new internal point
		"
		t = self.t
		es = graph.edges[self.eid]
		self.t = n
		self.w = geomath.distance(s.lat, s.lon, n.lat, n.lon)		
		e2 = Edge(self.eid, n, self.t, streets.inverse_search(self.name), highways.inverse_search(self.hw), self.type)
		es.append(e2)
		n.adj.append(e2)
	"""
	
	def get_coordinate(self):
		"""
		Restituisce una lista di coppie: le coordinate dei punti. Oppure None
		"""				
		return [(self.s.x, self.s.y), (self.t.x, self.t.y)]
	
	def get_tempo(self, t, opz):
		if opz['auto']:
			s = speed[types['car']]
			if self.hw in s and (self.type & types['car']):
				tempo = 3.6 * self.w / s[self.hw]
			else:
				tempo = -1
			return (tempo, tempo)
		else:
			context = self.s.dijkstra.context[self.s.context_i]
			if context['primo_tratto_bici'] and context['max_distanza_bici'] - self.get_distanza() > 0:
				if self.type & types['car']:
					n = self.get_nome()
					cambio_strada = 1 if (n != '' and self.name != context['nome_strada']) else 0
					tempo = 3.6 * self.w / opz['v_bici'] + cambio_strada * opz['t_bici_cambio_strada']
					return (tempo, tempo)
				return (-1, -1)
			if self.type & types['walk']:
				tempo = 3.6 * self.w / opz['v_piedi']
				return (tempo * opz['coeff_penal_pedonale'], tempo)
			return (-1, -1)
		
	def costruisci_percorso(self, t, opzioni):
		if opzioni['auto']:
			TrattoAutoArco(t, self.s.time, self, 3.6 * self.w / speed[types['car']][self.hw])
		elif not self.s.dijkstra.context[self.s.context_i]['primo_tratto_bici']:
			if type(t) != TrattoPiedi:
				t = TrattoPiedi(t.parent, self.s.time)
			TrattoPiediArco(t, self.s.time, self, 3.6 * self.w / opzioni['v_piedi'])
		elif self.t.dijkstra.context[self.t.context_i]['primo_tratto_bici']:
			TrattoBiciArco(t, self.s.time, self, 3.6 * self.w / opzioni['v_bici'])
		else:
			t = TrattoPiedi(t.parent, self.s.time)
			TrattoBiciArco(t, self.s.time, self, 3.6 * self.w / opzioni['v_bici'])
		return t


def save_graph(grafo, file_name):
	print "Saving graph in proprietary format..."
	f = open(file_name, "w")
	f.write("%d\n" % (len(grafo.nodi),))
	for n in grafo.nodi:
		grafo.nodi[n].save(f)
	f.write("%d\n" % (len(grafo.archi),))
	for e in grafo.archi:
		grafo.archi[e].save(f)
	f.close()
	print "Done"
	
def load_graph(grafo, file_name):
	print "Loading graph from proprietary format..."
	f = codecs.open(file_name, "r", 'utf-8')
	l = int(f.readline().strip())
	for i in xrange(0, l):
		NodoOsm.load(grafo, f)
	l = int(f.readline().strip())
	for i in xrange(0, l):
		ArcoOsm.load(grafo, f)
	f.close()
	print "Done"


		

def parse_osm(graph, rows):

	dupn = 0
	dupe = 0
	
	for i_for in range(1, rows + 1):
		print "Parsing tree: i=%d" % i_for
		tree = ET.parse("paline/osm/map-%d.osm" % i_for)
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
					for i in k:
						if i.tag == 'tag' and i.attrib['k'] == 'highway' and i.attrib['v'] == 'traffic_signals':
							ts = True
					n = NodoOsm(id, x, y, ts)
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
					if hw in pedestrian_highways:
						count = 0
						for i in k:
							if i.tag == 'nd':
								t = graph.nodi[(11, int(i.attrib['ref']))]
								if s is not None:
									ftype = types['walk']
									if forward:
										ftype = ftype | types['car']
									e = ArcoOsm(eid, count, s, t, name, hw, ftype)
									count += 1
									graph.add_arco(e)			
									btype = types['walk']
									if backward:
										btype = btype | types['car']
									e = ArcoOsm(eid, count, t, s, name, hw, btype)
									count += 1
									graph.add_arco(e)
								s = t
			print "Done: %d nodes (%d duplicates), %d edges (%d duplicates)" % (len(graph.nodi), dupn, len(graph.archi), dupe)


def retrieve(left, bottom, right, top, rows, columns, start=1):
	height = (top - bottom) / rows
	width = (right - left) / columns
	for i in xrange(0, rows):
		for j in xrange(0, columns):
			print "i=%d, j=%d" % (i, j)
			s = bottom + i * height
			n = s + height
			w = left + j * width
			e = w + width
			start = retrieve2(w, s, e, n, start)
	return start
	

def retrieve2(left, bottom, right, top, start=0):
	try:
		f = open("map-%d.osm" % start, "w")
		print "i=%d" % start
		url = "http://api.openstreetmap.org/api/0.6/map?bbox=%f,%f,%f,%f" % (left, bottom, right, top)
		print url
		u = urllib2.urlopen(url)
		f.write(u.read())
		f.close()
		u.close()
		return start + 1
	except Exception, e:
		print "Exception, recurring"
		traceback.print_exc()
		f.close()
		return retrieve(left, bottom, right, top, 2, 2, start)
	

	
chrono_old = None
def chrono():
	global chrono_old
	now = datetime.datetime.now()
	if chrono_old is not None:
		print "Elapsed: %s" % (str(now - chrono_old),)
	chrono_old = now
	


def main_retrieve():
	#ipshell = IPShellEmbed()
	chrono()
	retrieve(12.2, 41.7, 12.7, 42.0, 6, 6) # large
	#retrieve(12.42, 41.85, 12.55, 41.95, 4, 4) # small
	#g = Graph()
	#g.parse_osm(16) #36
	#g.load("map.dat")
	chrono()
	#g.save("c:/documents and settings/allulll/Desktop/map.dat")
	#test_segment_repo(g)
	chrono()
	#ipshell()
	
def main_convert():
	#ipshell = IPShellEmbed()
	chrono()
	#retrieve(12.2, 41.7, 12.7, 42.0, 6, 6) # large
	#retrieve(12.42, 41.85, 12.55, 41.95, 4, 4) # small
	g = Grafo()
	parse_osm(g, 45) #36
	#g.load("map.dat")
	chrono()
	save_graph(g, "c:/documents and settings/allulll/Desktop/osm-con-dup.dat")	
	#load_graph(g, "c:/documents and settings/allulll/Desktop/osm-con-dup.dat")
	chrono()
	raggiungibilita.rendi_fortemente_connesso(g)
	chrono()
	save_graph(g, "c:/documents and settings/allulll/Desktop/osm-nodup.dat")
	#test_segment_repo(g)
	chrono()
	#ipshell()
	
def main_parse_only():
	g = Grafo()
	parse_osm(g, 16)
	
