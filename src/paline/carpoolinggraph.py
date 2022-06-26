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


from datetime import date, time, datetime, timedelta
import traceback
from grafo import Nodo, Arco, Grafo
from geomath import wgs84_to_gbfe, distance
from tratto import TrattoCarPooling, TrattoCarPoolingArco, TrattoCarPoolingAttesa
from carpooling.models import PassaggioRichiesto, PassaggioOfferto, UtenteCarPooling

LUNGHEZZA_MINIMA_CARPOOLING = 1500

class ReteOffertaCarPooling(object):
	def __init__(self, offerta):
		self.id_offerta = offerta.pk
		self.aggiorna_vincoli(offerta)

	def aggiorna_vincoli(self, offerta=None):
		if offerta is None:
			offerta = PassaggioRichiesto.object.select_related().get(pk=self.id_offerta)
		richieste = offerta.passaggiorichiesto_set.all()
		all = list(richieste) + [offerta]
		self.utenti = set()
		self.uomini = False
		self.donne = False
		self.fumatori = False
		self.solo_non_fumatori = False
		self.solo_stesso_sesso = False
		for el in all:
			u = el.user
			self.utenti.add(u.pk)
			ucp = UtenteCarPooling.from_user(u)
			if ucp.sesso == 'M':
				self.uomini = True
			else:
				self.donne = True
			if ucp.fumatore:
				self.fumatori = True
			if ucp.solo_non_fumatori:
				self.solo_non_fumatori = True
			if ucp.solo_stesso_sesso:
				self.solo_stesso_sesso = True

	def viola_vincoli(self, vincoli):
		if vincoli['solo_stesso_sesso'] or self.solo_stesso_sesso:
			if(
				(vincoli['sesso'] == 'M' and self.donne)
				or (vincoli['sesso'] == 'F' and self.uomini)
			):
				return True
		if(
			(vincoli['solo_non_fumatori'] and self.fumatori)
			or (self.solo_non_fumatori and vincoli['fumatore'])
		):
			return True
		if vincoli['pk_utente'] in self.utenti:
			return True
		return False

class NodoCarPooling(Nodo):
	def __init__(self, tomtom_node, cpid, cpcount):
		Nodo.__init__(self, (14, cpid, cpcount))
		self.tomtom_node = tomtom_node
		
	def get_coordinate(self):
		return self.tomtom_node.get_coordinate()

class ArcoCarPoolingSalita(Arco):
	def __init__(self, nodo_car_pooling, tempo_arrivo, flessibilita, offerta):
		Arco.__init__(self, nodo_car_pooling.tomtom_node, nodo_car_pooling, (15, nodo_car_pooling.id[1], nodo_car_pooling.id[2]))
		self.nodo_car_pooling = nodo_car_pooling
		self.tempo_arrivo_min = tempo_arrivo - timedelta(seconds=flessibilita)
		self.tempo_arrivo_max = tempo_arrivo + timedelta(seconds=flessibilita)
		self.tempo_arrivo = tempo_arrivo
		self.rete_offerta = ReteOffertaCarPooling(offerta)

	def aggiorna_vincoli(self, offerta=None):
		self.rete_offerta.aggiorna_vincoli(offerta)
		

	def aggiorna_contesto(self, opz, rev=False):
		context = self.duplica_contesto(opz, rev)
		context['carpooling_usato'] = 0


	def get_tempo(self, t, opt):
		if (
			not opt['car_pooling']
			or t > self.tempo_arrivo_max or "CP%d" % self.id[1] in opt['linee_escluse']
			or self.s.get_context(opt)['carpooling_usato'] != -1
			or self.rete_offerta.viola_vincoli(opt['carpooling_vincoli'])
		):
			return (-1, -1)
		if t > self.tempo_arrivo_min:
			return (0, 0)
		diff = (self.tempo_arrivo_min - t).total_seconds()
		return (diff, diff)
	
	def costruisci_percorso(self, t, opzioni):
		vars = self.s.get_vars(opzioni)
		if type(t) != TrattoCarPooling:
			offset = vars.time - self.tempo_arrivo
			t = TrattoCarPooling(t.parent, vars.time, offset)
		TrattoCarPoolingAttesa(t, vars.time, self.get_tempo(vars.time, opzioni)[1])
		return t
	
	@classmethod
	def update_or_create(cls, dijkstra_pool, nodo_car_pooling, tempo_arrivo, flessibilita, offerta):
		graph = dijkstra_pool.graph
		eid = (15, nodo_car_pooling.id[1], nodo_car_pooling.id[2])
		if eid in graph.archi:
			a = graph.archi[eid]
			a.tempo_arrivo_min = tempo_arrivo - timedelta(seconds=flessibilita)
			a.tempo_arrivo_max = tempo_arrivo + timedelta(seconds=flessibilita)
			a.aggiorna_vincoli(offerta)
		else:
			a = ArcoCarPoolingSalita(nodo_car_pooling, tempo_arrivo, flessibilita, offerta)
			dijkstra_pool.add_arco(a)
		return a
	
	
	
