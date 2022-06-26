# coding: utf-8
# cython: profile=False

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



from copy import copy
from datetime import datetime, timedelta
import time
import tratto
import cPickle as pickle
cimport cython
from Queue import Queue
from contextlib import contextmanager
from threading import Lock
from pprint import pprint
from geomath import distance
"""
Classi per rappresentare un grafo astratto

1. Derivare le classi Nodo e Arco
2. Creare un Grafo
3. Creare direttamente i nodi e gli archi, e aggiungerli al grafo

"""

lock = Lock()

auto_id_cnt = [0]
def get_auto_id():
	auto_id_cnt[0] -= 1
	return auto_id_cnt

cdef class DijkstraVars(object):
	cdef short settled
	cdef object custom
	cdef object pred
	cdef object next
	cdef double dist
	cdef long pqi
	cdef double prio
	cdef double heu
	cpdef long versione_cp
	cpdef object time
	cdef long context_i
	
	def __init__(self):
		object.__init__(self)
		self.reset()
	
	cpdef reset(self):
		self.settled = False
		self.pred = None
		self.next = None
		self.dist = -1
		self.time = -1
		self.versione_cp = 0
		self.context_i = 0
		self.heu = -1
		
	property time:
		def __get__(self):
			return self.time
		def __set__(self, value):
			self.time = value
			
	property dist:
		def __get__(self):
			return self.dist
		def __set__(self, value):
			self.dist = value
			
	property versione_cp:
		def __get__(self):
			return self.versione_cp
		def __set__(self, value):
			self.versione_cp = value
			
	property custom:
		def __get__(self):
			return self.custom
		def __set__(self, value):
			self.custom = value
			
	property pred:
		def __get__(self):
			return self.pred
		def __set__(self, value):
			self.pred = value
			
	property next:
		def __get__(self):
			return self.next
		def __set__(self, value):
			self.next = value			
			
	property context_i:
		def __get__(self):
			return self.context_i
		def __set__(self, value):
			self.context_i = value
			
	cpdef get_distanza(self):
		return self.dist
		

cdef class NodoDijkstra(object):
	"""
	Mixin che fornisce le funzionalità necessarie per Dijkstra.
	
	Separato da Nodo semplicemente per maggiore pulizia
	"""
	cdef long dijkstra_index

	property dijkstra_index:
		def __get__(self):
			return self.dijkstra_index
		def __set__(self, value):
			self.dijkstra_index = value
			
	

	def get_coordinate(self):
		"""
		Restituisce una lista con un unico elemento, una coppia con le coordinate del punto, oppure None
		"""
		return None
	
	def costruisci_percorso(self, tratto, opzioni):
		"""
		Metodo invocato per costruire il percorso.
		
		Riceve in input un tratto di percorso, e ne restituisce un altro.
		Il tratto restituito può essere un sottotoratto, il tratto stesso, o il tratto padre.
		"""
		return tratto
	
	def init_percorso(self, opzioni, tr=None):
		"""
		Inizializza il sistema di rappresentazione dei percorsi a partire da questo nodo.
		
		Restituisce una coppia: il tratto radice e il tratto corrente
		"""
		vars = self.get_vars(opzioni)
		if tr is None:
			tr = tratto.TrattoRoot(vars.time)
		if opzioni['primo_tratto_bici']:
			t = tratto.TrattoBici(tr, vars.time)
		elif opzioni['auto']:
			t = tratto.TrattoAuto(tr, vars.time)
		else:
			t = tratto.TrattoPiedi(tr, vars.time)
		return (tr, t)
	
class NodoCercaVicini(object):
	def aggiorna_risultati_vicini(self, risultati, opt):
		pass
	
	def risultati_vicini(self, opt):
		return False

class ArcoCercaVicini(object):
	def attraversabile_vicini(self, opzioni):
		return False

class Nodo(NodoDijkstra, NodoCercaVicini):
	def __init__(self, id=None):
		NodoDijkstra.__init__(self)
		self.fstar = []
		self.bstar = []

		if id is None:
			id = get_auto_id()
		self.id = id
		
	def add_outgoing(self, e):
		"""
		Chiamato da Arco
		"""
		self.fstar.append(e)

	def add_incoming(self, e):
		"""
		Chiamato da Arco
		"""
		self.bstar.append(e)
		
	def get_vars(self, opt):
		dijkstra = opt['dijkstra']
		return dijkstra.vars[self.dijkstra_index]
		
	def get_context(self, opt):
		"""
		Restituisce il contesto del nodo
		"""		
		dijkstra = opt['dijkstra']
		return dijkstra.context[dijkstra.vars[self.dijkstra_index].context_i]	

		
class ArcoDijkstra(object):
	"""
	Mixin che fornisce le funzionalità necessarie per Dijkstra.
	
	Separato da Arco semplicemente per maggiore pulizia
	"""	
	def get_coordinate(self):
		"""
		Restituisce una lista di coppie: le coordinate dei punti. Oppure None
		"""				
		return None
		
	def costruisci_percorso(self, tratto, opzioni):
		"""
		Metodo invocato per costruire il percorso.
		
		Riceve in input un tratto di percorso, e ne restituisce un altro.
		Il tratto restituito può essere un sottotoratto, il tratto stesso, o il tratto padre.
		"""
		return tratto
	
	def get_distanza(self):
		return 0
	
	def aggiorna_contesto(self, opt, rev=False):
		pass
	
	def duplica_contesto(self, opt, rev=False):
		"""
		Crea sul nodo t una copia del contesto del nodo s, e restituisce tale contesto
		"""
		dijkstra = opt['dijkstra']
		if not rev:
			context_i = dijkstra.vars[self.s.dijkstra_index].context_i 
			context_j = dijkstra.copy_context(context_i)
			dijkstra.vars[self.t.dijkstra_index].context_i = context_j
		else:
			context_i = dijkstra.vars[self.t.dijkstra_index].context_i 
			context_j = dijkstra.copy_context(context_i)
			dijkstra.vars[self.s.dijkstra_index].context_i = context_j
		return dijkstra.context[context_j]
		


class Arco(ArcoDijkstra, ArcoCercaVicini):
	def __init__(self, s, t, id=None):
		ArcoDijkstra.__init__(self)
		self.s = s
		self.t = t
		s.add_outgoing(self)
		t.add_incoming(self)
		if id is None:
			id = get_auto_id()		
		self.id = id
		
	def get_tempo(self, t, opt):
		return (0, 0)
	

class GrafoDijkstra(object):
	def reset(self):
		for id in self.nodi:
			self.nodi[id].reset()


class Grafo(GrafoDijkstra):
	def __init__(self):
		self.nodi = {}
		self.archi = {}
		self.tipi_nodi = {}
		self.tipi_archi = {}
		
	def add_nodo(self, n):
		self.nodi[n.id] = n
		
	def add_arco(self, e):
		self.archi[e.id] = e
		
	def rm_nodo(self, n):
		"""
		Rimuove un nodo dal grafo
		"""
		archi = set(n.fstar).union(set(n.bstar))
		for e in archi:
			self.rm_arco(e)
		del self.nodi[n.id]
	
	def rm_arco(self, e):
		"""
		Rimuove un arco dal grafo
		
		Il metodo aggiorna le liste di adiacenza degli estremi dell'arco
		"""
		e.s.fstar.remove(e)
		e.t.bstar.remove(e)
		del self.archi[e.id]
		
	def registra_tipo_archi(self, classe):
		self.tipi_archi[classe.tipo_archi] = classe
		
	def registra_tipo_nodi(self, classe):
		self.tipi_nodi[classe.tipo_nodi] = classe		

	def serialize(self, filename, classi_archi=None, classi_nodi=None):
		grafo = self
		print "Saving graph in proprietary format..."
		nodi = []
		for n in grafo.nodi:
			nodo = grafo.nodi[n]
			if classi_nodi is None or nodo.__class__ in classi_nodi:
				nodi.append(nodo.serialize())
		archi = []
		for a in grafo.archi:
			arco = grafo.archi[a]
			if classi_archi is None or arco.__class__ in classi_archi:
				archi.append(arco.serialize())
		print "Saving"
		f = open(filename, 'wb')
		f.write(pickle.dumps({
			'nodi': nodi,
			'archi': archi,
		}, 2)	)
		f.close()
		print "Done"

		
	def deserialize(self, filename, classi_archi=None, classi_nodi=None):
		grafo = self
		print "Loading graph from proprietary file..."
		f = open(filename, 'rb')
		res = pickle.loads(f.read())
		f.close()
		print "Deserializing graph..."
		for n in res['nodi']:
			c = self.tipi_nodi[n['id'][0]]
			if classi_nodi is None or c in classi_nodi:
				c.deserialize(grafo, n)
		for a in res['archi']:
			c = self.tipi_archi[a['id'][0]]
			if classi_archi is None or c in classi_archi:			
				c.deserialize(grafo, a)


cdef extern from "stdlib.h":
	void free(void* ptr)
	void* malloc(size_t size)
	void* realloc(void* ptr, size_t size)


opzioni_cp = {
	'metro': True,
	'bus': True,
	'fc': True,
	'fr': True,
	'v_piedi': [2, 4.4, 5.2][2],
	't_sal_bus': 30,
	't_disc_bus': 20,
	't_sal_metro': 140,
	't_disc_metro': 120,
	't_sal_fc': 140,
	't_disc_fc': 120,	
	'indici_stat': [],
	'penalizzazione_bus': 60,
	'penalizzazione_metro': 0,
	'penalizzazione_fc': 0,
	'auto': False,
	'car_pooling': False,
	'utente': -1,	
	'primo_tratto_bici': False,
	'giorno': 1,
	'wd_giorno': 0,
	'wd_giorno_succ': 0,
	'penal_pedonale_0': 1.6,
	'penal_pedonale_1': 2.5,
	'penal_pedonale_exp': 0.85,
	'heuristic_speed': 0,
}

context_cp = {
	'primo_tratto_bici': False,
	'max_distanza_bici': 5.0,
	'nome_strada': -1,
	'carpooling_usato': -1,
	'distanza_piedi': 0.0,
}