class ArcoCarPoolingDiscesa(Arco):
	def __init__(self, nodo_car_pooling):
		Arco.__init__(self, nodo_car_pooling, nodo_car_pooling.tomtom_node, (17, nodo_car_pooling.id[1], nodo_car_pooling.id[2]))
		self.nodo_car_pooling = nodo_car_pooling

	def get_tempo(self, t, opt):
		if self.s.get_context(opt)['carpooling_usato'] < LUNGHEZZA_MINIMA_CARPOOLING:
			return (-1, -1)
		return (1, 0)

	@classmethod
	def update_or_create(cls, dijkstra_pool, nodo_car_pooling):
		graph = dijkstra_pool.graph
		eid = (17, nodo_car_pooling.id[1], nodo_car_pooling.id[2])
		if eid in graph.archi:
			a = graph.archi[eid]
		else:
			a = ArcoCarPoolingDiscesa(nodo_car_pooling)
			dijkstra_pool.add_arco(a)
		return a	
	
	

class ArcoCarPooling(Arco):
	def __init__(self, cpid, cpcount, tomtom_edge, cp_s, cp_t, tempo_percorrenza, posti):
		Arco.__init__(self, cp_s, cp_t, (13, cpid, cpcount))
		self.tomtom_edge = tomtom_edge
		if tomtom_edge is not None:
			self.w = tomtom_edge.w
		else:
			self.w = distance(cp_s.get_coordinate()[0], cp_t.get_coordinate()[0]) 
		self.tempo_percorrenza = tempo_percorrenza
		self.posti = posti

	def get_distanza(self):
		return self.w
	
	def get_coordinate(self):
		"""
		Restituisce una lista di coppie: le coordinate dei punti. Oppure None
		"""
		if self.tomtom_edge is not None:
			return self.tomtom_edge.get_coordinate()
		return self.s.get_coordinate() + self.t.get_coordinate()
	
	def get_tempo(self, t, opz):
		if self.posti > 0:
			return (self.tempo_percorrenza, self.tempo_percorrenza)
		return (-1, -1)
		
	def costruisci_percorso(self, t, opzioni):
		vars = self.s.get_vars(opzioni)
		TrattoCarPoolingArco(t, vars.time, self, self.tempo_percorrenza)
		return t
	
	def get_nome(self):
		if self.tomtom_edge is not None:
			return self.tomtom_edge.get_nome()
		return ""
	
	def aggiorna_contesto(self, opz, rev=False):
		context = self.duplica_contesto(opz, rev)
		context['carpooling_usato'] += self.w
	
	@classmethod
	def update_or_create(cls, dijkstra_pool, cpid, cpcount, osm_edge, cp_s, cp_t, tempo_percorrenza, posti):
		graph = dijkstra_pool.graph
		eid = (13, cpid, cpcount)
		if eid in graph.archi:
			a = graph.archi[eid]
			a.tempo_percorrenza = tempo_percorrenza
			a.posti = posti
		else:
			a = ArcoCarPooling(cpid, cpcount, osm_edge, cp_s, cp_t, tempo_percorrenza, posti)
			dijkstra_pool.add_arco(a)
		return a	
		
	