class ArcoIngresso(Arco):
	count = 0
	def __init__(self, dijkstra_pool, source):
		ArcoIngresso.count += 1
		id = (0, ArcoIngresso.count)
		s = Nodo(id)
		Arco.__init__(self, s, source, id)
		dijkstra_pool.add_nodo(self.s)
		dijkstra_pool.add_arco(self)
		
	def aggiorna_contesto(self, opt, rev=False):
		pass
	
class ArcoUscita(Arco):
	count = 0
	def __init__(self, dijkstra_pool, target):
		ArcoIngresso.count += 1
		id = (0, ArcoIngresso.count)
		t = Nodo(id)
		Arco.__init__(self, target, t, id)
		dijkstra_pool.add_nodo(self.t)
		dijkstra_pool.add_arco(self)
		
	def aggiorna_contesto(self, opt, rev=False):
		pass
	

cdef class PQ(object):
	# Nota: la pq è ottimizzata per l'uso (calcola percorso), e consente al più n inserimenti
	#cdef object a
	cdef long len
	# array delle priorità
	cdef double* p
	# array degli indici dei nodi (associato all'array delle priorità)
	cdef long* n
	# lista dei nodi
	cdef object nl
	# array degli indici delle priorità dei nodi (associata alla lista dei nodi)
	cdef long* pl
	# contatore degli elementi di nl usati, i.e., contatore dei nodi inseriti complessivamente
	cdef long nli

	def __init__(self, n):
		object.__init__(self)
		self.p = <double*> malloc(n * sizeof(double))
		self.n = <long*> malloc(n * sizeof(long))
		self.nl = [None for x in range(0, n)]
		self.pl = <long*> malloc(n * sizeof(long))
		self.len = 0
		self.nli = 0

	@cython.profile(False)
	cdef void _swap(self, long i, long j) nogil:
		self.p[j], self.p[i] = self.p[i], self.p[j]
		self.n[j], self.n[i] = self.n[i], self.n[j]
		self.pl[self.n[i]] = i
		self.pl[self.n[j]] = j

	@cython.profile(False)
	cdef void _move_down(self, long i) nogil:
		cdef long c
		if i > 0:
			c = i / 2
			if self.p[c] > self.p[i]:
				self._swap(c, i)
				self._move_down(c)
					
	@cython.profile(False)
	cdef void _move_up(self, long i) nogil:
		cdef long n = self.len
		cdef long i1 = 2 * i
		cdef long i2 = i1 + 1
		if i1 < n:
			if i2 == n:
				if self.p[i] > self.p[i1]: 
					self._swap(i, i1)
			else:
				if self.p[i] > self.p[i1] or self.p[i] > self.p[i2]: 
					if self.p[i1] < self.p[i2]:
						self._swap(i, i1)
						self._move_up(i1)
					else:
						self._swap(i, i2)
						self._move_up(i2)
	
	@cython.profile(False)
	cpdef insert(self, NodoDijkstra v, DijkstraVars vv, double p):
		cdef long i = self.len
		cdef long j = self.nli
		self.nli += 1
		self.nl[j] = v
		self.pl[j] = i
		vv.pqi = j
		self.p[i] = p
		self.n[i] = j
		self.len += 1
		with nogil:
			self._move_down(i)
		
	@cython.profile(False)
	cpdef decrease_key(self, DijkstraVars vv, double p):
		cdef long i = self.pl[vv.pqi]
		self.p[i] = p
		with nogil:
			self._move_down(i)

	@cython.profile(False)
	cpdef NodoDijkstra delete_min(self):
		cdef NodoDijkstra m = <NodoDijkstra>(self.nl[self.n[0]])
		cdef long n
		with nogil:
			n = self.len
			self._swap(0, n - 1)
			self.len -= 1
			self._move_up(0)
		return m
	
	@cython.profile(False)
	cpdef double get_min_priority(self):
		return self.p[0]

	@cython.profile(False)
	cpdef int is_empty(self):
		return self.len == 0
	
	cpdef cleanup(self):
		self.len = 0
		self.nli = 0

"""
@cython.profile(False)
cpdef inline double datetime_to_double(dt):
	return dt.year * 980294400 + dt.month * 2678400 + dt.day * 86400 + dt.hour * 3600 + dt.minute * 60 + dt.second
"""


cdef class Dijkstra(object):
	cdef object graph
	cdef PQ pq
	cdef long versione_cp
	# Array dei contesti dei nodi
	cdef object context
	# Array dei dati associati ai nodi per il cerca percorso
	cdef object vars
	cdef long context_i
	cdef object pool
	
	property context:
		def __get__(self):
			return self.context
		def __set__(self, value):
			self.context = value
			
	property vars:
		def __get__(self):
			return self.vars
		def __set__(self, value):
			self.vars = value			
	
	def __init__(self, graph, dijkstra_pool):
		object.__init__(self)
		cdef long n = len(graph.nodi)
		self.graph = graph
		self.pool = dijkstra_pool
		n_aug = int(n * 1.5)
		self.pq = PQ(n_aug)
		self.versione_cp = 0
		self.context = [None for x in range(n_aug)]
		self.vars = [DijkstraVars() for x in range(n_aug)]

	
	cpdef copy_context(self, long i):
		cdef long j = self.context_i
		if self.context[j] is None:
			self.context[j] = {}
		for k in self.context[i]:
			self.context[j][k] = self.context[i][k]
		self.context_i = j + 1
		return j
	
	def create_context(self):
		self.context[0] = {}
		self.context_i = 1
		return 0
		
	cdef cleanup(self):
		self.pq.cleanup()
		self.context_i = 1
		
	def genera_arco_ingresso(self, s):
		e = ArcoIngresso()
		self.vars[s]
	
	def rimuovi_arco_ingresso(self, e):
		pass


	cpdef heuristic(self, NodoDijkstra n, DijkstraVars nv, old_heu, double xd, double yd, double speed):
		# print "Heu", xd, yd
		if nv.heu == -1:
			c = n.get_coordinate()
			if c is None:
				nv.heu = old_heu
			else:
				nv.heu = distance(c[0], (xd, yd)) / speed
		# print nv.heu
		return nv.heu
		

	cpdef dijkstra(self, NodoDijkstra s, object targets, int complete=False, object dep_time=None, object opt=opzioni_cp, get_unreachable=False, s_context=context_cp):
		"""
		Find fastest route from s to all vertices in ts
		
		s: vertex
		targets: set of vertices
		return: dictionary with the form
			t: (time(s, t), d(s, t))
		"""
		cdef NodoDijkstra v, w
		cdef long cnt, remaining
		cdef double min_priority, new_prio, inc_prio, heuristic_speed
		self.cleanup()
		self.versione_cp += 1
		cdef long versione_cp = self.versione_cp
		opt['dijkstra'] = self
		opt['rev'] = False
		heuristic_speed = opt['heuristic_speed']
		vars = self.vars
		sv = <DijkstraVars>(vars[s.dijkstra_index])
		coord = list(targets)[0].get_coordinate()[0]
		xt, yt = coord
		sv.dist = self.heuristic(s, sv, -1, xt, yt, heuristic_speed)
		ai = ArcoIngresso(self.pool, s)
		aiv = <DijkstraVars>(vars[ai.s.dijkstra_index])
		aiv.context_i = 0
		self.context[0] = s_context
		sv.pred = ai
		sv.time = dep_time if dep_time is not None else datetime.now()
		sv.versione_cp = self.versione_cp
		self.pq.insert(s, sv, 0)
		cnt = 0
		ts = copy(targets)
		remaining = len(ts)
		out = {}
		while not self.pq.is_empty() and (remaining > 0 or complete):
			cnt += 1
			min_priority = self.pq.get_min_priority()
			v = self.pq.delete_min()
			vv = <DijkstraVars>(vars[v.dijkstra_index])
			pred = vv.pred
			old_heu = vv.heu
			w = <NodoDijkstra>(pred.s)
			wv = <DijkstraVars>(vars[w.dijkstra_index])
			vv.context_i = wv.context_i
			pred.aggiorna_contesto(opt)
			time = vv.time
			#print "Prio", min_priority
			#print "Time", time			
			#dist = v.dist
			vv.settled = True
			if v in ts:
				ts.remove(v)
				remaining -= 1
				out[v] = (vv.time, vv.dist)
			for e in v.fstar:
				w = <NodoDijkstra>(e.t)
				wv = <DijkstraVars>(vars[w.dijkstra_index])
				if wv.versione_cp != versione_cp:
					inc_prio, tempo_arco = e.get_tempo(time, opt)
					if inc_prio >= 0:
						#print "inc_prio nuovo nodo", inc_prio
						wv.versione_cp = versione_cp
						wv.pred = e
						wv.settled = False
						wv.heu = -1
						new_prio = min_priority - old_heu + self.heuristic(w, wv, old_heu, xt, yt, heuristic_speed) + inc_prio
						wv.prio = new_prio
						wv.time = time + timedelta(seconds=tempo_arco)
						self.pq.insert(w, wv, new_prio)
				elif not wv.settled:
					inc_prio, tempo_arco = e.get_tempo(time, opt)
					#print "inc_prio nodo esistente", inc_prio
					if tempo_arco >= 0:
						new_prio = min_priority - old_heu + self.heuristic(w, wv, old_heu, xt, yt, heuristic_speed) + inc_prio
						#new_dist = dist + e.w
						if new_prio < wv.prio:
							wv.prio = new_prio
							wv.time = time + timedelta(seconds=tempo_arco)
							#w.dist = new_dist
							wv.pred = e
							self.pq.decrease_key(wv, new_prio)
				
		sv.pred = None
		self.pool.rm_nodo(ai.s)
		
		print "Dijkstra done, %d nodes reached" % (cnt,)
		
		if get_unreachable:
			unr = set()
			for nid in self.graph.nodi:
				v = self.graph.nodi[nid]
				vv = <DijkstraVars>(vars[v.dijkstra_index])
				if vv.versione_cp != self.versione_cp:
					unr.add(v)
			return unr
			
		return out
	
	cpdef rev_dijkstra(self, NodoDijkstra t, object sources, int complete=False, object arr_time=None, object opt=opzioni_cp, get_unreachable=False, t_context=context_cp):
		"""
		Find fastest route from t to s
		
		s: vertex
		targets: set of vertices
		return: dictionary with the form
			t: (time(s, t), d(s, t))
		"""
		cdef NodoDijkstra v, w
		cdef long cnt, remaining
		cdef double min_priority, new_prio, inc_prio
		self.cleanup()
		self.versione_cp += 1
		cdef long versione_cp = self.versione_cp
		opt['dijkstra'] = self
		opt['rev'] = True
		vars = self.vars
		tv = <DijkstraVars>(vars[t.dijkstra_index])
		tv.dist = 0
		au = ArcoUscita(self.pool, t)
		auv = <DijkstraVars>(vars[au.t.dijkstra_index])
		auv.context_i = 0
		self.context[0] = t_context
		tv.next = au
		tv.time = arr_time if arr_time is not None else datetime.now()
		tv.versione_cp = self.versione_cp
		self.pq.insert(t, tv, 0)
		cnt = 0
		ss = copy(sources)
		remaining = len(ss)
		out = {}
		while not self.pq.is_empty() and (remaining > 0 or complete):
			cnt += 1
			min_priority = self.pq.get_min_priority()
			v = self.pq.delete_min()
			vv = <DijkstraVars>(vars[v.dijkstra_index])
			next = vv.next
			w = <NodoDijkstra>(next.t)
			wv = <DijkstraVars>(vars[w.dijkstra_index])
			vv.context_i = wv.context_i
			next.aggiorna_contesto(opt, rev=True)
			time = vv.time
			#print "Prio", min_priority
			#print "Time", time			
			#dist = v.dist
			vv.settled = True
			if v in ss:
				ss.remove(v)
				remaining -= 1
				out[v] = (vv.time, vv.dist)
			for e in v.bstar:
				w = <NodoDijkstra>(e.s)
				wv = <DijkstraVars>(vars[w.dijkstra_index])
				if wv.versione_cp != versione_cp:
					inc_prio, tempo_arco = e.get_tempo(time, opt)
					if inc_prio >= 0:
						#print "inc_prio nuovo nodo", inc_prio
						wv.versione_cp = versione_cp
						wv.next = e
						wv.settled = False
						new_prio = min_priority + inc_prio
						wv.prio = new_prio
						wv.time = time - timedelta(seconds=tempo_arco)
						self.pq.insert(w, wv, new_prio)
				elif not wv.settled:
					inc_prio, tempo_arco = e.get_tempo(time, opt)
					#print "inc_prio nodo esistente", inc_prio
					if tempo_arco >= 0:
						new_prio = min_priority + inc_prio
						#new_dist = dist + e.w
						if new_prio < wv.prio:
							wv.prio = new_prio
							wv.time = time - timedelta(seconds=tempo_arco)
							#w.dist = new_dist
							wv.next = e
							self.pq.decrease_key(wv, new_prio)
				
		tv.next = None
		self.pool.rm_nodo(au.t)
		
		print "Dijkstra done, %d nodes reached" % (cnt,)
		
		if get_unreachable:
			unr = set()
			for nid in self.graph.nodi:
				v = self.graph.nodi[nid]
				vv = <DijkstraVars>(vars[v.dijkstra_index])
				if vv.versione_cp != self.versione_cp:
					unr.add(v)
			return unr
			
		return out


	cpdef archi_vicini(self, NodoDijkstra s, double max_distanza, object dep_time=None, object opt=opzioni_cp, object s_context=context_cp):
		"""
		Return edges near to node s
		"""
		cdef NodoDijkstra v, w
		cdef long cnt
		cdef double min_priority, new_prio, inc_prio
		self.cleanup()
		self.versione_cp += 1
		cdef long versione_cp = self.versione_cp
		opt['dijkstra'] = self
		opt['rev'] = False
		vars = self.vars
		sv = <DijkstraVars>(vars[s.dijkstra_index])
		sv.dist = 0
		dist = 0
		ai = ArcoIngresso(self.pool, s)
		aiv = <DijkstraVars>(vars[ai.s.dijkstra_index])
		aiv.context_i = 0
		self.context[0] = s_context
		sv.pred = ai
		sv.time = dep_time if dep_time is not None else datetime.now()
		sv.versione_cp = self.versione_cp
		self.pq.insert(s, sv, 0)
		cnt = 0
		out = []
		while not self.pq.is_empty() and dist < max_distanza:
			cnt += 1
			min_priority = self.pq.get_min_priority()
			v = self.pq.delete_min()
			vv = <DijkstraVars>(vars[v.dijkstra_index])
			pred = vv.pred
			w = <NodoDijkstra>(pred.s)
			wv = <DijkstraVars>(vars[w.dijkstra_index])
			vv.context_i = wv.context_i
			# pprint(v.get_context(opt))
			pred.aggiorna_contesto(opt)
			time = vv.time
			#print "Prio", min_priority
			#print "Time", time
			dist = vv.dist
			vv.settled = True
			for e in v.fstar:
				if e.attraversabile_vicini(opt):
					out.append(e)
					w = <NodoDijkstra>(e.t)
					wv = <DijkstraVars>(vars[w.dijkstra_index])
					if wv.versione_cp != versione_cp:
						inc_prio, tempo_arco = e.get_tempo(time, opt)
						if inc_prio >= 0:
							#print "inc_prio nuovo nodo", inc_prio
							wv.versione_cp = versione_cp
							wv.pred = e
							wv.settled = False
							new_prio = min_priority + inc_prio
							wv.prio = new_prio
							wv.time = time + timedelta(seconds=tempo_arco)
							wv.dist = dist + e.get_distanza()
							self.pq.insert(w, wv, new_prio)
					elif not wv.settled:
						inc_prio, tempo_arco = e.get_tempo(time, opt)
						#print "inc_prio nodo esistente", inc_prio
						if tempo_arco >= 0:
							new_prio = min_priority + inc_prio
							if new_prio < wv.prio:
								wv.prio = new_prio
								wv.time = time + timedelta(seconds=tempo_arco)
								wv.dist = dist + e.get_distanza()
								wv.pred = e
								self.pq.decrease_key(wv, new_prio)

		sv.pred = None
		self.pool.rm_nodo(ai.s)

		# print "Dijkstra (near edges) done, %d nodes reached" % (cnt,)
		return out


	cpdef cerca_vicini(self, NodoDijkstra s, risultati, double max_distanza, object dep_time=None, object opt=opzioni_cp, object s_context=context_cp, short solo_pedonale=True):
		"""
		Find fastest route from s to all vertices in ts
		
		s: vertex
		targets: set of vertices
		return: dictionary with the form
			t: (time(s, t), d(s, t))
		"""
		cdef NodoDijkstra v, w
		cdef long cnt
		cdef double min_priority, new_prio, inc_prio
		self.cleanup()
		self.versione_cp += 1
		cdef long versione_cp = self.versione_cp
		opt['dijkstra'] = self
		opt['rev'] = False
		vars = self.vars
		sv = <DijkstraVars>(vars[s.dijkstra_index])
		sv.dist = 0
		dist = 0
		ai = ArcoIngresso(self.pool, s)
		aiv = <DijkstraVars>(vars[ai.s.dijkstra_index])
		aiv.context_i = 0
		self.context[0] = s_context
		sv.pred = ai
		sv.time = dep_time if dep_time is not None else datetime.now()
		sv.versione_cp = self.versione_cp
		self.pq.insert(s, sv, 0)
		cnt = 0
		while not self.pq.is_empty() and dist < max_distanza:
			cnt += 1
			min_priority = self.pq.get_min_priority()
			v = self.pq.delete_min()
			vv = <DijkstraVars>(vars[v.dijkstra_index])
			pred = vv.pred
			w = <NodoDijkstra>(pred.s)
			wv = <DijkstraVars>(vars[w.dijkstra_index])
			vv.context_i = wv.context_i
			# pprint(v.get_context(opt))
			pred.aggiorna_contesto(opt)
			time = vv.time
			#print "Prio", min_priority
			#print "Time", time			
			dist = vv.dist
			vv.settled = True
			v.aggiorna_risultati_vicini(risultati, opt)
			if risultati.completo():
				break
			for e in v.fstar:
				if e.attraversabile_vicini(opt) or not solo_pedonale:
					w = <NodoDijkstra>(e.t)
					wv = <DijkstraVars>(vars[w.dijkstra_index])
					if wv.versione_cp != versione_cp:
						inc_prio, tempo_arco = e.get_tempo(time, opt)
						if inc_prio >= 0:
							#print "inc_prio nuovo nodo", inc_prio
							wv.versione_cp = versione_cp
							wv.pred = e
							wv.settled = False
							new_prio = min_priority + inc_prio
							wv.prio = new_prio
							wv.time = time + timedelta(seconds=tempo_arco)
							wv.dist = dist + e.get_distanza()
							self.pq.insert(w, wv, new_prio)
					elif not wv.settled:
						inc_prio, tempo_arco = e.get_tempo(time, opt)
						#print "inc_prio nodo esistente", inc_prio
						if tempo_arco >= 0:
							new_prio = min_priority + inc_prio
							if new_prio < wv.prio:
								wv.prio = new_prio
								wv.time = time + timedelta(seconds=tempo_arco)
								wv.dist = dist + e.get_distanza()
								wv.pred = e
								self.pq.decrease_key(wv, new_prio)
				
		sv.pred = None
		self.pool.rm_nodo(ai.s)
		
		print "Dijkstra done, %d nodes reached" % (cnt,)
		
		


	cpdef indicazioni_su_tratti(self, NodoDijkstra s, NodoDijkstra t, object opzioni, tr=None, rev=False):
		opzioni['dijkstra'] = self
		cdef NodoDijkstra 
		p = []
		vars = self.vars
		s_orig = s
		if not rev:
			while t != s:
				p.append(t)
				e = vars[t.dijkstra_index].pred
				p.append(e)
				t = e.s
			iter = reversed(p)
		else:
			while s != t:
				p.append(s)
				# print vars[s.dijkstra_index].time
				e = vars[s.dijkstra_index].next
				p.append(e)
				s = e.t
			iter = p
		tr, tt = s_orig.init_percorso(opzioni, tr)
		for x in iter:
			#print "Tipo nodo/arco: " + str(type(x))
			tt = x.costruisci_percorso(tt, opzioni)
			#print tt.tempo, type(tt), type(x)
			#print "Restituisce un nodo di tipo: " + str(type(tt))		
		return tr


	def calcola_e_stampa(self, s, t, opt=opzioni_cp, dep_time=None, tr=None, s_context=None, rev=False):
		if not rev:
			self.dijkstra(s, set([t]), dep_time=dep_time, opt=opt, s_context=s_context)
		else:
			self.rev_dijkstra(t, set([s]), arr_time=dep_time, opt=opt, t_context=s_context)
		tr = self.indicazioni_su_tratti(s, t, opt, tr, rev)
		return tr, t.get_vars(opt).time
		
		