def carica_percorsi(rete, dijkstra_pool, offerte_queryset):
	print "Carico percorsi car pooling"
	grafo = dijkstra_pool.graph
	for p in offerte_queryset:
		#print p
		archi = p.percorso.percorso['archi']
		durata = p.durata

		offset = 0
		annullato = p.annullato
		upk = p.user.pk
		# Ricalcolo la durata originaria del percorso
		d_orig = 0.0
		opt = rete.get_opzioni_calcola_percorso(False, False, False, False, False, auto=True)
		for i in range(1, len(archi) - 1):
			a = archi[i]
			tempo_arrivo, eid, sid, tid, tempo_percorrenza = a['t'], a['eid'], a['sid'], a['tid'], a['tp']
			if eid[0] == 12:
				e = grafo.archi[eid]
				d_orig += e.get_tempo(tempo_arrivo, opt)[1]
			else:
				d_orig += tempo_percorrenza
		fattore_durata = durata / d_orig
		# Costruisco gli archi con la nuova durata
		count = 0
		if p.orario_definito is None:
			t = p.orario
			flessibilita = p.flessibilita
		else:
			t = p.orario_definito
			flessibilita = 0
		a = archi[1]
		tempo_arrivo, eid, sid, tid, tempo_percorrenza = a['t'], a['eid'], a['sid'], a['tid'], a['tp']
		osm_s = e.s
		cp_s = NodoCarPooling(osm_s, p.pk, 0)
		dijkstra_pool.add_nodo(cp_s)
		arco_salita = ArcoCarPoolingSalita.update_or_create(dijkstra_pool, cp_s, t, flessibilita, p)
		arco_discesa = ArcoCarPoolingDiscesa.update_or_create(dijkstra_pool, cp_s)
		salto = False
		tempo_salto = 0
		for i in range(1, len(archi) - 1):
			a = archi[i]
			tempo_arrivo, eid, sid, tid, tempo_percorrenza, posti = a['t'], a['eid'], a['sid'], a['tid'], a['tp'], a['p']
			if annullato:
				posti = 0
			if eid[0] == 12:
				e = grafo.archi[eid]
				if salto:
					cp_t = NodoCarPooling(e.s, p.pk, count + 1)
					ecp = ArcoCarPooling.update_or_create(dijkstra_pool, p.pk, count, None, cp_s, cp_t, tempo_percorrenza, posti)
					t += timedelta(seconds=tempo_salto)
					tempo_salto = 0
					count += 1
					salto = False
					cp_s = cp_t
				osm_t = e.t
				cp_t = NodoCarPooling(osm_t, p.pk, count + 1)
				dijkstra_pool.add_nodo(cp_t)
				arco_salita = ArcoCarPoolingSalita.update_or_create(dijkstra_pool, cp_t, t, flessibilita, p)
				arco_discesa = ArcoCarPoolingDiscesa.update_or_create(dijkstra_pool, cp_t)
							
				tempo_percorrenza = e.get_tempo(t, opt)[1] * fattore_durata
				ecp = ArcoCarPooling.update_or_create(dijkstra_pool, p.pk, count, e, cp_s, cp_t, tempo_percorrenza, posti)		
				t += timedelta(seconds=tempo_percorrenza)			
				count += 1
				cp_s = cp_t
			else:
				salto = True
				tempo_percorrenza = tempo_percorrenza * fattore_durata
				tempo_salto += tempo_percorrenza		
					
			