class DijkstraPool(object):
	def __init__(self, grafo, n):
		self.graph = grafo
		self.n = n
		self.queue = Queue()
		for i in range(n):
			self.queue.put(Dijkstra(grafo, self))
		self.free_list = []
		self.max_i = 0
		for id in grafo.nodi:
			grafo.nodi[id].dijkstra_index = self.max_i
			self.max_i += 1
		
	@contextmanager
	def get_dijkstra(self, n=1):
		ds = []
		try:
			with lock:
				for i in range(n):
					ds.append(self.queue.get())
			if n == 1:
				yield ds[0]
			else:
				yield ds
		finally:
			for d in ds:
				self.queue.put(d)
	
	def add_nodo(self, n):
		if len(self.free_list) == 0:
			n.dijkstra_index = self.max_i
			self.max_i += 1
		else:
			n.dijkstra_index = self.free_list.pop()
		self.graph.add_nodo(n)
		
	def add_arco(self, a):
		self.graph.add_arco(a)
		
	def rm_nodo(self, n):
		archi = set(n.fstar).union(set(n.bstar))
		for e in archi:
			self.rm_arco(e)
		self.free_list.append(n.dijkstra_index)
		self.graph.rm_nodo(n)
	
	def rm_arco(self, a):
		self.graph.rm_arco(a)
		
		
cpdef cerca_vicini_tragitto(Dijkstra dijkstra1, Dijkstra dijkstra2, NodoDijkstra s, NodoDijkstra t, object dep_time=None, object opt1=opzioni_cp, object s_context=context_cp, object opt2=None, int mandatory=True):
		"""
		Find fastest route from s to all vertices in ts
		
		s: vertex
		targets: set of vertices
		return: dictionary with the form
			t: (time(s, t), d(s, t))
		"""
		cdef NodoDijkstra v, w
		cdef long cnt
		cdef double min_priority, new_prio, inc_prio, min_priority1, min_priority2
		cdef short esci, reached, e1, e2
		cdef long versione_cp1
		cdef long versione_cp2		
		dijkstra1.cleanup()
		dijkstra2.cleanup()
		dijkstra1.versione_cp += 1
		dijkstra2.versione_cp += 1
		versione_cp1 = dijkstra1.versione_cp
		versione_cp2 = dijkstra2.versione_cp
		#opt['dijkstra'] = self
		opt1['rev'] = False
		opt2['rev'] = False	
		vars1 = dijkstra1.vars
		vars2 = dijkstra2.vars
		sv1 = <DijkstraVars>(vars1[s.dijkstra_index])
		sv1.dist = 0
		ai = ArcoIngresso(dijkstra1.pool, s)
		aiv1 = <DijkstraVars>(vars1[ai.s.dijkstra_index])
		aiv1.context_i = 0
		aiv2 = <DijkstraVars>(vars2[ai.s.dijkstra_index])
		aiv2.context_i = 0
		dijkstra1.context[0] = s_context
		dijkstra2.context[0] = s_context
		sv1.pred = ai
		sv1.time = dep_time if dep_time is not None else datetime.now()
		sv1.versione_cp = dijkstra1.versione_cp
		sv1.settled = False
		pq1 = dijkstra1.pq
		pq2 = dijkstra2.pq
		pq1.insert(s, sv1, 0)
		cnt = 0
		esci = False
		while esci == 0:
			cnt += 1
			e1 = pq1.is_empty()
			e2 = pq2.is_empty()
			if not e1:
				min_priority1 = pq1.get_min_priority()
			if not e2:
				min_priority2 = pq2.get_min_priority()
			if e1 and e2:
				esci = True
				break
			if e2 or (not e1 and min_priority1 < min_priority2):
				#print "p1", min_priority1
				reached = False
				v = pq1.delete_min()
				vv1 = <DijkstraVars>(vars1[v.dijkstra_index])
				vv1.settled = True
				pred = vv1.pred
				w = <NodoDijkstra>(pred.s)
				wv1 = <DijkstraVars>(vars1[w.dijkstra_index])
				vv1.context_i = wv1.context_i
				# pprint(v.get_context(opt))
				pred.aggiorna_contesto(opt1)
				time = vv1.time
				if (not mandatory) and (v == t):
					esci = 1
					break				
				
				if v.risultati_vicini(opt1):
					#print "Reached!"
					vv2 = <DijkstraVars>(vars2[v.dijkstra_index])
					vv2.settled = True
					vv2.versione_cp = versione_cp2
					vv2.pred = pred
					vv2.custom = True
					vv2.time = time
					vv2.dist = vv1.dist
					vv2.prio = min_priority1
					wv2 = <DijkstraVars>(vars2[w.dijkstra_index])
					# Copy context across graphs
					i = wv1.context_i
					j = dijkstra2.context_i
					if dijkstra2.context[j] is None:
						dijkstra2.context[j] = {}
					for k in dijkstra1.context[i]:
						dijkstra2.context[j][k] = dijkstra1.context[i][k]
					wv2.context_i = j
					dijkstra2.context_i = j + 1
					# End copy context
					#vv2.context_i = j
					#pred.aggiorna_contesto(opt)
					pq2.insert(v, vv2, min_priority1)
					

			else:
				#print "p2", min_priority2
				reached = True
				v = pq2.delete_min()
				vv2 = <DijkstraVars>(vars2[v.dijkstra_index])
				vv2.settled = True
				pred = vv2.pred
				w = <NodoDijkstra>(pred.s)
				wv2 = <DijkstraVars>(vars2[w.dijkstra_index])
				vv2.context_i = wv2.context_i
				# pprint(v.get_context(opt))
				pred.aggiorna_contesto(opt2)
				time = vv2.time
				if v == t:
					esci = 2
					break
				
			if not reached:
				vv = vv1
				wv = wv1
				pq = pq1
				vars = vars1
				versione_cp = versione_cp1
				min_priority = min_priority1
				opt = opt1
			else:
				vv = vv2
				wv = wv2
				pq = pq2
				vars = vars2
				versione_cp = versione_cp2
				min_priority = min_priority2
				opt = opt2

			#print "Prio", min_priority
			#print "Time", time
			dist = vv.dist
			for e in v.fstar:
				w = <NodoDijkstra>(e.t)
				wv = <DijkstraVars>(vars[w.dijkstra_index])
				if wv.versione_cp != versione_cp:
					inc_prio, tempo_arco = e.get_tempo(time, opt)
					if inc_prio >= 0:
						#print "inc_prio nuovo nodo", inc_prio
						wv.versione_cp = versione_cp
						wv.pred = e
						new_prio = min_priority + inc_prio
						wv.prio = new_prio
						wv.time = time + timedelta(seconds=tempo_arco)
						wv.dist = dist + e.get_distanza()
						wv.custom = False
						pq.insert(w, wv, new_prio)
				elif not wv.settled:
					inc_prio, tempo_arco = e.get_tempo(time, opt)
					#print "inc_prio nodo esistente", inc_prio
					if tempo_arco >= 0:
						new_prio = min_priority + inc_prio
						if new_prio < wv.prio:
							wv.prio = new_prio
							wv.time = time + timedelta(seconds=tempo_arco)
							wv.dist = dist + e.get_distanza()
							wv.pred = e
							pq.decrease_key(wv, new_prio)
				
		sv1.pred = None
		dijkstra1.pool.rm_nodo(ai.s)
		
		print "Dijkstra done, %d nodes reached" % (cnt,)
		
		return esci


cpdef indicazioni_su_tratti_vicini_tragitto(NodoDijkstra s, NodoDijkstra t, object opt1, object opt2, tr=None, stage=2):
	cdef NodoDijkstra
	p = []
	s_orig = s
	opzioni = opt2 if stage == 2 else opt1
	while t != s:
		p.append((t, opzioni))
		tv = opzioni['dijkstra'].vars[t.dijkstra_index]
		#print t.dijkstra_index, type(t)
		#if t.dijkstra_index == 8599:
		#	break
		if tv.custom:
			#print "CUSTOM"
			opzioni = opt1
		e = tv.pred
		#print type(e)
		p.append((e, opzioni))
		t = e.s
	iter = reversed(p)
	tr, tt = s_orig.init_percorso(opzioni, tr)
	for xl in iter:
		#print "Tipo nodo/arco: " + str(type(x))
		x, opzioni = xl
		tt = x.costruisci_percorso(tt, opzioni) # Nodo
		#print tt.tempo, type(tt), type(x)
		#print "Restituisce un nodo di tipo: " + str(type(tt))		
	return tr

def calcola_e_stampa_vicini_tragitto(dijkstra1, dijkstra2, s, t, opt=opzioni_cp, dep_time=None, tr=None, s_context=None, opt2=None, mandatory=True):
	if opt2 is None:
		opt2 = copy(opt)
	opt['dijkstra'] = dijkstra1
	opt2['dijkstra'] = dijkstra2		
	stage = cerca_vicini_tragitto(dijkstra1, dijkstra2, s, t, dep_time=dep_time, opt1=opt, s_context=s_context, opt2=opt2, mandatory=mandatory)
	tr = indicazioni_su_tratti_vicini_tragitto(s, t, opt, opt2, tr, stage)
	return tr, t.get_vars(opt).time