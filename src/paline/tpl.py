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

from bt import AVLTree as Avl
import pyximport; pyximport.install()
from models import *
from datetime import datetime, timedelta, time, date
import Queue
from threading import Thread, Lock
from grafo import Arco, Nodo, Grafo, DijkstraPool
import shapefile
import math
from copy import copy
from time import sleep
import logging
import traceback
import geomath
import geocoder
from django.contrib.gis.geos import Point
from django.db import transaction as djangotransaction
from servizi.utils import datetime2compact, datetime2time, transaction, date2datetime
from servizi.utils import datetime2date, dateandtime2datetime, ricapitalizza
from servizi.utils import model2contenttype, contenttype2model, batch_qs, datetime2mysql
from servizi.utils import mostra_avanzamento, mysql2datetime, date2mysql
from servizi.models import Festivita
import os
import settings
import tratto
from django import db
from django.db.models import Avg, Max, Min, Count, F
import os, os.path
from floatingvehicle import FVPath
from constance import config
import cPickle as pickle
from mercury.models import Mercury, DaemonControl
from risorse import models as risorse
from ztl.views import Orari, orari_per_ztl
import xmlrpclib
import tomtom
from collections import defaultdict
from pprint import pprint
from random import Random
from gtfs import realtime, parse_static, alerts #, map_id_veicolo
# import gtfs_rt


LINEE_MINI = ['90', '542', '61', 'MEB', 'MEB1', '998', 'MEA', 'FR1']
#LINEE_MINI = ['012', '063', '90', '999', 'MEB', 'MEB1']
VALIDITA_TEMPO_ARCHI = timedelta(minutes=60)
# Per ogni ciclo di aggiornamento tempi archi, massimo numero di tentativi per ciascun arcoprint
MAX_PERIODO_PERCORSO_ATTIVO = timedelta(minutes=58)
MAX_ARRETRAMENTO_MANTENIMENTO_CORSA = 200

MIN_PESO_VELOCITA = 0.1

TIMEOUT_VALIDITA_VEICOLO = timedelta(minutes=5)
AVANZAMENTO_INTERPOLATO = False

TIMEOUT_AGGIORNAMENTO_RETE = timedelta(seconds=90)


class RetePalina(object):
	def __init__(self, id_palina, nome, soppressa=False):
		object.__init__(self)
		self.inizio_validita = None
		self.id_palina = id_palina
		self.nome = nome
		self.zona = None
		self.nome_ricapitalizzato = ricapitalizza(nome)
		self.arrivi = {}
		self.ultimo_aggiornamento = None
		self.x = -1
		self.y = -1
		self.fermate = {}
		self.tratti_percorsi_precedenti = []
		self.tratti_percorsi_successivi = []
		self.soppressa = soppressa
		self.ferroviaria = False
		# Nota: le paline soppresse esistono, ed esistono anche le corrispondenti fermate.
		#       Nel grafo, però, esistono solo i nodi relativi alle fermate, NON quelli relativi alle paline.
		#       In questo modo sarà possibile transitare per le fermate ma non salire/scendere dal mezzo.

	def serializza_dinamico(self):
		return {
			'type': 'RetePalina',
			'id': self.id_palina,
			'arrivi': self.arrivi,
			'ultimo_aggiornamento': self.ultimo_aggiornamento,
		}

	def deserializza_dinamico(self, rete, res):
		self.arrivi = res['arrivi']
		self.ultimo_aggiornamento = res['ultimo_aggiornamento']

	def serializza(self):
		return {
			'id': self.id_palina,
			'zona': self.zona,
		}

	def deserializza(self, res):
		self.zona = res['zona']

	def log_arrivi(self, dt=None):
		if settings.CPD_LOG_PER_STATISTICHE:
			if dt is None:
				dt = datetime.now()
			for k in self.fermate:
				f = self.fermate[k]

				if f.tratto_percorso_successivo is None:
					#print "Capolinea percorso " + k
					f.log_arrivi(dt)

	def distanza(self, p):
		if self.x == -1 or p.x == -1:
			return None
		a = self.x - p.x
		b = self.y - p.y
		return math.sqrt(a * a + b * b)


class PosizioneVeicolo(object):
	"""
	Classe per rappresentare la posizione del veicolo su percorso
	"""
	def __init__(self, tratto_percorso, distanza, rev=False):
		"""
		Inizializza con rappresentazione standard

		:param tratto_percorso: tratto di percorso di appartenenza
		:param distanza: distanza dall'inizio del tratto (o dalla fine se rev=True)
		:param rev: se True, la distanza è espressa dalla fine del tratto
		"""
		self.tratto_percorso = tratto_percorso
		self.distanza = distanza if not rev else tratto_percorso.rete_tratto_percorsi.dist - distanza
		self._coord = None

	@classmethod
	def from_coord(cls, percorso, x, y):
		"""
		Inizializza una posizione veicolo a partire da percorso e coordinate proiettive

		:return: (PosizioneVeicolo, distanza_2d)
		"""
		i, dist_tratto, dist_inizio = percorso.segmenti.project((x, y))
		return cls.from_dist(percorso, dist_inizio), dist_tratto

	@classmethod
	def generate_diverging(cls, center, n):
		"""
		Starting from center, generate alternating indexes between 0 and n - 1
		"""
		if center < 0:
			center = 0
		if center >= n:
			center = n - 1
		a = center
		b = center + 1
		while a >= 0 and b < n:
			yield a
			a -= 1
			yield b
			b += 1

		while a >= 0:
			yield a
			a -= 1

		while b < n:
			yield b
			b += 1

	@classmethod
	def from_coord_and_stop_no(cls, percorso, x, y, stop_no, fuziness=0, max_dist=100):
		"""
		Init position from coordinates and stop number in path

		:param percorso: Percorso object
		:param x: coord x, gbfe
		:param y: coord y, gbfe
		:param stop_no: number of next stop (departing terminus has number 0)
		:param fuziness: consider also stops +-fuziness
		:return: PosizioneVeicolo object
		"""
		tpos = percorso.tratti_percorso
		min_d = None
		min_i = None
		min_d_2d = None
		min_iterations = 1 + 2 * fuziness
		for cnt, i in enumerate(cls.generate_diverging(stop_no - 1, len(tpos))):
			tpi = tpos[i].rete_tratto_percorsi
			it, dist_tratto, dist_inizio, dist_2d = tpi.segmenti.project_and_get_dist((x, y))
			if min_d_2d is None or dist_2d < min_d_2d:
				min_d_2d = dist_2d
				min_i = i
				min_d = min(max(0, dist_inizio), tpi.dist)
			if cnt >= min_iterations - 1 and min_d_2d <= max_dist:
				break

		tpo = tpos[min_i]
		dist = tpo.s.distanza_da_partenza + min_d
		return cls.from_dist(percorso, dist), min_d_2d

	@classmethod
	def from_dist(cls, percorso, distanza_capolinea, rev=False):
		"""
		Inizializza una posizione veicolo a partire dalla distanza dal capolinea

		Se rev, restituisce la distanza dal capolinea di destinazione

		:return: Oggetto PosizioneVeicolo
		"""
		residua = distanza_capolinea if not rev else percorso.dist - distanza_capolinea
		tp = percorso.tratti_percorso[0]

		while True:
			dist = tp.rete_tratto_percorsi.dist
			tratto_successivo = tp.t.tratto_percorso_successivo
			if residua < dist or tratto_successivo is None:
				return PosizioneVeicolo(tp, residua)
			residua -= dist
			tp = tratto_successivo

	@classmethod
	def from_fermata(cls, percorso, indice_fermata, dist_fermata=None, rev=False):
		"""
		Inizializza una posizione veicolo a partire da numero e distanza della fermata

		indice_fermata: indice fermata non soppressa, a partire da 0
		dist_fermata: distanza dalla fermata; se None, posiziona nel punto medio
		Se rev, conta all'indietro dal capolinea di destinazione

		:return: Oggetto PosizioneVeicolo
		"""
		if not rev:
			n_tratto = percorso.map_fermate_tratti[indice_fermata]
			tp = percorso.tratti_percorso[n_tratto]
			dist = tp.rete_tratto_percorsi.dist
			if dist_fermata is None:
				dist_fermata = dist / 2
			while dist < dist_fermata:
				dist_fermata -= dist
				tp = tp.t.tratto_percorso_successivo
				dist = tp.rete_tratto_percorsi.dist
			return PosizioneVeicolo(tp, dist_fermata)
		else:
			indice_fermata = percorso.numero_fermate - indice_fermata - 1
			n_tratto = percorso.map_fermate_tratti[indice_fermata + 1]
			tp = percorso.tratti_percorso[n_tratto - 1]
			dist = tp.rete_tratto_percorsi.dist
			if dist_fermata is None:
				dist_fermata = dist / 2
			while dist < dist_fermata:
				dist_fermata -= dist
				tp = tp.t.tratto_percorso_precedente
				dist = tp.rete_tratto_percorsi.dist
			return PosizioneVeicolo(tp, dist - dist_fermata)

	def get_dettagli(self, coord=False):
		"""
		Restituisce dettagli (e rappresentazioni alternative) della posizione

		coord: se True, calcola e restituisce le coordinate e l'azimuth del punto

		Restituisce un dizionario con le seguenti chiavi:
		- distanza_capolinea_iniziale: distanza dal capolinea iniziale
		- distanza_capolinea_finale: distanza dal capolinea finale
		- tratto_percorso: tratto_percorso a cui appartiene il punto
		- distanza_inizio_tratto: distanza dall'inizio del tratto
		- distanza_fine_tratto: distanza dalla fine del tratto
		- progressiva_tratto: progressivo del tratto di percorso (partendo da 0 per il primo tratto)
		- progressiva_fermata: progressivo della fermata non soppressa (partendo da 0 per il capolinea di origine)
		- x, y, azimuth: coordinate nel sistema di riferimento usato (e.g. Gauss-Boaga fuso est)
		"""
		tp = self.tratto_percorso
		dist_inizio = tp.s.distanza_da_partenza + self.distanza
		percorso = tp.rete_percorso

		out = {
			'distanza_capolinea_iniziale': dist_inizio,
			'distanza_capolinea_finale': percorso.dist - dist_inizio,
			'tratto_percorso': tp,
			'distanza_inizio_tratto': self.distanza,
			'distanza_fine_tratto': tp.rete_tratto_percorsi.dist - self.distanza,
			'progressiva_tratto': tp.indice_tratto,
			'progressiva_fermata': tp.indice_fermata,
		}

		if coord:
			if self._coord is None:
				self._coord = tp.rete_tratto_percorsi.linear_to_coord(self.distanza)
			if self._coord is not None:
				out.update(self._coord)
			else:
				out['x'] = None
				out['y'] = None
				out['azimuth'] = None

		return out

	def __sub__(self, other):
		"""
		Restituisce la differenza di posizione fra due posizioni del medesimo percorso, in metri
		"""
		assert self.tratto_percorso.rete_percorso is other.tratto_percorso.rete_percorso
		dist_inizio_1 = self.tratto_percorso.s.distanza_da_partenza + self.distanza
		dist_inizio_2 = other.tratto_percorso.s.distanza_da_partenza + other.distanza
		return dist_inizio_1 - dist_inizio_2

	def avanza_interpolando(self, dt, coefficiente_velocita=1, decelerando=False):
		"""
		Move position forward

		:param dt: timedelta object
		:param coefficiente_velocita: coefficient to lower speed
		:return: True if in path, False if out of path
		"""
		self._coord = None
		tpo = self.tratto_percorso
		percorso = tpo.rete_percorso
		tratto_percorso_finale = percorso.tratti_percorso[-1]
		dt = dt.seconds
		first = True
		tmax = TIMEOUT_VALIDITA_VEICOLO.seconds
		t = 0
		while dt >= 0:
			tpi = tpo.rete_tratto_percorsi
			v = tpi.get_velocita() * coefficiente_velocita
			if decelerando:
				v = v - t / tmax
			d = tpi.dist
			if first:
				d -= self.distanza
				first = False
			if v <= 0:
				break

			if decelerando:
				t_left = tmax - t
				delta = (2 * v * t_left) ** 2 - 8 * v * d * t_left
				# print("Delta: ", delta)
				if delta >= 0:
					t_tratto = (2 * v * t_left - math.sqrt(delta)) / (2 * v)
					if t_tratto < dt:
						# Tratto percorso completamente
						dt -= t_tratto
						# print("t_tratto: " , t_tratto, " - dt: ", dt)
						t += t_tratto
						if tpo == tratto_percorso_finale:
							return False
						tpo = tpo.t.tratto_percorso_successivo
					else:
						# Tratto percorso in parte per ragioni di tempo
						d -= (v * t_tratto / 2) * (1 - ((t_tratto - dt) / t_tratto) ** 2)
						dt = -1

				else:
					# Tratto percorso in parte per ragioni di velocità (il veicolo si ferma)
					d -= (v * t_left) / 2
					dt = -1

			else:
				t_tratto = d / v
				if t_tratto < dt:
					dt -= t_tratto
					t += t_tratto
					if tpo == tratto_percorso_finale:
						return False
					tpo = tpo.t.tratto_percorso_successivo
				else:
					d -= (t_tratto - dt) * v
					dt = -1

		self.distanza = tpo.rete_tratto_percorsi.dist - d
		self.tratto_percorso = tpo
		self._coord = tpo.rete_tratto_percorsi.linear_to_coord(self.distanza)
		# if self.distanza > tpo.rete_tratto_percorsi.dist:
		# 	print("*** ERRORE DISTANZA: ", self.distanza, tpo.rete_tratto_percorsi.dist)
		# else:
		# 	print("+++ DISTANZA OK: ", self.distanza, tpo.rete_tratto_percorsi.dist)
		return True


class RetePercorso(object):
	def __init__(self, id_percorso, id_linea, tipo, descrizione, soppresso, gestore):
		object.__init__(self)
		self.id_percorso = id_percorso
		self.id_linea = id_linea
		self.tipo = tipo
		self.descrizione = descrizione if descrizione is not None else id_linea
		self.soppresso = soppresso and tipo != 'FR'
		self.gestore = gestore
		self.fv = FVPath()
		# Tratti del percorso, in ordine
		self.tratti_percorso = []
		self.frequenza = []
		self.tempo_stat_orari = []
		# Mapping tra gli indici delle fermate non soppresse (0-based) e i tratti di percorso che iniziano con tali fermate
		# L'indice del capolinea finale non è mappato, perché esso non dà origine a un tratto di percorso
		self.map_fermate_tratti = []
		self.numero_fermate = 0
		self.dist = 0
		self.veicoli = {}
		self.veicoli_problematici = {}
		self.ultimo_aggiornamento = None
		self.orario_inizio_aggiornamento_veicoli = None
		self.segmenti = None
		for i in range(0, 7):
			self.frequenza.append([(0.0, -1, -1) for j in range(0, 24)])

	def __repr__(self):
		return "Percorso %s (linea %s)" % (self.id_percorso, self.id_linea)

	def serializza(self):
		return {
			'id': self.id_percorso,
			'frequenza': self.frequenza,
			'tempo_stat_orari': self.tempo_stat_orari,
		}

	def deserializza(self, res):
		self.frequenza = res['frequenza']
		self.tempo_stat_orari = res['tempo_stat_orari']

	def init_mapping_fermate_non_soppresse(self):
		"""
		Inizializza il mapping delle fermate non soppresse e gli indici dei tratti di percorso

		Metodo chiamato durante il caricamento della rete, per mappare l'indice di ogni fermata non soppressa
		nel primo tratto di percorso con origine in essa.
		"""
		n_tratto = 0
		n_fermata = 0
		for tp in self.tratti_percorso:
			tp.indice_tratto = n_tratto
			tp.indice_fermata = n_fermata
			f = tp.s
			if not f.rete_palina.soppressa:
				self.map_fermate_tratti.append(n_tratto)
				n_fermata += 1
			n_tratto += 1
		# Dummy final value
		self.map_fermate_tratti.append(n_tratto)
		self.numero_fermate = n_fermata

	def serializza_dinamico(self):
		return {
			'type': 'RetePercorso',
			'id': self.id_percorso,
			'veicoli': [id_veicolo for id_veicolo in self.veicoli],
		}

	def deserializza_dinamico(self, rete, res):
		self.veicoli = {}
		for id_veicolo in res['veicoli']:
			if not id_veicolo in rete.veicoli:
				rete.veicoli[id_veicolo] = ReteVeicolo(id_veicolo)
			self.veicoli[id_veicolo] = rete.veicoli[id_veicolo]

	def iter_punti(self):
		"""
		Restituisce un iteratore sui punti della polilinea, dall'ultimo al primo
		"""
		tp = self.tratti_percorso[0]
		while tp is not None:
			punti = tp.rete_tratto_percorsi.punti
			n = len(punti)
			for i in range(n):
				yield punti[i]
			tp = tp.t.tratto_percorso_successivo

	def iter_punti_rev(self):
		"""
		Restituisce un iteratore sui punti della polilinea, dall'ultimo al primo
		"""
		tp = self.tratti_percorso[-1]
		while tp is not None:
			punti = tp.rete_tratto_percorsi.punti
			n = len(punti)
			for i in range(n-1, -1, -1):
				yield punti[i]
			tp = tp.s.tratto_percorso_precedente

	def set_punti(self):
		self.segmenti = geocoder.SegmentGeocoder()
		punti = list(self.iter_punti())
		for i in range(1, len(punti)):
			self.segmenti.add_segment(punti[i-1], punti[i], i)
		self.segmenti.freeze()

	def log_tempo_attesa(self, data=None, ora=None):
		arrivi = self.tratti_percorso[-1].t.arrivi
		if len(arrivi) > 0:
			tempo = arrivi[0]['tempo']
			if tempo > -1:
				if data is None:
					t = datetime.now()
					ora = datetime2time(t)
					data = datetime2date(t)
				LogTempoAttesaPercorso(
					id_percorso=self.id_percorso,
					data=data,
					ora=ora,
					tempo=tempo
				).save()

	def stampa_tempi(self):
		print " *** Tempi percorso %s (linea %s) ***" % (self.id_percorso, self.id_linea)
		i = 0
		for tp in self.tratti_percorso:
			i += 1
			t = tp.rete_tratto_percorsi
			s = str(t.tempo_percorrenza)
			#else:
			#	s = str(t.tempo_percorrenza_interpolato) + " (I)"
			print "%d - %s" % (i, s)

	def calcola_distanze(self):
		self.tratti_percorso[0].s.distanza_da_partenza = 0
		d = 0
		for tp in self.tratti_percorso:
			d += tp.rete_tratto_percorsi.dist
			tp.t.distanza_da_partenza = d

	def get_destinazione(self):
		return self.tratti_percorso[-1].t.rete_palina.nome_ricapitalizzato

	def calcola_percorrenze(self):
		dist_rem = self.dist
		n = datetime.now()
		for t in self.tratti_percorso:
			dist = t.rete_tratto_percorsi.dist
			if dist is None:
				logging.error("Distanza non disponibile per percorso %s (linea %s)" % (self.id_percorso, self.id_linea))
				return
			nd = dist_rem - dist
			v, w = self.fv.compute_speed(n, dist_rem, nd)
			#print "SPEED: ", v, t.weight_tempo_percorrenza
			if v >= 0 and w >= 0:
				t.tempo_percorrenza = dist / v
				t.weight_tempo_percorrenza = w
			else:
				t.weight_tempo_percorrenza = -1
				#print "Non disponibile"
			dist_rem = nd
		#print "Distanza finale: ", dist_rem

	def get_fermate(self):
		fs = []
		for tp in self.tratti_percorso:
			fs.append(tp.s)
		fs.append(tp.t)
		return fs

	def get_paline(self):
		return [f.rete_palina for f in self.get_fermate()]

	def is_circolare(self):
		return self.tratti_percorso[0].s.rete_palina == self.tratti_percorso[-1].t.rete_palina

	def aggiorna_posizione_veicoli(self, forza_interpolazione=False):
		if AVANZAMENTO_INTERPOLATO or forza_interpolazione:
			# Vehicles that are (still) being moved forward
			# Map id_veicolo to 3-tuple (vehicle, left_dist_in_current_tratto_percorso, time to be moved forward)
			# If left_dist_in_current_tratto_percorso is None, vehicle is at the beginning of tratto_percorso
			veicoli_spostati = {}
			# Vehicles whose position has been settled, and whose waiting times have to be propagated
			# to all the following stops
			# Map id_veicle to 4-tuple (vehicle, partial_distance_from_starting_stop_of_tratto, waiting_time, dist_number_stops)
			veicoli_propaganti = {}
			n = datetime.now()
			for tpo in self.tratti_percorso:
				fermata = tpo.t
				fermata.reset_arrivi()
				for id_veicolo in tpo.veicoli:
					v = tpo.veicoli[id_veicolo]
					if v.is_valido():
						veicoli_spostati[id_veicolo] = (v, v.distanza_successiva, (n - v.ultima_interpolazione).seconds)
				tpi = tpo.rete_tratto_percorsi
				dist = tpi.dist
				velocita = tpi.get_velocita()
				da_eliminare = []
				for id_veicolo in veicoli_spostati:
					v, s, t = veicoli_spostati[id_veicolo]
					if s is None:
						s = dist
					if velocita < 0:
						da_eliminare.append(id_veicolo)
						veicoli_propaganti[id_veicolo] = (v, -1, None, 1)
					else:
						ds = velocita * t
						if ds < s:
							da_eliminare.append(id_veicolo)
							veicoli_propaganti[id_veicolo] = (v, dist - (s - ds), 0, 1)
							v.aggiorna_posizione_interpolata(tpo, ds, n) # To be analyzed
						else:
							veicoli_spostati[id_veicolo] = (v, None, t - (s / velocita))
				for id_veicolo in da_eliminare:
					del veicoli_spostati[id_veicolo]
				for id_veicolo in veicoli_propaganti:
					v, s, t, ferm = veicoli_propaganti[id_veicolo]
					if s < 0 or velocita < 0:
						fermata.add_arrivo(v, None, ferm)
						veicoli_propaganti[id_veicolo] = (v, -1, -1, ferm + 1)
					else:
						ds = dist - s
						dt = ds / velocita
						fermata.add_arrivo(v, n + timedelta(seconds=t + dt), ferm)
						veicoli_propaganti[id_veicolo] = (v, 0, t + dt, ferm + 1)
		# else:
			# Elimino veicoli vecchi
			# for tpo in self.tratti_percorso:
			# 	da_cancellare = []
			# 	arrivi = tpo.t.arrivi
			# 	for a in arrivi:
			# 		id_veicolo = a['id_veicolo']
			# 		if id_veicolo in self.veicoli:
			# 			v = self.veicoli[id_veicolo]
			# 			if not v.is_valido():
			# 				da_cancellare.append(a)
			# 		else:
			# 			da_cancellare.append(a)
			# 	for a in da_cancellare:
			# 		arrivi.remove(a)

	def elimina_tutti_veicoli(self):
		"""
		Elimina tutti i veicoli dal percorso

		:return:
		"""
		vs = self.veicoli.values()
		for v in vs:
			v.elimina_da_percorso()

	def stato(self):
		"""
		Restituisce informazioni sullo stato del percorso: fermate, tratti di percorso ecc.
		"""
		out = {
			'fermate': [],
		}
		s = self.tratti_percorso[0].s.rete_palina
		out['fermate'].append({
			'id_palina': s.id_palina,
			'nome': s.nome,
			'soppressa': s.soppressa,
			'nome_ricapitalizzato': s.nome_ricapitalizzato,
			'stato_traffico': 0,
		})
		n = datetime.now()
		for t in self.tratti_percorso:
			stato = -1
			tp = t.rete_tratto_percorsi
			v = -1
			if tp.ultimo_aggiornamento is not None and n - tp.ultimo_aggiornamento < VALIDITA_TEMPO_ARCHI:
				v = 3.6 * tp.dist / tp.tempo_percorrenza
				if v <= 5:
					stato = 1
				elif 5 < v <= 10:
					stato = 2
				elif 10 < v <= 15:
					stato = 3
				else:
					stato = 4
			t = t.t.rete_palina
			out['fermate'].append({
				'id_palina': t.id_palina,
				'nome': t.nome,
				'soppressa': t.soppressa,
				'nome_ricapitalizzato': t.nome_ricapitalizzato,
				'stato_traffico': stato,
			})
		return out

	def get_frequenza(self, dt=None):
		if dt is None:
			dt = datetime.now()
		d = Festivita.get_weekday(dt, compatta_feriali=True)
		t_prog, da, a = self.frequenza[d][dt.hour]
		# print "Frequenza percorso:", t_prog, da, a
		if not (da <= dt.minute <= a):
			return None
		else:
			return round(t_prog / 60.0)

	def statistiche(self):
		now = datetime.now()
		attesa_totale = 0
		attesa_max = None
		cnt = 0
		tempo_totale = 0
		distanza_totale = 0

		for t in self.tratti_percorso:
			f = t.t
			tempo = f.get_primo_arrivo(now)
			if tempo is not None:
				tempo = tempo[0]
				attesa_totale += tempo
				attesa_max = max(tempo, attesa_max)
				cnt += 1
			tp = t.rete_tratto_percorsi
			if tp.tempo_percorrenza > 0:
				tempo_totale += tp.tempo_percorrenza
				distanza_totale += tp.dist

		vic = 0
		vac = 0

		for id_veicolo in self.veicoli:
			v = self.veicoli[id_veicolo]
			if v.a_capolinea:
				vac += 1
			else:
				vic += 1

		freq = self.get_frequenza(now)
		indice_attesa = None
		if freq is not None and attesa_max is not None:
			indice_attesa = attesa_max / (freq * 60.0)

		return {
			'attesa_media': None if cnt == 0 else int(round(attesa_totale / (60.0 * cnt))),
			'attesa_max': None if attesa_max is None else int(round(attesa_max / 60.0)),
			'veicoli_in_corsa': vic,
			'veicoli_capolinea': vac,
			'velocita_media': None if distanza_totale == 0 else (3.6 * distanza_totale / tempo_totale),
			'frequenza_programmata': None if freq is None else int(freq),
			'indice_attesa': indice_attesa,
		}

	def destinazione(self):
		return self.tratti_percorso[-1].t.rete_palina.nome_ricapitalizzato

	def esporta_come_shape(self, path, gbfe=False):
		"""
		Esporta il percorso come coppia di shapefile, uno per il percorso e uno per le fermate

		path: cartella nella quale creare gli shapefile
		Il nome degli shapefile ha lo schema seguente:
		LINEA_PERCORSO_percorso.shp/dbf/...
		LINEA_PERCORSO_fermate.shp/dbf/...
		"""
		base_file_name = "{}_{}_".format(self.id_linea, self.id_percorso)
		with geomath.zipped_shapefile(shapefile.POLYLINE, path, base_file_name + "percorso", gbfe) as shp_p:
			with geomath.zipped_shapefile(shapefile.POINT, path, base_file_name + "fermate", gbfe) as shp_f:
				shp_p.autoBalance = 1
				shp_f.autoBalance = 1
				shp_f.field('ID_PAL', 'C', '10')
				shp_f.field('NOME_PAL', 'C', '40')
				shp_f.field('PROGR', 'N', '10')
				shp_p.field('ID_LINEA', 'C', '10')
				shp_p.field('ID_PERC', 'C', '10')
				shp_p.field('ID_PAL_S', 'C', '10')
				shp_p.field('NOME_PAL_S', 'C', '40')
				shp_p.field('PROGR', 'N', '10')
				shp_p.field('ID_PAL_T', 'C', '10')
				shp_p.field('NOME_PAL_T', 'C', '40')
				f = self.tratti_percorso[0].s
				i = 0
				palina_old = None
				while f is not None:
					pl = f.rete_palina
					if gbfe:
						lon, lat = pl.x, pl.y
					else:
						lon, lat = gbfe_to_wgs84(pl.x, pl.y)
					shp_f.point(lon, lat)
					shp_f.record(
						ID_PAL=pl.id_palina,
						NOME_PAL=pl.nome,
						PROGR=i,
					)
					if palina_old is not None:
						line = []
						punti = f.tratto_percorso_precedente.rete_tratto_percorsi.punti
						for pt in punti:
							if gbfe:
								ptw = pt
							else:
								ptw = gbfe_to_wgs84(*pt)
							line.append(ptw)
						shp_p.line(parts=[line])
						shp_p.record(
							ID_LINEA=self.id_linea,
							ID_PERC=self.id_percorso,
							ID_PAL_S=palina_old.id_palina,
							NOME_PAL_S=palina_old.nome,
							ID_PAL_T=pl.id_palina,
							NOME_PAL_T=pl.nome,
							PROGR=i,
						)
					palina_old = pl
					i += 1
					f = f.tratto_percorso_successivo.t if f.tratto_percorso_successivo is not None else None


class ReteTrattoPercorsi(object):
	"""
	Rappresenta un tratto fra due paline, condiviso fra uno o più percorsi
	"""
	def __init__(self, s, t, rete):
		object.__init__(self)
		self.s = s
		self.t = t
		s.tratti_percorsi_successivi.append(self)
		t.tratti_percorsi_precedenti.append(self)
		self.percorsi = {}
		self.tempo_percorrenza = -1
		self.ultimo_aggiornamento = None
		self.tempo_percorrenza_stat_orari = []
		self.punti = []
		self.dist = None
		self.rete = rete
		self.segmenti = None #geocoder.SegmentGeocoder()

		self.infotp = False
		self.tratti_percorso = []

	def get_id(self):
		return (self.s.id_palina, self.t.id_palina)

	def serializza_dinamico(self):
		return {
			'type': 'ReteTrattoPercorsi',
			'id': self.get_id(),
			'tempo_percorrenza': self.tempo_percorrenza,
			'ultimo_aggiornamento': self.ultimo_aggiornamento,
		}

	def deserializza_dinamico(self, rete, res):
		self.tempo_percorrenza = res['tempo_percorrenza']
		self.ultimo_aggiornamento = res['ultimo_aggiornamento']

	def serializza(self):
		return {
			'id': self.get_id(),
			'punti': self.punti,
			'dist': self.dist,
			'tempo_percorrenza_stat_orari': self.tempo_percorrenza_stat_orari,
		}

	def deserializza(self, res):
		self.set_punti(res['punti'])
		self.set_dist(res['dist'])
		self.tempo_percorrenza_stat_orari = res['tempo_percorrenza_stat_orari']

	def aggiungi_tratto_percorso(self, tp):
		self.percorsi[tp.rete_percorso.id_percorso] = tp
		if tp.rete_percorso.tipo in TIPI_LINEA_INFOTP:
			self.infotp = True

	def add_tratto_percorso(self, tp):
		self.tratti_percorso.append(tp)

	def media_tempi_percorrenza(self, logging=False):
		tot = 0
		cnt = 0
		for t in self.tratti_percorso:
			#print "TRATTO, weight=", t.weight_tempo_percorrenza, t.tempo_percorrenza
			if t.weight_tempo_percorrenza > 0:
				if t.tempo_percorrenza < 0:
					print "VELOCITA ARCO SINGOLO NEGATIVA", t.tempo_percorrenza, t.weight_tempo_percorrenza
				if self.dist < 0:
					print "DISTANZA NEGATIVA"
				cnt += t.weight_tempo_percorrenza
				tot += t.weight_tempo_percorrenza * (self.dist / t.tempo_percorrenza)
				#print "Considero la velocità: ", (self.dist / t.tempo_percorrenza)
		if cnt > MIN_PESO_VELOCITA:
			velocita = tot / cnt
			#print "La velocità media: ", velocita
			self.tempo_percorrenza = self.dist / velocita
			if self.tempo_percorrenza < 0:
				print "TEMPO RISULTANTE < 0", self.tempo_percorrenza
			n = datetime.now()
			self.ultimo_aggiornamento = n
			if logging and settings.CPD_LOG_PER_STATISTICHE:
				self.log_per_statistiche(n, cnt)
		#print "Calcolato tempo percorrenza:", cnt, self.tempo_percorrenza

	def log_per_statistiche(self, dt=None, peso=1):
		if dt is None:
			dt = datetime.now()
		tp = self.tempo_percorrenza
		if tp > 0:
			velocita = self.dist / tp
			LogTempoArco(
				id_palina_s=self.s.id_palina,
				id_palina_t=self.t.id_palina,
				data=datetime2date(dt),
				ora=datetime2time(dt),
				tempo=velocita,
				peso=peso,
			).save()

	def get_velocita(self):
		if self.ultimo_aggiornamento is None or datetime.now() - self.ultimo_aggiornamento > VALIDITA_TEMPO_ARCHI:
			return -1
		if self.tempo_percorrenza == -1 or self.dist is None:
			return -1
		return self.dist / self.tempo_percorrenza

	def distanza(self):
		return self.dist
		#return self.s.distanza(self.t)

	def coord_to_linear(self, p):
		"""
		Restituisce la distanza lineare della proiezione di p sul tratto dall'inizio del tratto
		"""
		i, dist_tratto, dist_inizio = self.segmenti.project(p)
		return dist_inizio

	def linear_to_coord(self, dist):
		"""
		Restituisce coordinate ed azimuth corrispondenti alla distanza

		:param dist: distanza da inizio tratto
		:return: array con chiavi x, y (coord. proiettate) e azimuth
		"""
		op = None
		mp = None
		d = dist
		for p in self.punti:
			if op is not None:
				dp = geomath.distance(p, op)
				if d < dp:
					frac = d / dp
					#print "frac = ", frac
					mp = (op[0] + frac * (p[0] - op[0]), op[1] + frac * (p[1] - op[1]))
					#print "Posizione: ", mp
					break
				d -= dp
			op = p
		if mp is None:
			return None
		return {
			'x': mp[0],
			'y': mp[1],
			'azimuth': geomath.azimuth_deg(op, p)
		}

	def set_dist(self, dist):
		if dist is not None:
			delta = 0
			if self.dist is not None:
				delta = -self.dist
			self.dist = dist
			delta += dist

			for k in self.percorsi:
				self.percorsi[k].rete_percorso.dist += delta

	def set_punti(self, punti):
		self.segmenti = geocoder.SegmentGeocoder()
		self.punti = punti
		for i in range(1, len(punti)):
			self.segmenti.add_segment(punti[i-1], punti[i], i)
		self.segmenti.freeze()

	def sposta_paline_su_percorso(self):
		self.s.x, self.s.y = self.punti[0][0], self.punti[0][1]
		self.t.x, self.t.y = self.punti[-1][0], self.punti[-1][1]


class ReteFermata(object):
	"""
	Rappresenta una fermata di un percorso presso una palina
	"""
	def __init__(self, id_fermata, rete_palina, rete_percorso, rete):
		self.id_fermata = id_fermata
		self.rete_palina = rete_palina
		self.rete_percorso = rete_percorso
		self.rete = rete
		# Gli arrivi qui sono ordinati per tempo di attesa, e ricalcolati di frequente
		# a partire dagli arrivi al capolinea di destinazione (vecchio metodo)
		# oppure direttamente a partire dalla posizione dei veicoli (nuovo metodo)
		self.arrivi = []
		self.arrivi_temp = []
		self.ultimo_aggiornamento = None
		rete_palina.fermate[rete_percorso.id_percorso] = self
		if rete_percorso.tipo in TIPI_LINEA_FERRO:
			rete_palina.ferroviaria = True
		self.tratto_percorso_precedente = None
		self.tratto_percorso_successivo = None
		self.distanza_da_partenza = -1

	def is_valida(self):
		return self.ultimo_aggiornamento is not None and datetime.now() - self.ultimo_aggiornamento <= TIMEOUT_VALIDITA_VEICOLO

	def serializza_dinamico(self):
		arr = []
		for el in self.arrivi:
			el2 = copy(el)
			if 'tratto_percorso' in el2:
				el2['tratto_percorso'] = el2['tratto_percorso'].get_id()
			arr.append(el2)
		return {
			'type': 'ReteFermata',
			'id': self.id_fermata,
			'arrivi': arr,
			'ultimo_aggiornamento': self.ultimo_aggiornamento,
		}

	def deserializza_dinamico(self, rete, res):
		self.ultimo_aggiornamento = res['ultimo_aggiornamento']
		arr = res['arrivi']
		for a in arr:
			if 'tratto_percorso' in a:
				a['tratto_percorso'] = rete.tratti_percorso[a['tratto_percorso']]
		self.arrivi = arr

	def is_capolinea(self):
		if self.rete_percorso.is_circolare():
			t = self.tratto_percorso_successivo
			if t is None:
				return False
			return t.t.tratto_percorso_successivo is None
		else:
			return self.tratto_percorso_successivo is None

	def is_capolinea_partenza(self):
		return self.tratto_percorso_precedente is None

	def log_arrivi(self, dt=None):
		if dt is None:
			dt = datetime.now()
		logged = set()
		for a in self.arrivi_temp:
			idp = a['id_percorso']
			t = a['tempo']
			if t > -1 and not idp in logged:
				logged.add(idp)
				LogTempoAttesaPercorso(
					id_percorso=idp,
					data=date.today(),
					ora=datetime2time(dt),
					tempo=t,
				).save()

	def get_primo_arrivo(self, t, rev=False):
		"""
		Restituisce il primo arrivo del bus a partire dal tempo t (secondi), None se non disponibile

		Restituisce una coppia (t, el), dove el è il dizionario con le info sull'arrivo del veicolo
		"""
		#TODO: rendere la funzione efficiente con un'opportuna struttura dati!
		if self.ultimo_aggiornamento is None:
			return None
		diff = (t - self.ultimo_aggiornamento).seconds
		old = None
		for a in self.arrivi:
			if a['tempo'] >= 0 and a['tempo'] - diff >= 0: # Quando le partenze da capolinea sono "ufficiali", le uso! and not a['a_capolinea']:
				if not rev:
					return (a['tempo'] - diff, a)
				else:
					if old is not None:
						return (diff - old['tempo'], old)
					return None
			old = a
		return None

	def reset_arrivi(self):
		self.arrivi = []
		self.ultimo_aggiornamento = datetime.now()

	def reset_arrivi_temp(self):
		self.arrivi_temp = []

	def aggiungi_arrivo_temp(self, arrivo):
		a = copy(arrivo)
		self.arrivi_temp.append(a)

	def ordina_arrivi_temp(self, aggiorna_fv):
		n = datetime.now()
		for d in self.arrivi_temp:
			if aggiorna_fv and d['distanza'] > 0:
				self.rete_percorso.fv.add(d['id_veicolo'], n, d['distanza'])
		self.arrivi_temp.sort(key=lambda x: x['tempo'])

	def add_arrivo(self, veicolo, orario_arrivo, dist_fermate):
		"""
		Nuovo metodo per aggiungere gli arrivi
		"""
		n = datetime.now()
		self.ultimo_aggiornamento = n
		secondi = -1
		if orario_arrivo is not None:
			if orario_arrivo > n:
				secondi = (orario_arrivo - n).seconds
			else:
				secondi = 0
		if secondi > (10 + 4 * dist_fermate) * 60:
			secondi = -1
		percorso = veicolo.posizione.tratto_percorso.rete_percorso
		self.arrivi.append({
			'tempo': secondi,
			'id_percorso': percorso.id_percorso,
			'id_veicolo': veicolo.id_veicolo,
			'id_linea': percorso.id_linea,
			'destinazione': percorso.get_destinazione(),
			'fermate': dist_fermate,
			'pedana': veicolo.dotazioni['pedana'],
			'aria': veicolo.dotazioni['aria'],
			'moby': veicolo.dotazioni['moby'],
			'meb': veicolo.dotazioni['meb'],
			'a_capolinea': veicolo.a_capolinea,
			'in_arrivo': secondi < INTERVALLO_IN_ARRIVO,
			'stato_occupazione': veicolo.stato_occupazione,
		})
		self.arrivi.sort(key=lambda x: x['tempo'])

	def elimina_veicolo(self, veicolo):
		"""
		Elimina le previsioni di arrivo per il veicolo passato; restituisce True se erano presenti.
		"""
		id_veicolo = veicolo.id_veicolo
		for a in self.arrivi:
			if a['id_veicolo'] == id_veicolo:
				self.arrivi.remove(a)
				return True
		return False


def analizza_percorso(pe):
	for tp in pe.tratti_percorso:
		print "Percorrenza arco: " + str(tp.rete_tratto_percorsi.tempo_percorrenza)
		f = tp.t
		p = f.rete_palina
		for a in f.arrivi:
			idv = a['id_veicolo']
			if idv in p.arrivi:
				print "%s fermata %d: Differenza %s" % (str(idv), a['fermate'], str(a['tempo'] - p.arrivi[idv]['tempo']))
			else:
				print "%s fermata %d: Bus non presente in palina" % (str(idv), a['fermate'])


class ReteTrattoPercorso(object):
	"""
	Rappresenta un tratto di percorso fra due fermate
	"""
	def __init__(self, rete_percorso, rete_tratto_percorsi, rete_fermata_s, rete_fermata_t):
		self.rete_percorso = rete_percorso
		self.rete_tratto_percorsi = rete_tratto_percorsi
		rete_tratto_percorsi.add_tratto_percorso(self)
		self.s = rete_fermata_s
		self.t = rete_fermata_t
		self.s.tratto_percorso_successivo = self
		self.t.tratto_percorso_precedente = self
		# Indice del tratto nel percorso, partendo da 0
		self.indice_tratto = None
		# Indice della fermata non soppressa nel percorso, partendo da 0
		self.indice_fermata = None
		rete_tratto_percorsi.aggiungi_tratto_percorso(self)
		rete_percorso.tratti_percorso.append(self)
		self.tempo_percorrenza = 0
		self.weight_tempo_percorrenza = 0
		self.veicoli = {}

	def get_id(self):
		return (self.s.id_fermata, self.t.id_fermata)

	def serializza_dinamico(self):
		return {
			'type': 'ReteTrattoPercorso',
			'id': self.get_id(),
			'tempo_percorrenza': self.tempo_percorrenza,
			'weight_tempo_percorrenza': self.weight_tempo_percorrenza,
			'veicoli': [id_veicolo for id_veicolo in self.veicoli],
		}

	def deserializza_dinamico(self, rete, res):
		self.tempo_percorrenza = res['tempo_percorrenza']
		self.weight_tempo_percorrenza = res['weight_tempo_percorrenza']
		self.veicoli = {}
		for id_veicolo in res['veicoli']:
			if not id_veicolo in rete.veicoli:
				rete.veicoli[id_veicolo] = ReteVeicolo(id_veicolo)
			self.veicoli[id_veicolo] = rete.veicoli[id_veicolo]

	def coord_to_linear(self, p):
		"""
		Restituisce la distanza lineare dal capolinea iniziale della proiezione di p sul tratto
		"""
		dist_tratto = self.rete_tratto_percorsi.coord_to_linear(p)
		return {
			'da_fermata': dist_tratto,
			'da_capolinea': dist_tratto + self.s.distanza_da_partenza,
		}

	def elimina_veicolo(self, v):
		id_veicolo = v.id_veicolo
		if id_veicolo in self.veicoli:
			del self.veicoli[id_veicolo]

	def distanza_a_capolinea(self, dist_succ):
		"""
		Restituisce la distanza fino al capolinea finale

		:param dist_succ: distanza alla fine del tratto
		:return: distanza al capolinea finale
		"""
		return self.rete_percorso.dist - self.s.distanza_da_partenza - self.rete_tratto_percorsi.dist + dist_succ


class ReteVeicolo(object):
	def __init__(self, id_veicolo, dotazioni=None):
		object.__init__(self)
		self.id_veicolo = id_veicolo
		self.posizione = None
		self.posizione_interpolata = None
		# self.distanza_capolinea = None
		# self.distanza_successiva = None
		# self.posizione.tratto_percorso = None
		self.ultimo_aggiornamento = None
		self.ultima_interpolazione = None
		self.a_capolinea = None
		self.orario_partenza_capolinea = None
		self.stato_occupazione = None
		# self.punto = None
		if dotazioni is None:
			self.dotazioni = {
				'pedana': False,
				'aria': False,
				'moby': False,
				'meb': False,
			}
		else:
			self.dotazioni = dotazioni
		self.orario_inizio_corsa = None

	def serializza_dinamico(self):
		v = self.posizione.get_dettagli(True)
		return {
			'type': 'ReteVeicolo',
			'id': self.id_veicolo,
			'distanza_capolinea': v['distanza_capolinea_finale'],
			'distanza_successiva': v['distanza_fine_tratto'],
			'tratto_percorso': v['tratto_percorso'],
			'ultimo_aggiornamento': self.ultimo_aggiornamento,
			'ultima_interpolazione': self.ultima_interpolazione,
			'stato_occupazione': self.stato_occupazione,
			'a_capolinea': self.a_capolinea,
			'dotazioni': self.dotazioni,
			'punto': (v['x'], v['y']),
			'orario_inizio_corsa': self.orario_inizio_corsa,
			'orario_partenza_capolinea': self.orario_partenza_capolinea,
		}

	def log_su_db(self):
		v = self.posizione.get_dettagli(True)
		lon, lat = gbfe_to_wgs84(v['x'], v['y'])
		LogPosizioneVeicolo(
			id_veicolo=self.id_veicolo,
			id_percorso=v['tratto_percorso'].rete_percorso.id_percorso,
			orario=self.ultimo_aggiornamento,
			distanza_capolinea=v['distanza_capolinea_finale'],
			lon=lon,
			lat=lat,
			sistema=settings.MERCURY_GIANO,
		).save()

	def deserializza_dinamico(self, rete, res):
		percorso = rete.tratti_percorso[res['tratto_percorso']].rete_percorso
		dist = res['distanza_capolinea']
		self.posizione = PosizioneVeicolo.from_dist(percorso, dist, True)
		# self.distanza_capolinea = dist
		# self.distanza_successiva = v['distanza_fine_tratto']
		# self.posizione.tratto_percorso = rete.tratti_percorso[res['tratto_percorso']]
		self.ultimo_aggiornamento = res['ultimo_aggiornamento']
		self.ultima_interpolazione = res['ultima_interpolazione']
		self.stato_occupazione = res['stato_occupazione']
		self.a_capolinea = res['a_capolinea']
		self.dotazioni = res['dotazioni']
		# self.punto = res['punto']
		if 'orario_inizio_corsa' in res:
			self.orario_inizio_corsa = res['orario_inizio_corsa']
		if 'orario_partenza_capolinea' in res:
			self.orario_partenza_capolinea = res['orario_partenza_capolinea']
		else:
			self.orario_partenza_capolinea = None

	def aggiorna_posizione(
		self,
		posizione,
		a_capolinea,
		propaga=True,
		ultimo_aggiornamento=None,
		orario_partenza_capolinea=None,
		stato_occupazione=None,
	):
		"""
		Aggiorna la posizione del veicolo.

		Se punto=None, calcola le coordinate in base alla posizione linearizzata
		"""
		percorso = posizione.tratto_percorso.rete_percorso

		variata_corsa = False

		if self.orario_inizio_corsa is None:
			variata_corsa = True

		if self.posizione is not None:
			old_percorso = self.posizione.tratto_percorso.rete_percorso
			if percorso != old_percorso:
				self.elimina_da_percorso()
				variata_corsa = True
			elif (a_capolinea and not self.a_capolinea) or posizione - self.posizione < - MAX_ARRETRAMENTO_MANTENIMENTO_CORSA:
				variata_corsa = True

		if variata_corsa:
			if a_capolinea:
				self.orario_inizio_corsa = orario_partenza_capolinea
			else:
				self.orario_inizio_corsa = datetime.now() if ultimo_aggiornamento is None else ultimo_aggiornamento

		percorso.veicoli[self.id_veicolo] = self
		old_tratto = None
		if self.posizione is not None:
			old_tratto = self.posizione.tratto_percorso
			if posizione.tratto_percorso != old_tratto and self.id_veicolo in old_tratto.veicoli:
				del old_tratto.veicoli[self.id_veicolo]
		if old_tratto != posizione.tratto_percorso:
			posizione.tratto_percorso.veicoli[self.id_veicolo] = self

		self.posizione = posizione
		self.ultimo_aggiornamento = datetime.now() if ultimo_aggiornamento is None else ultimo_aggiornamento
		self.ultima_interpolazione = self.ultimo_aggiornamento
		self.a_capolinea = a_capolinea
		self.orario_partenza_capolinea = orario_partenza_capolinea
		self.stato_occupazione = stato_occupazione
		if propaga:
			self.propaga_su_fermate()

	def aggiorna_posizione_interpolata(self, tratto_percorso, distanza_precedente, ultima_interpolazione):
		# TODO: Rivedere
		tpi = tratto_percorso.rete_tratto_percorsi
		self.distanza_successiva = tpi.dist - distanza_precedente
		percorso = tratto_percorso.rete_percorso
		self.distanza_capolinea = percorso.dist - tratto_percorso.s.distanza_da_partenza + distanza_precedente
		if self.posizione.tratto_percorso != tratto_percorso:
			del self.posizione.tratto_percorso.veicoli[self.id_veicolo]
			self.posizione.tratto_percorso.veicoli[self.id_veicolo] = self
		self.ultima_interpolazione = ultima_interpolazione
		self.get_punto()

	def get_punto(self):
		"""
		A partire dalla posizione linearizzata, calcola le coordinate occupate dal veicolo
		"""
		v = self.posizione.get_dettagli()
		return v['x'], v['y']

	# def calcola_punto(self):
	# 	self.punto = self.get_punto()

	def reset_fermate(self, a_fermata=None):
		"""
		Cancella gli arrivi del veicolo corrente dal capolinea di partenza fino alla fermata indicata, inclusa.

		Se non è indicata una fermata, cancella su tutto il percorso.
		"""
		if a_fermata is None:
			a_fermata = self.posizione.tratto_percorso.rete_percorso.tratti_percorso[-1].t
		while a_fermata is not None:
			a_fermata.elimina_veicolo(self)
			tp = a_fermata.tratto_percorso_precedente
			if tp is not None:
				tp.elimina_veicolo(self)
				a_fermata = tp.s
			else:
				a_fermata = None

	def elimina_da_percorso(self):
		if self.posizione is not None:
			old_percorso = self.posizione.tratto_percorso.rete_percorso
			self.reset_fermate()
			if self.id_veicolo in old_percorso.veicoli:
				del old_percorso.veicoli[self.id_veicolo]
			self.posizione = None

	def propaga_su_fermate(self):
		tpo = self.posizione.tratto_percorso
		self.reset_fermate(tpo.s)
		numero = 0
		tempo = self.orario_partenza_capolinea if self.a_capolinea else datetime.now()
		while tpo is not None:
			numero += 1
			fermata = tpo.t
			fermata.elimina_veicolo(self)
			tpi = tpo.rete_tratto_percorsi
			dist = tpi.dist
			velocita = tpi.get_velocita()
			if tempo is not None and velocita > 0:
				if numero == 1:
					v = self.posizione.get_dettagli()
					d = v['distanza_fine_tratto']
					if d < 0:
						d = dist / 2
					tempo = tempo + timedelta(seconds=(d / velocita))
				else:
					tempo = tempo + timedelta(seconds=(dist / velocita))
			else:
				tempo = None
			fermata.add_arrivo(self, tempo, numero)
			tpo = fermata.tratto_percorso_successivo

	def is_valido(self):
		if self.posizione.tratto_percorso is None:
			return False
		if self.ultimo_aggiornamento is None or datetime.now() - self.ultimo_aggiornamento > TIMEOUT_VALIDITA_VEICOLO:
			return False
		return True

	def get_arrivi(self):
		"""
		Restituisce gli arrivi alle fermate successive
		"""
		out = {}
		n = datetime.now()
		if not self.a_capolinea:
			t = self.posizione.tratto_percorso
			v = self.posizione.get_dettagli()
			d = v['distanza_fine_tratto']
			dt = (n - self.ultimo_aggiornamento).seconds
			# Scalo
			while t is not None and dt > 0:
				v = t.rete_tratto_percorsi.get_velocita()
				if v < 0:
					return {}
				tempo = d / v
				if tempo < dt:
					dt -= tempo
					t = t.t.tratto_percorso_successivo
					if t is not None:
						d = t.rete_tratto_percorsi.dist
				else:
					d -= v * dt
					dt = 0
			tempo = 0
		else:
			# A capolinea
			if self.orario_partenza_capolinea is None:
				return {}
			t = self.posizione.tratto_percorso
			v = self.posizione.get_dettagli()
			d = v['distanza_fine_tratto']
			if self.orario_partenza_capolinea > n:
				tempo = (self.orario_partenza_capolinea - n).seconds
			else:
				tempo = 0
			# out[t.s.rete_palina.id_palina] = self.orario_partenza_capolinea
			out['departure'] = self.orario_partenza_capolinea

		# Determino posizioni
		i = 1
		tempo_iniziale = tempo
		while t is not None:
			v = t.rete_tratto_percorsi.get_velocita()
			if v < 0:
				t = None
				break
			tempo += d / v
			# Protezione da malfunzionamenti algoritmo previsione causati da dati di input errati:
			# in caso di tempi anomali, rendi tempo non disponibile
			if (tempo - tempo_iniziale) > (10 + 4 * i) * 60:
				t = None
				break
			f = t.t
			out[f.rete_palina.id_palina] = n + timedelta(seconds=tempo)
			t = f.tratto_percorso_successivo
			i += 1
			if t is not None:
				d = t.rete_tratto_percorsi.dist
		return out

	def get_info(self, get_arrivi=True, get_distanza=False):
		v = self.posizione.get_dettagli(True)
		out = {
			'id_veicolo': self.id_veicolo,
			'id_prossima_palina': self.posizione.tratto_percorso.t.rete_palina.id_palina if not self.a_capolinea else self.posizione.tratto_percorso.s.rete_palina.id_palina,
			'self.a_capolinea': self.a_capolinea,
			'a_capolinea': self.a_capolinea,
			'x': v['x'],
			'y': v['y'],
			'orario_partenza_capolinea': self.orario_partenza_capolinea,
			'stato_occupazione': self.stato_occupazione,
		}
		if get_distanza:
			out['distanza_capolinea'] = v['distanza_capolinea_finale']
		if get_arrivi:
			out['arrivi'] = self.get_arrivi()
		return out


def get_parametri_costo_pedonale(a0, a1, exp):
	c0 = a0
	c1 = (a1 - c0) / math.pow(1000, exp)
	return (c0, c1, exp)


class ReteZtl(object):
	def __init__(self, codice, nome, orari):
		self.id_ztl = codice
		self.nome = nome
		# Orari è una lista di tuple (orario_inizio, orario_fine), che rappresentano
		# gli orari in cui la ZTL è attiva nei prossimi n giorni
		self.orari = orari

	def attesa(self, t, rev=False):
		"""
		Restituisce None se la ztl non è attiva, oppure il tempo di attesa in secondi
		"""
		for o in self.orari:
			if t >= o[0] and t < o[1]:
				if not rev:
					return (o[1] - t).seconds
				else:
					return (t - o[0]).seconds
		return None


class Rete(object):
	def __init__(self):
		object.__init__(self)
		self.paline = {}
		self.tratti_percorsi = {}
		self.tratti_percorso = {}
		self.percorsi = {}
		# Capilinea: dizionario {id_palina: [percorsi]}
		self.capilinea = {}
		self.fermate = {}
		self.fermate_da_palina = {}
		self.veicoli = {}
		self.ztl = {}
		# Dizionario che associa le pk degli oggetti di tipo StatPeriodiAggregazione agli indici degli elementi
		# che contengono il tempo
		self.indice_stat_periodi_aggregazione = {}
		self.velocita_medie = []
		self.percorrenze_calcolate = False
		# Dizionario avente per chiave una linea, e elementi la lista delle linee ad essa equivalenti
		# ai fini dell'esclusione dal calcola percorso
		self.linee_equivalenti = {}
		self.ultimo_aggiornamento = None
		self.geocoder = None
		self.random = Random()
		# Mapping per decodificare il GTFS real time
		self.trip_to_id_percorso = None
		self.gtfs_update_in_progress = False
		self.gtfs_rt_last_update = None
		self.gtfs_last_mapping = config.GIANO_DATA_MAPPING_RETE
		self.gtfs_alerts = None
		# Caches last call to self.get_stat_percorsi()
		self.stat_percorsi = {}

	def gtfs_update(self):
		if self.gtfs_update_in_progress or not settings.GTFS_ST_CHECK_FOR_UPDATES:
			return
		print("Looking for static GTFS update")
		self.gtfs_update_in_progress = True
		try:
			d = parse_static.download_gtfs_and_map(self.gtfs_last_mapping, True)
			if d is not None:
				print("Update found, applying")
				# calcola_frequenze()
				# Schedule application server restart
				dc = DaemonControl.objects.get(name=settings.MERCURY_GIANO)
				dc.restart_all_daemons()
			else:
				self.gtfs_update_in_progress = False
		except:
			traceback.print_exc()
		# self.gtfs_update_in_progress = False
		print("Static GTFS update check completed")

	def serializza_dinamico_interno(self):
		return {
			'type': 'Rete',
			'id': '',
			'ultimo_aggiornamento': self.ultimo_aggiornamento,
		}

	def deserializza_dinamico_interno(self, res):
		self.ultimo_aggiornamento = res['ultimo_aggiornamento']

	def serializza_dinamico(self):
		out = []
		for id in self.paline:
			out.append(self.paline[id].serializza_dinamico())
		for id in self.tratti_percorsi:
			out.append(self.tratti_percorsi[id].serializza_dinamico())
		for id in self.fermate:
			out.append(self.fermate[id].serializza_dinamico())
		for id in self.veicoli:
			out.append(self.veicoli[id].serializza_dinamico())
		for id in self.percorsi:
			out.append(self.percorsi[id].serializza_dinamico())
		for id in self.tratti_percorso:
			out.append(self.tratti_percorso[id].serializza_dinamico())
		out.append(self.serializza_dinamico_interno())
		return out

	def serializza_dinamico_veicoli(self, percorrenze=True, veicoli=True):
		out = []
		if percorrenze:
			for id in self.tratti_percorsi:
				out.append(self.tratti_percorsi[id].serializza_dinamico())
		if veicoli:
			for id in self.veicoli:
				v = self.veicoli[id]
				out.append(v.serializza_dinamico())
			out.append(self.serializza_dinamico_interno())
		return out

	def deserializza_dinamico(self, res):
		for r in res:
			try:
				t = r['type']
				id = r['id']
				if t == 'RetePalina':
					self.paline[id].deserializza_dinamico(self, r)
				elif t == 'ReteTrattoPercorsi':
					self.tratti_percorsi[id].deserializza_dinamico(self, r)
				elif t == 'ReteFermata':
					self.fermate[id].deserializza_dinamico(self, r)
				elif t == 'ReteTrattoPercorso':
					self.tratti_percorso[id].deserializza_dinamico(self, r)
				elif t == 'ReteVeicolo':
					if not id in self.veicoli:
						self.veicoli[id] = ReteVeicolo(id)
					self.veicoli[id].deserializza_dinamico(self, r)
				elif t == 'RetePercorso':
					self.percorsi[id].deserializza_dinamico(self, r)
				elif t == 'Rete':
					self.deserializza_dinamico_interno(r)
				else:
					print "Tipo %s non riconosciuto" % t
			except Exception, e:
				print e

	def deserializza_dinamico_veicoli(self, res):
		for r in res:
			try:
				t = r['type']
				id = r['id']
				if t == 'ReteTrattoPercorsi':
					self.tratti_percorsi[id].deserializza_dinamico(self, r)
				elif t == 'ReteVeicolo':
					try:
						id_tratto = r['tratto_percorso']
						if id_tratto is None:
							self.invalida_bus(r['id'])
						else:
							tpo = self.tratti_percorso[id_tratto]
							posizione = PosizioneVeicolo(tpo, r['distanza_successiva'], True)
							self.aggiorna_posizione_bus(
								r['id'],
								posizione,
								r['a_capolinea'],
								r['dotazioni'],
								ultimo_aggiornamento=r['ultimo_aggiornamento'],
								orario_partenza_capolinea=r['orario_partenza_capolinea'],
							)
					except:
						logging.error('Errore aggiornamento posizione veicolo: %s' % traceback.format_exc())
				elif t == 'Rete':
					self.deserializza_dinamico_interno(r)
			except Exception, e:
				print e

		self.invalida_bus_obsoleti()

	def esporta_tratti_percorsi(self, filename, cond=None):
		"""
		Esporta i tratti percorsi che soddisfano la condizione cond

		L'esportazione avviene in formato pickle come lista di dizionari. Ogni tratto_percorsi
		ha il formato:
		{
			'id_palina_s': (string)
			'id_palina_t': (string)
			'geom': [list of (x, y)] # srid: 3004
			'tipo': (string)
		}
		:param filename: nome del file di output
		:param cond: condizione di selezione
		"""
		if cond is None:
			cond = lambda x: True
		out = []
		for tp in self.tratti_percorsi.values():
			if cond(tp):
				p = tp.percorsi.values()[0].rete_percorso
				out.append({
					'id_palina_s': tp.s.id_palina,
					'id_palina_t': tp.t.id_palina,
					'geom': tp.punti,
					'tipo': p.tipo,
				})
		with open(filename, 'w') as w:
			pickle.dump(out, w)

	def get_veicoli_tutti_percorsi(self, get_arrivi, get_distanza=False):
		ret = []
		for id_percorso in self.percorsi:
			vs = self.get_veicoli_percorso(id_percorso)
			out = []
			for v in vs:
				out.append(v.get_info(get_arrivi, get_distanza))
			ret.append({
				'id_percorso': id_percorso,
				'arrivi': out,
				'ultimo_aggiornamento': self.percorsi[id_percorso].tratti_percorso[-1].t.ultimo_aggiornamento
			})
		db.reset_queries()
		return ret

	# def genera_gtfs_rt(self, gtfs_static):
	# 	arrivi = {
	# 		'ultimo_aggiornamento': self.ultimo_aggiornamento,
	# 		'percorsi': self.get_veicoli_tutti_percorsi(True, True),
	# 	}
	# 	return None  # gtfs_rt.generate_gtfs_rt(self, arrivi, gtfs_static)

	def add_palina(self, id_palina, nome, soppressa=False, geom=None):
		p = RetePalina(id_palina, nome, soppressa)
		if geom:
			p.x, p.y = geom.x, geom.y

		self.paline[id_palina] = p
		return p

	def add_percorso(self, id_percorso, id_linea, tipo, descrizione, soppresso, gestore):
		p = RetePercorso(id_percorso, id_linea, tipo, descrizione, soppresso, gestore)
		self.percorsi[id_percorso] = p
		return p

	def add_fermata(self, id_fermata, id_palina, id_percorso):
		f = ReteFermata(id_fermata, self.paline[id_palina], self.percorsi[id_percorso], self)
		if id_fermata in self.fermate:
			print "FERMATA DUPLICATA", id_fermata
		self.fermate[id_fermata] = f
		self.fermate_da_palina[(id_palina,id_percorso)] = f
		return f

	def add_tratto_percorso(self, id_percorso, id_fermata_s, id_fermata_t):
		s = self.fermate[id_fermata_s]
		t = self.fermate[id_fermata_t]
		ps = s.rete_palina
		pt = t.rete_palina
		p = self.percorsi[id_percorso]
		c = (ps.id_palina, pt.id_palina)

		if c in self.tratti_percorsi:
			a = self.tratti_percorsi[c]
		else:
			a = ReteTrattoPercorsi(ps, pt, self)
			self.tratti_percorsi[c] = a
		tp = ReteTrattoPercorso(p, a, s, t)
		self.tratti_percorso[(id_fermata_s, id_fermata_t)] = tp
		return tp

	def add_capolinea(self, id_percorso, id_palina):
		if id_palina in self.capilinea:
			self.capilinea[id_palina].append(id_percorso)
		else:
			self.capilinea[id_palina] = [id_percorso]

	def add_ztl(self, codice, nome, orari):
		self.ztl[codice] = ReteZtl(codice, nome, orari)

	def log_tempi_attesa_percorsi(self):
		t = datetime.now()
		ora = datetime2time(t)
		data = datetime2date(t)
		if settings.CPD_LOG_PER_STATISTICHE:
			for id_percorso in self.percorsi:
				self.percorsi[id_percorso].log_tempo_attesa(data, ora)

	def aggiorna_arrivi(self, calcola_percorrenze=False, logging=False, aggiorna_arrivi=True, timeout=TIMEOUT_AGGIORNAMENTO_RETE):
		if aggiorna_arrivi:
			print "Aggiornamento arrivi!"
			self.dati_da_gtfs_rt()
			self.stat_percorsi = self.get_stat_percorsi()
			print "Aggiornamento arrivi completato!!"
		if calcola_percorrenze:
			print "Calcolo percorrenze archi"
			for k in self.percorsi:
				try:
					#print "Processo percorso %s" % self.percorsi[k].id_percorso
					self.percorsi[k].fv.process_data()
					self.percorsi[k].calcola_percorrenze()
				except:
					traceback.print_exc()
			for k in self.tratti_percorsi:
				try:
					self.tratti_percorsi[k].media_tempi_percorrenza(logging)
				except:
					traceback.print_exc()
			self.percorrenze_calcolate = True
			print "Calcolo percorrenze completato"
			print "Aggiorno alerts"
			self.gtfs_alerts = alerts.read_alerts()
			print "Alerts aggiornati"
			Thread(target=self.gtfs_update).start()
		# print "Log posizione veicoli"
		# plpvs = PercorsiLogPosizioneVeicolo.objects.all()
		# for plpv in plpvs:
		# 	id_percorso = plpv.id_percorso
		# 	if id_percorso in self.percorsi:
		# 		p = self.percorsi[id_percorso]
		# 		for id_veicolo in p.veicoli:
		# 			p.veicoli[id_veicolo].log_su_db()
		# print "Log posizione veicoli completato"
		if logging:
			print "Log tempi di attesa percorsi"
			self.log_tempi_attesa_percorsi()
			print "Log tempi attesa percorsi completato"
		self.ultimo_aggiornamento = datetime.now()

	def invalida_bus_obsoleti(self):
		for id_veicolo in self.veicoli:
			v = self.veicoli[id_veicolo]
			if not v.is_valido():
				v.elimina_da_percorso()

	def invalida_bus(self, id_veicolo):
		if id_veicolo in self.veicoli:
			self.veicoli[id_veicolo].elimina_da_percorso()

	def aggiorna_posizione_veicoli(self, forza_interpolazione=False):
		for id_percorso in self.percorsi:
			p = self.percorsi[id_percorso]
			p.aggiorna_posizione_veicoli(forza_interpolazione)

	def aggiorna_posizione_bus(
		self,
		id_veicolo,
		posizione,
		a_capolinea,
		dotazioni=None,
		propaga=True,
		ultimo_aggiornamento=None,
		orario_partenza_capolinea=None,
		stato_occupazione=None,
	):
		if not id_veicolo in self.veicoli:
			self.veicoli[id_veicolo] = ReteVeicolo(id_veicolo, dotazioni=dotazioni)
		self.veicoli[id_veicolo].aggiorna_posizione(
			posizione,
			a_capolinea,
			propaga,
			ultimo_aggiornamento=ultimo_aggiornamento,
			orario_partenza_capolinea=orario_partenza_capolinea,
			stato_occupazione=stato_occupazione,
		)
		return self.veicoli[id_veicolo]

	def elimina_veicolo_da_percorso(self, id_veicolo):
		if id_veicolo in self.veicoli:
			self.veicoli[id_veicolo].elimina_da_percorso()
			del self.veicoli[id_veicolo]

	# @djangotransaction.commit_on_success(using='gis')
	def dati_da_gtfs_rt(self):
		# print("Dati da GTFS rt")
		max_distanza = 100
		snap_dist_capolinea = config.CL_SNAP_DIST_CAPOLINEA
		coeff_velocita = config.CL_INTERPOL_COEFF_VELOCITA

		last_update = realtime.get_gtfs_rt_last_update()
		while last_update == self.gtfs_rt_last_update:
			print("Not yet")
			sleep(5)
			last_update = realtime.get_gtfs_rt_last_update()
		self.gtfs_rt_last_update = last_update

		print("GTFS Updated")
		now = datetime.now()
		today = date.today()
		veicoli = realtime.decode_vehicles(self.trip_to_id_percorso, realtime.read_vehicles())
		veicoli = list(veicoli)
		# print(veicoli)
		filtrati = 0
		per_tipo = defaultdict(list)
		for v in veicoli:
			v_fuori = False
			v_filtrato = False
			da_eliminare = False
			try:
				timestamp = v['timestamp']
				id_veicolo = v['vehicle_id']
				dt = now - timestamp
				if dt < TIMEOUT_VALIDITA_VEICOLO:
					id_percorso = v['id_percorso']
					progressiva = v['progressiva']
					a_capolinea = progressiva == 0
					if id_percorso in self.percorsi:
						percorso = self.percorsi[id_percorso]
						x, y = geomath.wgs84_to_gbfe(*v['coord'])
						posizione_veicolo, dist = PosizioneVeicolo.from_coord_and_stop_no(percorso, x, y, progressiva, 1, max_distanza)
						dettagli = posizione_veicolo.get_dettagli()
						distanza_capolinea_iniziale = dettagli['distanza_capolinea_iniziale']
						distanza_capolinea_finale = dettagli['distanza_capolinea_finale']

						if distanza_capolinea_iniziale < snap_dist_capolinea:
							# print("SNAP a capolinea!", id_percorso, distanza_capolinea_iniziale)
							a_capolinea = True

						if distanza_capolinea_finale > snap_dist_capolinea:
							dotazioni = {
								'meb': False,
								'aria': False,
								'moby': False,
								'pedana': False,
							}

							orario_partenza_capolinea = None
							if a_capolinea:
								orario_partenza_capolinea = mysql2datetime('{} {}'.format(date2mysql(today), v['start_time']))
								if orario_partenza_capolinea < now:
									orario_partenza_capolinea += timedelta(days=1)
								# posizione_veicolo.set_capolinea_iniziale()
								in_path = True
							else:
								in_path = posizione_veicolo.avanza_interpolando(dt, coeff_velocita, True)

							if in_path:
								self.aggiorna_posizione_bus(
									id_veicolo,
									posizione_veicolo,
									a_capolinea,
									dotazioni=dotazioni,
									ultimo_aggiornamento=now,
									orario_partenza_capolinea=orario_partenza_capolinea,
									stato_occupazione=v['occupancy_status'],
								)

							else:
								da_eliminare = True

							if dist is not None and dist <= max_distanza:
								# Aggiungo campione
								# print("Aggiunta veicolo")
								if not a_capolinea:
									percorso.fv.add(id_veicolo, timestamp, distanza_capolinea_finale)
							else:
								print "** Veicolo %s troppo distante, %f" % (id_veicolo, dist)
								pprint(v)
								filtrati += 1
								da_eliminare = True

							per_tipo[(v_fuori, v_filtrato)].append({'veicolo': v, 'distanza': dist})

						else:
							da_eliminare = True

					else:
						da_eliminare = True

				else:
					da_eliminare = True

			except:
				da_eliminare = True
				traceback.print_exc()
				logging.error('Errore aggiornamento posizione veicolo: %s' % traceback.format_exc())

			try:
				if da_eliminare:
					self.elimina_veicolo_da_percorso(id_veicolo)
			except:
				traceback.print_exc()
				logging.error('Errore eliminazione posizione veicolo: %s' % traceback.format_exc())

		print("Filtrati: ", filtrati)

	def costruisci_percorso_intersezione(self, id_percorso_1, id_percorso_2, id_percorso, id_linea, tipo, descrizione):
		try:
			p1 = self.percorsi[id_percorso_1]
			p2 = self.percorsi[id_percorso_2]
			pal1 = p1.get_paline()
			paline1 = set(pal1)
			paline2 = set(p2.get_paline())
			paline = paline1.intersection(paline2)
			p = self.add_percorso(id_percorso, id_linea, tipo, descrizione, False, p1.gestore)
			n = 0
			old_f = None
			for pa in pal1:
				if pa in paline:
					n += 1
					f = str(id_percorso) + str(n)
					self.add_fermata(f, pa.id_palina, id_percorso)
					if old_f is not None:
						self.add_tratto_percorso(id_percorso, old_f, f)
					old_f = f
			self.add_capolinea(id_percorso, pa.id_palina)
			# Frequenze
			for giorno_settimana in range(0, 7):
				for ora_inizio in range(0, 24):
					f1, oi1, of1 = p1.frequenza[giorno_settimana][ora_inizio]
					f2, oi2, of2 = p2.frequenza[giorno_settimana][ora_inizio]
					if f1 <= 0:
						f = f2
					elif f2 <= 0:
						f = f1
					else:
						f = (1 / (1 / f1 + 1 / f2))
					if oi1 == -1:
						oi = oi2
					elif oi2 == -1:
						oi = oi1
					else:
						oi = min(oi1, oi2)
					if of1 == -1:
						of = of2
					elif of2 == -1:
						of = of1
					else:
						of = max(of1, of2)
					p.frequenza[giorno_settimana][ora_inizio] = (f, oi, of)
			linee = [id_linea, p1.id_linea, p2.id_linea]
			for l in linee:
				self.linee_equivalenti[l] = linee
		except:
			m = "Errore nella costruzione del percorso intersezione: %s" % traceback.format_exc()
			logging.error(m)
			print m

	def costruisci_indice_periodi_aggregazione(self):
		# Inizializzazione indice
		ispa = self.indice_stat_periodi_aggregazione
		spas = StatPeriodoAggregazione.objects.all()
		# Costruzione indice
		n = 0
		for spa in spas:
			ispa[spa.pk] = n
			n += 1

	def get_zone_paline(self, versione=None):
		sql = """
			select id_palina, name
			from paline_palina P join areas A
				on st_contains(A.geom, P.geom)
			where min_versione <= %(n_versione)s and max_versione >= %(n_versione)s
		"""
		if versione is None:
			versione = VersionePaline.attuale()
		conn = db.connection
		cur = conn.cursor()
		cur.execute(sql, {'n_versione': versione.numero})
		out = {}
		for id_palina, name in cur:
			out[id_palina] = name
		return out

	def assegna_zone_a_capilinea(self, versione=None):
		zone = self.get_zone_paline(versione)
		for id_percorso in self.percorsi:
			r = self.percorsi[id_percorso]
			s = r.tratti_percorso[0].s.rete_palina
			t = r.tratti_percorso[-1].t.rete_palina
			s.zona = zone.get(s.id_palina)
			t.zona = zone.get(t.id_palina)

	def carica(self, retina=False, versione=None, rete_base=None):
		"""
		Genera e restituisce una rete a partire dal database

		bool retina: se True, carica una versione ridotta della rete a scopo di test
		datetime versione: se definita, timestamp dell'inizio di validità della versione
		Rete rete_base: se definita, rete (precedente) da cui copiare la geometria degli oggetti non modificati nella nuova rete
		"""

		if versione is None:
			versione_paline = VersionePaline.attuale()
			self.inizio_validita = versione_paline.inizio_validita
		else:
			versione_paline = VersionePaline.by_date(versione)
			self.inizio_validita = versione
		inizio_validita = datetime2compact(self.inizio_validita)
		path_rete = os.path.join(settings.TROVALINEA_PATH_RETE, inizio_validita)
		if not os.path.exists(path_rete):
			os.mkdir(path_rete)
		rete_serializzata_file = os.path.join(path_rete, 'rete%s.v3.dat' % ('_mini' if retina else ''))

		try:
			f = open(rete_serializzata_file, 'rb')
			res = pickle.loads(f.read())
			print "Carico rete serializzata"
			for tipo, param in res['add']:
				getattr(self, 'add_%s' % tipo)(*param)
			for p in res['paline']:
				self.paline[p['id']].deserializza(p)
			for p in res['percorsi']:
				self.percorsi[p['id']].deserializza(p)
			for p in res['tratti_percorsi']:
				self.tratti_percorsi[p['id']].deserializza(p)
			for id_percorso in self.percorsi:
				self.percorsi[id_percorso].set_punti()
			self.velocita_medie = res['velocita_medie']
			self.indice_stat_periodi_aggregazione = res['indice_stat_periodi_aggregazione']
			f.close()

		except IOError:
			print "Costruisco rete da database"
			r = self
			ser = []
			print "Carico paline"
			if retina:
				ps = Palina.objects.by_date(versione).filter(fermata__percorso__linea__id_linea__in=LINEE_MINI)
			else:
				ps = Palina.objects.by_date(versione).all()
			for p in ps:
				r.add_palina(p.id_palina, p.nome, p.soppressa, p.geom)
				ser.append(('palina', (p.id_palina, p.nome, p.soppressa, p.geom)))
			print "Carico percorsi"
			ps = Percorso.objects.by_date(versione).all()
			if retina:
				ps = Percorso.objects.by_date(versione).filter(linea__id_linea__in=LINEE_MINI)
			for p in ps:
				percorso_rete = r.add_percorso(p.id_percorso, p.linea.id_linea, p.linea.tipo, p.descrizione, p.soppresso, p.linea.gestore.nome)
				ser.append(('percorso', (p.id_percorso, p.linea.id_linea, p.linea.tipo, p.descrizione, p.soppresso, p.linea.gestore.nome)))
				# Fermate
				old_f = None
				fs = Fermata.objects.by_date(versione).filter(percorso=p).order_by('progressiva')
				for f in fs:
					id_fermata = "%s|%d" % (p.id_percorso, f.progressiva)
					r.add_fermata(id_fermata, f.palina.id_palina, p.id_percorso)
					ser.append(('fermata', (id_fermata, f.palina.id_palina, p.id_percorso)))
					if old_f is not None:
						r.add_tratto_percorso(p.id_percorso, old_id_fermata, id_fermata)
						ser.append(('tratto_percorso', (p.id_percorso, old_id_fermata, id_fermata)))
					old_f = f
					old_id_fermata = id_fermata
				if not percorso_rete.is_circolare():
					r.add_capolinea(p.id_percorso, old_f.palina.id_palina)
					ser.append(('capolinea', (p.id_percorso, old_f.palina.id_palina)))
				else:
					r.add_capolinea(p.id_percorso, percorso_rete.tratti_percorso[-1].s.rete_palina.id_palina)
					ser.append(('capolinea', (p.id_percorso, percorso_rete.tratti_percorso[-1].s.rete_palina.id_palina)))
				# Frequenze
				fs = FrequenzaPercorso.objects.filter(id_percorso=p.id_percorso)
				for f in fs:
					percorso_rete.frequenza[f.giorno_settimana][f.ora_inizio] = (f.frequenza, f.da_minuto, f.a_minuto)

			print "Carico coordinate percorsi"
			tps = TrattoPercorsi.objects.by_date(versione).all().select_related()
			for tp in tps:
				try:
					id_palina_s = tp.palina_s.id_palina
					id_palina_t = tp.palina_t.id_palina
					p = r.tratti_percorsi[(id_palina_s, id_palina_t)]
					p.set_punti(list(tp.geom))
					p.set_dist(tp.geom.length)
					p.sposta_paline_su_percorso()
				except Exception:
					pass
					#print id_palina
			for id_percorso in self.percorsi:
				self.percorsi[id_percorso].set_punti()
			print "Carico zone capilinea"
			self.assegna_zone_a_capilinea(versione_paline)
			print "Carico statistiche"
			self.costruisci_indice_periodi_aggregazione()
			self.carica_stat_percorrenze_archi()
			self.carica_stat_attese_bus()
			print "Serializzo rete"
			f = open(rete_serializzata_file, 'wb')
			f.write(pickle.dumps({
				'add': ser,
				'paline': [self.paline[id].serializza() for id in self.paline],
				'percorsi': [self.percorsi[id].serializza() for id in self.percorsi],
				'tratti_percorsi': [self.tratti_percorsi[id].serializza() for id in self.tratti_percorsi],
				'velocita_medie': self.velocita_medie,
				'indice_stat_periodi_aggregazione': self.indice_stat_periodi_aggregazione,
			}, 2))
			f.close()
		print "Elaboro mapping fermate soppresse"
		for id_percorso in self.percorsi:
			self.percorsi[id_percorso].init_mapping_fermate_non_soppresse()
		print "Carico ZTL"
		today = date.today()
		zs = orari_per_ztl(today, today + timedelta(days=settings.CPD_GIORNI_LOOKAHEAD))
		for ztl_id in zs:
			z = zs[ztl_id]
			self.add_ztl(ztl_id, z['toponimo'], z['fasce'])
		print "Calcolo distanze"
		for id_percorso in self.percorsi:
			try:
				self.percorsi[id_percorso].calcola_distanze()
			except:
				print "Errore nel calcolo distanze sul percorso ", id_percorso
				# traceback.print_exc()
		print "Carico mapping GTFS"
		d = {}
		for gt in GtfsTrip.objects.all():
			d[gt.trip_id] = gt.id_percorso
		self.trip_to_id_percorso = d
		db.reset_queries()
		print "Init stat percorsi"
		self.stat_percorsi = self.init_stat_percorsi()

	def valida_distanze(self):
		"""
		Verifica che sia definita la distanza su tutti i tratti di percorsi
		"""
		out = ""
		for id in self.tratti_percorsi:
			t = self.tratti_percorsi[id]
			if t.dist is None:
				out += "%s - %s" % (t.s.id_palina, t.t.id_palina)
				out += " (percorsi: %s)\n" % ", ".join([x.rete_percorso.id_percorso for x in t.tratti_percorso])
		if out != "":
			return "Distanza non definita negli shapefile per i seguenti archi tra paline:\n" + out
		return ""

	def carica_stat_percorrenze_archi(self):
		print "Carico statistiche tempi di percorrenza archi"
		spas = StatPeriodoAggregazione.objects.all()
		n = len(self.indice_stat_periodi_aggregazione)
		spazio = [0.0 for x in range(n)]
		tempo = [0.0 for x in range(n)]
		self.velocita_medie = [-1 for x in range(n)]
		for k in self.tratti_percorsi:
			self.tratti_percorsi[k].tempo_percorrenza_stat_orari = [-1 for x in range(n)]
		stas = StatTempoArco.objects.all().order_by('id_palina_s', 'id_palina_t', '-periodo_aggregazione__livello')
		ips, ipt = None, None
		for sta in stas:
			ips2, ipt2 = sta.id_palina_s, sta.id_palina_t
			if (ips2, ipt2) != (ips, ipt):
				ips, ipt = ips2, ipt2
				try:
					tp = self.tratti_percorsi[(ips, ipt)]
					distanza = tp.dist
					if distanza is None:
						tp = None
				except:
					tp = None
			if tp is not None and distanza is not None:
				indice = self.indice_stat_periodi_aggregazione[sta.periodo_aggregazione.pk]
				tempo_vero = distanza / sta.tempo # sta.tempo è una velocità
				tp.tempo_percorrenza_stat_orari[indice] = tempo_vero
				spazio[indice] += distanza
				tempo[indice] += tempo_vero
		for i in range(n):
			#print i, spazio[i], tempo[i]
			if tempo[i] > 0:
				#print i, spazio[i] / tempo[i]
				self.velocita_medie[i] = spazio[i] / tempo[i]

	def carica_stat_attese_bus(self):
		print "Carico statistiche tempi di attesa bus"
		spas = StatPeriodoAggregazione.objects.all()
		n = len(self.indice_stat_periodi_aggregazione)
		for k in self.percorsi:
			self.percorsi[k].tempo_stat_orari = [-1 for x in range(n)]
		staps = StatTempoAttesaPercorso.objects.all().order_by('id_percorso', '-periodo_aggregazione__livello')
		idp = None
		for stap in staps:
			idp2 = stap.id_percorso
			if idp2 != idp:
				idp = idp2
				try:
					p = self.percorsi[idp]
				except:
					p = None
			if p is not None:
				indice = self.indice_stat_periodi_aggregazione[stap.periodo_aggregazione.pk]
				p.tempo_stat_orari[indice] = stap.tempo

	def get_veicoli_percorso(self, id_percorso):
		percorso = self.percorsi[id_percorso]
		# percorso.aggiorna_posizione_veicoli()
		veicoli = []
		for id_veicolo in percorso.veicoli:
			v = percorso.veicoli[id_veicolo]
			if v.is_valido():
				veicoli.append(v)
		return veicoli

	def init_stat_percorsi(self):
		"""
		Initializes statistics about percorsi

		Map each id_percorso to a dictionary with the following keys:
		- departures: 0 (initially)
		- vehicles: (initially)
		:return: dictionary
		"""
		out = {}
		for id_percorso in self.percorsi:
			out[id_percorso] = {
				'departures': 0,
				'vehicles': 0,
			}
		return out

	def get_stat_percorsi(self):
		"""
		Compute and return statistics about percorsi

		Map each id_percorso to a dictionary with the following keys:
		- departures: count of hourly departures in time [t - 20min, t + 40min]
		- vehicles: count of running vehicles
		:return: dictionary
		"""
		dep = PartenzeCapilinea.count_departures_by_route_id()
		out = {}
		for id_percorso in self.percorsi:
			out[id_percorso] = {
				'departures': dep.get(id_percorso, 0),
				'vehicles': len(self.get_veicoli_percorso(id_percorso)),
			}
		return out

	def get_indici_periodi_attivi(self, dt):
		"""
		Restituisce una array con gli indici dei periodi di aggregazione attivi nell'orario dt.

		Gli indici sono ordinati in ordine decrescente di granularità.
		"""
		wd = Festivita.get_weekday(dt)
		wdd = {'wd%d' % wd: True}
		spas = StatPeriodoAggregazione.objects.filter(
			ora_inizio__lte=dt,
			ora_fine__gt=dt,
			**wdd
		).order_by('livello')
		return [self.indice_stat_periodi_aggregazione[spa.pk] for spa in spas]

	def get_opzioni_calcola_percorso(
		self,
		metro,
		bus,
		fc,
		fr,
		piedi,
		dt=None,
		primo_tratto_bici=False,
		linee_escluse=None,
		auto=False,
		carpooling=False,
		carpooling_vincoli=None,
		teletrasporto=False,
		carsharing=False,
		ztl=None,
		tpl=False,
		bici_sul_tpl=False,
	):
		"""
		Restituisce le opzioni di calcolo del percorso

		metro, bus, fc, fr: boolean
		piedi: 0 (lento), 1 (medio) o 2 (veloce)
		dt: data e ora di calcolo
		"""
		if dt is None:
			dt = datetime.now()
		if linee_escluse is None:
			linee_escluse = set([])
		c0, c1, exp = get_parametri_costo_pedonale(
			[config.CPD_PENAL_PEDONALE_0_0, config.CPD_PENAL_PEDONALE_0_1, config.CPD_PENAL_PEDONALE_0_2][piedi],
			[config.CPD_PENAL_PEDONALE_1_0, config.CPD_PENAL_PEDONALE_1_1, config.CPD_PENAL_PEDONALE_1_2][piedi],
			[config.CPD_PENAL_PEDONALE_EXP_0, config.CPD_PENAL_PEDONALE_EXP_1, config.CPD_PENAL_PEDONALE_EXP_2][piedi],
		)

		if teletrasporto:
			heuristic_speed = 99999999
		elif carpooling or auto:
			heuristic_speed = 33.3
		else:
			heuristic_speed = 16.0

		fermate_escluse = {fs.id_fermata for fs in FermataSospesa.objects.all()}

		opt = {
			'metro': metro and not auto,
			'bus': bus and not auto,
			'fc': fc and not auto,
			'fr': fr and not auto,
			'v_piedi': [config.CPD_PIEDI_0, config.CPD_PIEDI_1, config.CPD_PIEDI_2][piedi],
			'v_bici': [config.CPD_BICI_0, config.CPD_BICI_1, config.CPD_BICI_2][piedi],
			't_sal_bus': config.CPD_T_SAL_BUS,
			't_disc_bus': config.CPD_T_DISC_BUS,
			't_sal_metro': config.CPD_T_SAL_METRO,
			't_disc_metro': config.CPD_T_DISC_METRO,
			't_sal_treno': config.CPD_T_SAL_TRENO,
			't_disc_treno': config.CPD_T_DISC_TRENO,
			't_sal_fc': config.CPD_T_SAL_FC,
			't_disc_fc': config.CPD_T_DISC_FC,
			't_disc_bici': config.CPD_T_DISC_BICI,
			't_interscambio': config.CPD_T_INTERSCAMBIO,
			'indici_stat': self.get_indici_periodi_attivi(dt),
			'giorno': dt.day,
			'wd_giorno': Festivita.get_weekday(dt, compatta_feriali=True),
			'wd_giorno_succ': Festivita.get_weekday(dt, True, True),
			'penalizzazione_auto': config.CPD_PENALIZZAZIONE_AUTO if not carsharing else config.CPD_PENALIZZAZIONE_CAR_SHARING,
			'penalizzazione_bus': config.CPD_PENALIZZAZIONE_BUS,
			'penalizzazione_metro': config.CPD_PENALIZZAZIONE_METRO,
			'penalizzazione_fc': config.CPD_PENALIZZAZIONE_FC,
			'penalizzazione_treno': config.CPD_PENALIZZAZIONE_TRENO,
			'incentivo_capolinea': config.CPD_INCENTIVO_CAPOLINEA,
			'penal_pedonale_0': c0,
			'penal_pedonale_1': c1,
			'penal_pedonale_exp': exp,
			'primo_tratto_bici': primo_tratto_bici,
			't_bici_cambio_strada': config.CPD_BICI_CAMBIO_STRADA,
			'linee_escluse': linee_escluse,
			'fermate_escluse': fermate_escluse,
			'auto': auto,
			'car_pooling': (not auto) and carpooling,
			'carpooling_vincoli': carpooling_vincoli,
			'carsharing': carsharing,
			'teletrasporto': teletrasporto,
			'rete': self,
			'ztl': set() if ztl is None else ztl,
			'tpl': tpl,
			'bici_sul_tpl': bici_sul_tpl,
			'rev': False,
			'heuristic_speed': heuristic_speed,
		}
		return opt


class Aggiornatore(Thread):
	"""
	Aggiornatore dinamico della rete
	"""
	def __init__(self, rete, intervallo, cicli_calcolo_percorrenze=6, cicli_logging=24, aggiorna_arrivi=True, gtfs_rt_handler=None, gtfs_static=None):
		Thread.__init__(self)
		self.rete = rete
		self.intervallo = intervallo
		self.ultimo_aggiornamento = None
		self.stopped = False
		self.cicli_calcolo_percorrenze = cicli_calcolo_percorrenze
		self.ciclo_calcolo_percorrenze = -1
		self.cicli_logging = cicli_logging
		self.ciclo_logging = 0
		self.aggiorna_arrivi = aggiorna_arrivi
		self.gtfs_rt_handler = gtfs_rt_handler
		self.gtfs_static = gtfs_static
		self.mercury = Mercury(settings.MERCURY_GIANO)

	def stop(self):
		self.stopped = True

	def run(self):
		while not self.stopped:
			if self.ultimo_aggiornamento is not None:
				t1 = self.ultimo_aggiornamento + self.intervallo
				t2 = datetime.now()
				if t1 > t2:
					diff = (t1 - t2).seconds
					sleep(diff)
			self.ultimo_aggiornamento = datetime.now()
			try:
				print "Inizio aggiornamento arrivi, ciclo {} su {}".format(self.ciclo_calcolo_percorrenze + 1, self.cicli_calcolo_percorrenze)
				self.ciclo_calcolo_percorrenze = (self.ciclo_calcolo_percorrenze + 1) % self.cicli_calcolo_percorrenze
				self.ciclo_logging = (self.ciclo_logging + 1) % self.cicli_logging
				aggiorna_percorrenze = self.ciclo_calcolo_percorrenze == 0
				self.rete.aggiorna_arrivi(aggiorna_percorrenze, self.ciclo_logging == 0, aggiorna_arrivi=self.aggiorna_arrivi)
				self.ultimo_aggiornamento = datetime.now()
				print "Fine aggiornamento arrivi"
				# print "Serializzazione"
				# self.mercury.async_all_stored('deserializza_dinamico_veicoli_stored', self.rete.serializza_dinamico_veicoli(aggiorna_percorrenze))
				# print "Serializzazione completata"
				# if self.gtfs_rt_handler is not None:
				# 	print "Generazione GTFS Real Time"
				# 	g, g_vehicles = self.rete.genera_gtfs_rt(self.gtfs_static)
				# 	print "Attivazione GTFS Real Time"
				# 	self.gtfs_rt_handler(g, g_vehicles)
				# 	print "GTFS Real Time generato e attivato"

				# if self.ciclo_calcolo_percorrenze == 0:
				# 	print "Mapping id veicoli"
				# 	map_id_veicolo.map_veicoli(self.rete)
				# 	print "Mapping id veicoli completato"

			except Exception, e:
				logging.error(traceback.format_exc())
		print "Stoppato"


class AggiornatoreDownload(Thread):
	"""
	Aggiornatore dinamico della rete. Scarica periodicamente la rete serializzata.
	"""
	def __init__(self, rete, intervallo, cicli_logging=24):
		Thread.__init__(self)
		self.rete = rete
		self.intervallo = intervallo
		self.stopped = False
		self.cicli_logging = cicli_logging

	def stop(self):
		self.stopped = True

	def run(self):
		sa = xmlrpclib.Server('%s/ws/xml/autenticazione/1' % settings.WS_BASE_URL)
		sp = xmlrpclib.Server('%s/ws/xml/paline/7' % settings.WS_BASE_URL)
		token = None
		ultimo_aggiornamento = None
		ciclo = 0
		while not self.stopped:
			try:
				print "Verifico ora ultimo aggiornamento rete dinamica"
				if token is None:
					token = sa.autenticazione.Accedi(settings.DEVELOPER_KEY, '')
				res = sp.paline.GetOrarioUltimoAggiornamentoArrivi(token)
				ua = res['risposta']['ultimo_aggiornamento']
				if ultimo_aggiornamento is None or ua > ultimo_aggiornamento:
					print "Scarico ultimo aggiornamento"
					res = sp.paline.GetStatoRete(token)['risposta']
					ultimo_aggiornamento = res['ultimo_aggiornamento']
					print "Deserializzo ultimo aggiornamento"
					self.rete.deserializza_dinamico(pickle.loads(res['stato_rete'].data))
					print "Rete dinamica aggiornata"
					if settings.CPD_LOG_PER_STATISTICHE:
						print "Log per statistiche"
						ciclo += 1
						if ciclo >= self.cicli_logging:
							ciclo = 0
							dt = datetime.now()
							d = datetime2date(dt)
							t = datetime2time(dt)
							for k in self.rete.tratti_percorsi:
								self.rete.tratti_percorsi[k].log_per_statistiche(dt)
							for id_percorso in self.rete.percorsi:
								self.rete.percorsi[id_percorso].log_tempo_attesa(d, t)

						print "Log effettuato"
			except:
				print "Errore aggiornamento rete dinamica"
				traceback.print_exc()
				token = None
			sleep(self.intervallo.seconds)


def differenza_datetime_secondi(t1, t2):
	if t1 > t2:
		return (t1 - t2).seconds
	return -((t2 - t1).seconds)


# Rete su grafo
class NodoRisorsa(Nodo):
	def __init__(self, ris):
		ct_ris = model2contenttype(ris)
		id_ris = ris.pk
		Nodo.__init__(self, (6, ct_ris, id_ris))
		self.ct_ris = ct_ris
		self.tipo_id = ris.tipo.pk
		self.tipo_ris = ris.tipo.nome
		self.id_ris = id_ris
		self.x, self.y = ris.geom

	def get_coordinate(self):
		return [(self.x, self.y)]

	def get_risorsa(self):
		m = contenttype2model(self.ct_ris)
		return m.objects.get(pk=self.id_ris)

	def risultati_vicini(self, opz):
		return (
			opz['cerca_vicini'] == 'risorse'
			and self.tipo_id in opz['tipi_ris']
			and not ('RIS-%s-%s' % (self.ct_ris, self.id_ris) in opz['linee_escluse'])
		)

	def aggiorna_risultati_vicini(self, risultati, opz):
		if opz['cerca_vicini'] == 'risorse' and self.tipo_id in opz['tipi_ris']:
			dist = self.get_vars(opz).get_distanza()
			risultati.aggiungi_risorsa(self, dist)

	def costruisci_percorso(self, t, opzioni):
		vars = self.get_vars(opzioni)
		ris = self.get_risorsa()
		return tratto.TrattoRisorsa(
			t.parent,
			vars.time,
			self.ct_ris,
			self.id_ris,
			ris.icon,
			ris.icon_size,
			ris.nome_luogo,
			ris.descrizione(),
			self.get_coordinate(),
		)


class NodoPuntoArrivo(geocoder.NodoGeocoder):
	"""
	Nodo usato per le ricerche di percorso single-source, multiple-destination, o per la ricerca di luoghi vicini
	tra un insieme di nodi (NodoPuntoArrivo) passati come parametro
	"""
	def __init__(self, *args, **kwargs):
		super(NodoPuntoArrivo, self).__init__(*args, **kwargs)
		self.nome = ''

	def aggiorna_risultati_vicini(self, risultati, opz):
		if opz['cerca_vicini'] == 'punti' and self in risultati.nodi:
			dist = self.get_vars(opz).get_distanza()
			tempo = self.get_vars(opz).time
			risultati.aggiungi_punto(self, dist, tempo)


class NodoPalinaAttesa(Nodo):
	def __init__(self, rete_palina):
		Nodo.__init__(self, (1, rete_palina.id_palina))
		self.rete_palina = rete_palina

	def get_coordinate(self):
		return [(self.rete_palina.x, self.rete_palina.y)]

	def aggiorna_risultati_vicini(self, risultati, opz):
		if opz['cerca_vicini'] == 'paline':
			p = self.rete_palina
			linee = {}
			dist = self.get_vars(opz).get_distanza()
			for k in p.fermate:
				perc = p.fermate[k].rete_percorso
				if perc.tipo in TIPI_LINEA_INFOTP:
					linee[perc.id_linea] = (p.id_palina, dist, p.x, p.y)
			if len(linee) > 0:
				risultati.aggiungi_palina(p.id_palina, dist, p.x, p.y)
				risultati.aggiungi_linee(linee)


class NodoFermata(Nodo):
	def __init__(self, rete_fermata):
		Nodo.__init__(self, (2, rete_fermata.id_fermata))
		self.rete_fermata = rete_fermata

	def get_coordinate(self):
		return [(self.rete_fermata.rete_palina.x, self.rete_fermata.rete_palina.y)]


class NodoInterscambio(Nodo):
	def __init__(self, nome):
		Nodo.__init__(self, (8, nome))
		self.nome = nome


class ArcoAttesaBus(Arco):
	def __init__(self, nodo_palina, nodo_fermata):
		Arco.__init__(self, nodo_palina, nodo_fermata, (3, nodo_fermata.rete_fermata.id_fermata))

	def get_tempo_vero(self, t, opz):
		d = get_weekday_caching(t, opz)
		f = self.t.rete_fermata
		p = f.rete_percorso
		if p.id_linea in opz['linee_escluse']:
			return (-1, 'Z')
		t_prog, da, a = p.frequenza[d][t.hour]
		if not (da <= t.minute <= a):
			return (-1, 'Z')
		t_arr = f.get_primo_arrivo(t, opz['rev'])
		if t_arr is not None:
			id_veicolo = ""
			if 'id_veicolo' in t_arr[1]:
				id_veicolo = str(t_arr[1]['id_veicolo'])
			return (t_arr[0], 'P' + id_veicolo)
		for i in opz['indici_stat']:
			try:
				ts = p.tempo_stat_orari[i]
				if ts != -1:
					return (ts * 2 / 1.4, 'S')
			except Exception:
				pass
		return (t_prog / 1.4, 'O')

	def get_tempo(self, t, opz):
		if opz['bus'] == False or self.t.rete_fermata.id_fermata in opz['fermate_escluse']:
			return (-1, -1)
		tempo = self.get_tempo_vero(t + timedelta(seconds=opz['t_sal_bus']), opz)[0]
		if tempo == -1:
			return (-1, -1)
		if self.t.rete_fermata.is_capolinea_partenza():
			tpen = max(0, tempo + opz['penalizzazione_bus'] - opz['incentivo_capolinea'])
		else:
			tpen = tempo + opz['penalizzazione_bus']
		return (tpen, tempo)

	def get_coordinate(self):
		return [(self.s.rete_palina.x, self.s.rete_palina.y)]

	def costruisci_percorso(self, t, opzioni):
		vars = self.s.get_vars(opzioni)
		ta, tt = self.get_tempo_vero(vars.time, opzioni)
		return tratto.TrattoBus(t.parent, vars.time, self.t.rete_fermata, ta - opzioni['t_sal_bus'], tt, opzioni['t_sal_bus'])


def tratto_piedi_o_bici(parent, time, arco, opzioni):
	if arco.s.get_context(opzioni)['primo_tratto_bici']:
		return tratto.TrattoBici(parent, time)
	else:
		return tratto.TrattoPiedi(parent, time)


class ArcoDiscesaBus(Arco):
	def __init__(self, nodo_fermata, nodo_palina):
		Arco.__init__(self, nodo_fermata, nodo_palina, (4, nodo_fermata.rete_fermata.id_fermata))

	def get_coordinate(self):
		return [(self.t.rete_palina.x, self.t.rete_palina.y)]

	def get_tempo(self, t, opz):
		if self.s.rete_fermata.id_fermata in opz['fermate_escluse']:
			return (-1, -1)
		tempo = opz['t_disc_bus']
		return (tempo, tempo)

	def costruisci_percorso(self, t, opzioni):
		vars = self.s.get_vars(opzioni)
		tratto.TrattoBusDiscesa(t, vars.time, self.s.rete_fermata, opzioni['t_disc_bus'])
		return tratto_piedi_o_bici(t.parent, vars.time, self, opzioni)


class ArcoPercorrenzaBus(Arco):
	def __init__(self, rete_tratto_percorso, nodo_fermata_s, nodo_fermata_t):
		# In some subclasses, such as ArcoPercorrenzaTreno, rete_tratto_percorso
		# may be a list of ReteTrattoPercorso objects
		self.rete_tratto_percorso = rete_tratto_percorso
		Arco.__init__(self, nodo_fermata_s, nodo_fermata_t, (5, nodo_fermata_s.rete_fermata.id_fermata, nodo_fermata_t.rete_fermata.id_fermata))

	def get_tempo_vero(self, t, opz):
		rtp = self.rete_tratto_percorso.rete_tratto_percorsi
		tp = rtp.tempo_percorrenza
		ua = rtp.ultimo_aggiornamento
		if ua is not None and abs(t - ua) < VALIDITA_TEMPO_ARCHI:
			if tp > 0:
				return (tp, 'P')
			#if rtp.tempo_percorrenza_interpolato > 0:
			#	return (rtp.tempo_percorrenza_interpolato, 'I')
		for i in opz['indici_stat']:
			t = rtp.tempo_percorrenza_stat_orari[i]
			if t != -1:
				return (t, 'S')
		if rtp.dist > 0:
			velocita = 19.0 * 5.0 / 18.0
			for i in opz['indici_stat']:
				if rtp.rete.velocita_medie[i] > 0:
					velocita = rtp.rete.velocita_medie[i]
					break
			return (rtp.dist / velocita, 'D')
		return (60, 'DD')

	def get_tempo(self, t, opz):
		tempo = self.get_tempo_vero(t, opz)[0]
		return (tempo, tempo)

	def get_distanza(self):
		if isinstance(self.rete_tratto_percorso, list):
			return sum(tp.rete_tratto_percorsi.dist for tp in self.rete_tratto_percorso)
		return self.rete_tratto_percorso.rete_tratto_percorsi.dist

	def get_coordinate(self):
		if isinstance(self.rete_tratto_percorso, list):
			return sum((tp.rete_tratto_percorsi.punti for tp in self.rete_tratto_percorso), [])
		return self.rete_tratto_percorso.rete_tratto_percorsi.punti

	def costruisci_percorso(self, t, opzioni):
		vars = self.s.get_vars(opzioni)
		ta, tt = self.get_tempo_vero(vars.time, opzioni)
		tratto.TrattoBusArcoPercorso(t, vars.time, self.rete_tratto_percorso, ta, tt, self.get_coordinate())
		return t


class ArcoAttesaMetro(ArcoAttesaBus):
	def get_tempo_vero(self, t, opz):
		d = get_weekday_caching(t, opz)
		p = self.t.rete_fermata.rete_percorso
		if p.id_linea in opz['linee_escluse'] or self.t.rete_fermata.id_fermata in opz['fermate_escluse']:
			return (-1, 'Z')
		f = p.frequenza[d][t.hour]
		t_arr, da, a = f
		if da <= t.minute <= a:
			return (t_arr / 1.5, False)
		return (-1, False)

	def get_tempo(self, t, opz):
		if opz['metro'] == False or self.t.rete_fermata.id_fermata in opz['fermate_escluse']:
			return (-1, -1)
		tm = self.get_tempo_vero(t, opz)[0]
		if tm < 0:
			return (-1, -1)
		tempo = tm + opz['t_sal_metro']
		if self.t.rete_fermata.is_capolinea_partenza():
			tpen = max(0, tempo + opz['penalizzazione_metro'] - opz['incentivo_capolinea'])
		else:
			tpen = tempo + opz['penalizzazione_metro']
		return (tpen, tempo)

	def costruisci_percorso(self, t, opzioni):
		vars = self.s.get_vars(opzioni)
		ta, tt = self.get_tempo_vero(vars.time, opzioni)
		return tratto.TrattoMetro(t.parent, vars.time, self.t.rete_fermata, ta, tt, opzioni['t_sal_metro'])


class ArcoDiscesaMetro(ArcoDiscesaBus):
	def get_tempo(self, t, opz):
		if self.s.rete_fermata.id_fermata in opz['fermate_escluse']:
			return (-1, -1)
		tempo = opz['t_disc_metro']
		return (tempo, tempo)

	def costruisci_percorso(self, t, opzioni):
		vars = self.s.get_vars(opzioni)
		tratto.TrattoMetroDiscesa(t, vars.time, self.s.rete_fermata, opzioni['t_disc_metro'])
		return tratto_piedi_o_bici(t.parent, vars.time, self, opzioni)


class ArcoDiscesaMetroInterscambio(Arco):
	def __init__(self, nodo_fermata, nodo_interscambio):
		Arco.__init__(self, nodo_fermata, nodo_interscambio, (9, nodo_fermata.rete_fermata.id_fermata))

	def get_tempo(self, t, opz):
		return (0, 0)

	def get_coordinate(self):
		return [(self.s.rete_fermata.rete_palina.x, self.s.rete_fermata.rete_palina.y)]
	def costruisci_percorso(self, t, opzioni):
		vars = self.s.get_vars(opzioni)
		tratto.TrattoMetroDiscesa(t, vars.time, self.s.rete_fermata, 0)
		return t.parent


class ArcoAttesaMetroInterscambio(Arco):
	def __init__(self, nodo_interscambio, nodo_fermata):
		Arco.__init__(self, nodo_interscambio, nodo_fermata,(20, nodo_fermata.rete_fermata.id_fermata))

	def get_tempo_vero(self, t, opz):
		d = get_weekday_caching(t, opz)
		p = self.t.rete_fermata.rete_percorso
		if p.id_linea in opz['linee_escluse']:
			return (-1, 'Z')
		f = p.frequenza[d][t.hour]
		t_arr, da, a = f
		if da <= t.minute <= a:
			return (t_arr / 1.5, False)
		return (-1, False)

	def get_tempo(self, t, opz):
		tv = self.get_tempo_vero(t, opz)[0]
		if tv <= 0:
			return (-1, -1)
		return (opz['t_sal_metro'] + tv, tv)

	def get_coordinate(self):
		return [(self.t.rete_fermata.rete_palina.x, self.t.rete_fermata.rete_palina.y)]

	def costruisci_percorso(self, t, opzioni):
		vars = self.s.get_vars(opzioni)
		ta, tt = self.get_tempo_vero(vars.time, opzioni)
		return tratto.TrattoMetro(t, vars.time, self.t.rete_fermata, ta, tt, opzioni['t_sal_metro'], True)


class ArcoAttesaInterscambio(Arco):
	def __init__(self, nodo_palina, nodo_interscambio):
		Arco.__init__(self, nodo_palina, nodo_interscambio, (21, nodo_palina.rete_palina.id_palina, nodo_interscambio.nome))

	def get_tempo(self, t, opz):
		if opz['auto']:
			return (-1, -1)
		return (opz['t_interscambio'], opz['t_interscambio'])

	def get_coordinate(self):
		return []

	def costruisci_percorso(self, t, opzioni):
		vars = self.s.get_vars(opzioni)
		return tratto.TrattoInterscambio(t.parent, vars.time, self.s.rete_palina, opzioni['t_interscambio'])


class ArcoDiscesaInterscambio(Arco):
	def __init__(self, nodo_interscambio, nodo_palina):
		Arco.__init__(self, nodo_interscambio, nodo_palina, (22, nodo_interscambio.nome, nodo_palina.rete_palina.id_palina))

	def get_tempo(self, t, opz):
		return (0, 0)

	def get_coordinate(self):
		return []

	def costruisci_percorso(self, t, opzioni):
		vars = self.s.get_vars(opzioni)
		t.set_palina_t(self.t.rete_palina)
		return tratto_piedi_o_bici(t.parent, vars.time, self, opzioni)


class ArcoPercorrenzaMetro(ArcoPercorrenzaBus):
	def get_tempo(self, t, opz):
		if self.rete_tratto_percorso.rete_percorso.id_linea == 'MEC':
			return (106, 106)
		return (90, 90)

	def get_tempo_vero(self, t, opz=None):
		if self.rete_tratto_percorso.rete_percorso.id_linea == 'MEC':
			return (106, 'D')
		return (90, 'D')

	def costruisci_percorso(self, t, opzioni):
		vars = self.s.get_vars(opzioni)
		ta, tt = self.get_tempo_vero(vars.time)
		tratto.TrattoMetroArcoPercorso(t, vars.time, self.rete_tratto_percorso, ta, tt, self.rete_tratto_percorso.rete_tratto_percorsi.punti)
		return t


# begin teletrasporto
class ArcoAttesaTeletrasporto(ArcoAttesaBus):
	def __init__(self, nodo_palina, nodo_fermata):
		Arco.__init__(self, nodo_palina, nodo_fermata, (97, nodo_fermata.rete_fermata.id_fermata))

	def get_tempo_vero(self, t, opz):
		return (0, False)

	def get_tempo(self, t, opz):
		if not opz['teletrasporto']:
			return (-1, -1)
		return (0, 0)

	def costruisci_percorso(self, t, opzioni):
		vars = self.s.get_vars(opzioni)
		ta, tt = self.get_tempo_vero(vars.time, opzioni)
		return tratto.TrattoTeletrasporto(t.parent, vars.time, self.t.rete_fermata, ta, tt, 0)


class ArcoPercorrenzaTeletrasporto(ArcoPercorrenzaBus):
	def __init__(self, nodo_fermata_s, nodo_fermata_t):
		Arco.__init__(self, nodo_fermata_s, nodo_fermata_t, (99, nodo_fermata_s.rete_fermata.id_fermata, nodo_fermata_t.rete_fermata.id_fermata))

	def get_coordinate(self):
		return self.s.get_coordinate() + self.t.get_coordinate()


	def get_tempo(self, t, opz):
		if not opz['teletrasporto']:
			return (-1, -1)
		return (1, 1)

	def get_tempo_vero(self, t, opz=None):
		return (1, 'D')

	def costruisci_percorso(self, t, opzioni):
		vars = self.s.get_vars(opzioni)
		ta, tt = self.get_tempo_vero(vars.time)
		tratto.TrattoTeletrasportoArcoPercorso(t, vars.time, self.s.rete_fermata.rete_palina, self.t.rete_fermata.rete_palina, ta)
		return t


class ArcoDiscesaTeletrasporto(ArcoDiscesaBus):
	def __init__(self, nodo_fermata, nodo_palina):
		Arco.__init__(self, nodo_fermata, nodo_palina, (98, nodo_fermata.rete_fermata.id_fermata))

	def get_tempo(self, t, opz):
		if not opz['teletrasporto']:
			return (-1, -1)
		tempo = 0
		return (tempo, tempo)

	def costruisci_percorso(self, t, opzioni):
		vars = self.s.get_vars(opzioni)
		tratto.TrattoTeletrasportoDiscesa(t, vars.time, self.s.rete_fermata, 0)
		return tratto_piedi_o_bici(t.parent, vars.time, self, opzioni)
# end teletrasporto


class ArcoAttesaFC(ArcoAttesaBus):
	def get_tempo_vero(self, t, opz):
		d = get_weekday_caching(t, opz)
		p = self.t.rete_fermata.rete_percorso
		if p.id_linea in opz['linee_escluse']:
			return (-1, 'Z')
		f = p.frequenza[d][t.hour]
		t_arr, da, a = f
		if da <= t.minute <= a:
			return (t_arr / 1.4, False)
		return (-1, False)

	def get_tempo(self, t, opz):
		if opz['fc'] == False or self.t.rete_fermata.id_fermata in opz['fermate_escluse']:
			return (-1, -1)
		tm = self.get_tempo_vero(t, opz)[0]
		if tm < 0:
			return (-1, -1)
		tempo = tm + opz['t_sal_fc']
		if self.t.rete_fermata.is_capolinea_partenza():
			tpen = max(0, tempo + opz['penalizzazione_fc'] - opz['incentivo_capolinea'])
		else:
			tpen = tempo + opz['penalizzazione_fc']
		return (tpen, tempo)

	def costruisci_percorso(self, t, opzioni):
		vars = self.s.get_vars(opzioni)
		ta, tt = self.get_tempo_vero(vars.time, opzioni)
		return tratto.TrattoFC(t.parent, vars.time, self.t.rete_fermata, ta, tt, opzioni['t_sal_fc'])


class ArcoDiscesaFC(ArcoDiscesaBus):
	def get_tempo(self, t, opz):
		if self.s.rete_fermata.id_fermata in opz['fermate_escluse']:
			return (-1, -1)
		tempo = opz['t_disc_fc']
		return (tempo, tempo)

	def costruisci_percorso(self, t, opzioni):
		vars = self.s.get_vars(opzioni)
		tratto.TrattoFCDiscesa(t, vars.time, self.s.rete_fermata, opzioni['t_disc_fc'])
		return tratto_piedi_o_bici(t.parent, vars.time, self, opzioni)


class ArcoPercorrenzaFC(ArcoPercorrenzaBus):
	def get_tempo(self, t, opz):
		p = self.rete_tratto_percorso.rete_percorso
		idl = p.id_linea
		n = len(p.tratti_percorso)
		tempo = {
			'RMG': 103,
			'Roma Giardinetti': 103,
			'RL': 185,
			'Roma Lido': 185,
			'RMVT': 94,
			'Roma Viterbo': 94,
		}[idl] * n * self.rete_tratto_percorso.rete_tratto_percorsi.dist / p.dist
		return (tempo, tempo)

	def get_tempo_vero(self, t, opz):
		p = self.rete_tratto_percorso.rete_percorso
		idl = p.id_linea
		n = len(p.tratti_percorso)
		return ({
			'RMG': 103,
			'Roma Giardinetti': 103,
			'RL': 185,
			'Roma Lido': 185,
			'RMVT': 94,
			'Roma Viterbo': 94,
		}[idl] * n * self.rete_tratto_percorso.rete_tratto_percorsi.dist / p.dist), 'D'

	def costruisci_percorso(self, t, opzioni):
		vars = self.s.get_vars(opzioni)
		ta, tt = self.get_tempo_vero(vars.time, opzioni)
		tratto.TrattoFCArcoPercorso(t, vars.time, self.rete_tratto_percorso, ta, tt, self.rete_tratto_percorso.rete_tratto_percorsi.punti)
		return t


class ArcoAttesaTreno(ArcoAttesaBus):
	def __init__(self, nodo_palina, nodo_fermata):
		ArcoAttesaBus.__init__(self, nodo_palina, nodo_fermata)
		self.partenze = [Avl() for i in range(7)]
		self.ha_partenze = False

	def aggiungi_partenza(self, dt, day=None):
		"""
		Aggiunge un orario di partenza

		L'orario di partenza può essere un time o un datetime.
		Se è un datetime bisogna passare day=None. Se è un time, day deve valere
		0 (festivo), 5 (sabato) o 6 (domenica)
		"""
		self.ha_partenze = True
		if day is None:
			d = dt.weekday()
			t = datetime2time(dt)
		else:
			d = day % 7
			t = dt
		if d < 5:
			d = 0
		self.partenze[d].insert(t, None)

	def prossima_partenza(self, t, opz):
		if not self.ha_partenze:
			return None
		ora = datetime2time(t)
		data = datetime2date(t)
		n = None
		giorni = 0
		while n is None:
			if giorni <= 1:
				d = get_weekday_caching(data, opz)
			else:
				d = Festivita.get_weekday(data, compatta_feriali=True)
			n = self.partenze[d].gt_key(ora)
			if n is None:
				ora = time(0, 0)
				data += timedelta(days=1)
				giorni += 1
		return dateandtime2datetime(data, n[0])

	def get_tempo_vero(self, t, opz):
		if not self.ha_partenze:
			return (-1, False)
		p = self.t.rete_fermata.rete_percorso
		if p.id_linea in opz['linee_escluse']:
			return (-1, 'Z')
		t1 = t + timedelta(seconds=opz['t_sal_treno'])
		dt = self.prossima_partenza(t1, opz)
		diff = dt - t
		tempo = diff.days * 86400 + diff.seconds
		return (tempo, 'O')

	def get_tempo(self, t, opz):
		if not opz['fr'] or self.t.rete_fermata.id_fermata in opz['fermate_escluse']:
			return (-1, -1)
		tempo, b = self.get_tempo_vero(t, opz)
		if tempo == -1:
			return (-1, -1)
		if self.t.rete_fermata.is_capolinea_partenza():
			tpen = max(0, tempo + opz['penalizzazione_treno'] - opz['incentivo_capolinea'])
		else:
			tpen = tempo + opz['penalizzazione_treno']
		return (tpen, tempo)

	def costruisci_percorso(self, t, opzioni):
		vars = self.s.get_vars(opzioni)
		ta, tt = self.get_tempo_vero(vars.time, opzioni)
		return tratto.TrattoTreno(t.parent, vars.time, self.t.rete_fermata, ta - opzioni['t_sal_treno'], tt, opzioni['t_sal_treno'])


class ArcoDiscesaTreno(ArcoDiscesaBus):
	def get_tempo(self, t, opz):
		if self.s.rete_fermata.id_fermata in opz['fermate_escluse']:
			return (-1, -1)
		return (opz['t_disc_treno'], opz['t_disc_treno'])

	def costruisci_percorso(self, t, opzioni):
		vars = self.s.get_vars(opzioni)
		tratto.TrattoTrenoDiscesa(t, vars.time, self.s.rete_fermata, opzioni['t_disc_treno'])
		return tratto_piedi_o_bici(t.parent, vars.time, self, opzioni)


class ArcoPercorrenzaTreno(ArcoPercorrenzaBus):
	def __init__(self, rete_tratto_percorso, nodo_fermata_s, nodo_fermata_t):
		# rete_tratto_percorso può essere una lista di tratti
		ArcoPercorrenzaBus.__init__(self, rete_tratto_percorso, nodo_fermata_s, nodo_fermata_t)
		self.partenze = [Avl() for i in range(7)]
		self.ha_partenze = False

	def aggiungi_partenza(self, dt, perc, day=None):
		"""
		Aggiunge un orario di partenza e lo associa a un tempo di percorrenza, in secondi

		L'orario di partenza può essere un time o un datetime.
		Se è un datetime bisogna passare day=None. Se è un time, day deve valere
		0 (festivo), 5 (sabato) o 6 (domenica)
		"""
		self.ha_partenze = True
		if day is None:
			d = dt.weekday()
			t = datetime2time(dt)
		else:
			d = day % 7
			t = dt
		if d < 5:
			d = 0
		self.partenze[d].insert(t, perc)

	def prossima_partenza(self, t, opz):
		if not self.ha_partenze:
			return None
		ora = datetime2time(t)
		data = datetime2date(t)
		n = None
		giorni = 0
		while n is None:
			if giorni <= 1:
				d = get_weekday_caching(data, opz)
			else:
				d = Festivita.get_weekday(data, compatta_feriali=True)
			n = self.partenze[d].gt_key(ora)
			if n is None:
				ora = time(0, 0)
				data += timedelta(days=1)
				giorni += 1
		return (dateandtime2datetime(data, n[0]), n[1])

	def get_tempo(self, t, opz):
		el = self.prossima_partenza(t, opz)
		if el is None:
			return (-1, -1)
		dt, tempo = el
		return (tempo, tempo)

	def get_tempo_vero(self, t, opz=None):
		pass
		#return (90, 'D')

	def costruisci_percorso(self, t, opzioni):
		vars = self.s.get_vars(opzioni)
		ta, x = self.get_tempo(vars.time, opzioni)
		tt = 'O'
		tratto.TrattoTrenoArcoPercorso(t, vars.time, self.rete_tratto_percorso, ta, tt, self.get_coordinate())
		return t


def registra_classi_grafo(g):
	classi_nodi = [tomtom.NodoTomTom, geocoder.NodoGeocoder]
	classi_archi = [tomtom.ArcoTomTom, geocoder.ArcoGeocoder]
	for cn in classi_nodi:
		g.registra_tipo_nodi(cn)
	for ca in classi_archi:
		g.registra_tipo_archi(ca)


def carica_rete_su_grafo(r, g, retina=False, versione=None):
	"""
	Carica la rete del TPL all'interno del grafo g e aggiorna i link inversi
	"""
	print "Carico rete su grafo"

	registra_classi_grafo(g)

	# Paline
	for k in r.paline:
		p = r.paline[k]
		if not p.soppressa:
			n = NodoPalinaAttesa(p)
			p.nodo_palina = n
			g.add_nodo(n)
	interscambio = {'TERMINI': None, 'BOLOGNA': None}
	nodi_scambio = {
		# 'PIRAMIDE': ['90151', '91151', 'BP8', 'BD15', '90221', '91221'],
		# 'EUR MAGLIANA': ['90153', '91153', 'BP4', 'BD19'],
		'EUR MAGLIANA': ['90153', '99153', 'C412073'],
		'SAN PAOLO': ['90152', '99152', 'C672865'],
		'PIRAMIDE': ['C251669', 'C074046', '90151']
		# 'TEST': ['BP8', 'BD15', 'AP7', 'AD21'] # Ostiense <-> Porta Furba
	}
	for k in interscambio:
		n = NodoInterscambio(k)
		interscambio[k] = n
		g.add_nodo(n)
	for k in nodi_scambio:
		n = NodoInterscambio(k)
		g.add_nodo(n)
		for id_palina in nodi_scambio[k]:
			try:
				np = g.nodi[(1, id_palina)]
				a = ArcoAttesaInterscambio(np, n)
				g.add_arco(a)
				a = ArcoDiscesaInterscambio(n, np)
				g.add_arco(a)
			except:
				traceback.print_exc()
				print "Nodo scambio: palina %s non trovata" % id_palina
	# Fermate
	fermata_teletrasporto = None
	for k in r.fermate:
		f = r.fermate[k]
		if not f.rete_percorso.soppresso:
			# Aggiungo fermata
			n = NodoFermata(f)
			f.nodo_fermata = n
			g.add_nodo(n)
			# Aggiungo arco di attesa e arco di discesa, se la palina non è soppressa
			if (1, f.rete_palina.id_palina) in g.nodi:
				np = g.nodi[(1, f.rete_palina.id_palina)]
				tipo = f.rete_percorso.tipo
				Attesa, Discesa = {
					'BU': (ArcoAttesaBus, ArcoDiscesaBus),
					'TR': (ArcoAttesaBus, ArcoDiscesaBus),
					'ME': (ArcoAttesaMetro, ArcoDiscesaMetro),
					'FR': (ArcoAttesaTreno, ArcoDiscesaTreno),
					'FC': (ArcoAttesaFC, ArcoDiscesaFC),
				}[tipo]
				a = Attesa(np, n)
				f.arco_attesa_bus = a
				g.add_arco(a)
				a = Discesa(n, np)
				f.arco_discesa_bus = a
				g.add_arco(a)
				# begin teletrasporto
				if tipo != 'BU' and tipo != 'TR':
					Attesa = ArcoAttesaTeletrasporto
					Discesa = ArcoDiscesaTeletrasporto
					a = Attesa(np, n)
					f.arco_attesa_bus = a
					g.add_arco(a)
					a = Discesa(n, np)
					f.arco_discesa_bus = a
					g.add_arco(a)
					if fermata_teletrasporto is not None:
						g.add_arco(ArcoPercorrenzaTeletrasporto(fermata_teletrasporto, n))
						g.add_arco(ArcoPercorrenzaTeletrasporto(n, fermata_teletrasporto))
					else:
						fermata_teletrasporto = n
				# end teletrasporto
				nome = f.rete_palina.nome
				if tipo == 'ME' and nome in interscambio:
					ni = interscambio[nome]
					a = ArcoAttesaMetroInterscambio(ni, n)
					g.add_arco(a)
					a = ArcoDiscesaMetroInterscambio(n, ni)
					g.add_arco(a)
	# Tratti di percorso
	for k in r.tratti_percorso:
		tp = r.tratti_percorso[k]
		if not tp.rete_percorso.soppresso:
			tipo = tp.rete_percorso.tipo
			Percorrenza = {
				'BU': ArcoPercorrenzaBus,
				'TR': ArcoPercorrenzaBus,
				'ME': ArcoPercorrenzaMetro,
				'FR': ArcoPercorrenzaTreno,
				'FC': ArcoPercorrenzaFC,
			}[tipo]
			a = Percorrenza(tp, tp.s.nodo_fermata, tp.t.nodo_fermata)
			tp.arco_tratto_percorso = a
			g.add_arco(a)
			# begin teletrasporto
			"""
			if tipo == 'ME':
				a = ArcoPercorrenzaTeletrasporto(tp, tp.s.nodo_fermata, tp.t.nodo_fermata)
				tp.arco_tratto_percorso = a
				g.add_arco(a)
			"""
			# end teletrasporto
	# Archi di distanza fra paline e grafo pedonale (osm)
	print "Collego la rete del TPL alla rete stradale"
	if versione is None:
		inizio_validita = datetime2compact(VersionePaline.attuale().inizio_validita)
	else:
		inizio_validita = datetime2compact(versione)
	path_rete = os.path.join(settings.TROVALINEA_PATH_RETE, inizio_validita)
	geocoding_file = os.path.join(path_rete, 'archi_geocoding%s.v3.dat' % ('_mini' if retina else ''))
	r.geocoder = geocoder.Geocoder(g, 12, caching_id='mini' if retina else 'full') # 12 e' il tipo degli archi stradali
	gc = r.geocoder
	try:
		g.deserialize(geocoding_file)
	except IOError:
		print "Necessario ricalcolo"
		ps = [r.paline[k] for k in r.paline if not r.paline[k].soppressa]
		dp = DijkstraPool(g, 1)
		with dp.get_dijkstra() as dj:
			for i in range(0, len(ps)):
				pi = ps[i]
				ni = g.nodi[(1, pi.id_palina)]
				if pi.ferroviaria :
					archi_conn = gc.connect_to_node_multi(ni, dj)
					if len(archi_conn) == 0:
						archi_conn = gc.connect_to_node(ni)
				else:
					archi_conn = gc.connect_to_node(ni)
				for a in archi_conn:
					g.add_arco(a)
		g.serialize(geocoding_file, [geocoder.ArcoGeocoder], [geocoder.NodoGeocoder])

	if True: #not retina:
		# Nodi luogo e connessione
		print "Aggiungo e collego nodi luogo"
		for risorsa in risorse.modelli_risorse:
			print risorsa.__name__
			for a in risorsa.objects.all():
				if a.geom is None:
					print "No luogo: " + a.nome_luogo
				else:
					n = NodoRisorsa(a)
					g.add_nodo(n)
					archi_conn = gc.connect_to_node(n)
					for a in archi_conn:
						g.add_arco(a)

		# Elimino archi rimossi da database
		print "Elimino archi rimossi da database"
		ars = ArcoRimosso.objects.filter(rimozione_attiva=True)
		for a in ars:
			try:
				print a, a.eid
				g.rm_arco(g.archi[a.eid])
			except Exception, e:
				logging.error(u'Arco rimosso %s non trovato', a.descrizione)

	# Orari Ferrovie del Lazio
	carica_orari_fl_da_db(r, g)

	gc.serialize_cache()
	db.reset_queries()


def carica_rete_e_grafo(retina=False, versione=None, rete_base=None):
	rete = Rete()
	rete.carica(retina, versione, rete_base=rete_base)
	g = Grafo()
	registra_classi_grafo(g)
	g.deserialize(os.path.join(settings.TROVALINEA_PATH_RETE, '%s%s.v3.dat' % (settings.GRAPH, '_mini' if retina else '')))
	#tomtom.load_from_shp(g, 'C:\\Users\\allulll\\Desktop\\grafo\\cpd\\RM_nw%s'  % ('_mini' if retina else ''))
	carica_rete_su_grafo(rete, g, retina, versione)
	return (rete, g)


# Frequenza bus
def calcola_frequenze_giorno(giorno, giorno_settimana, percorsi_da_rete=True):
	with transaction():
		FrequenzaPercorso.objects.filter(giorno_settimana=giorno_settimana).delete()
		giorno_succ = giorno + timedelta(days=1)
		if percorsi_da_rete:
			ps = Percorso.objects.by_date(date2datetime(giorno) + timedelta(hours=7)).all()
			id_percorsi = [p.id_percorso for p in ps]
		else:
			pcs = PartenzeCapilinea.objects.filter(orario_partenza__gte=giorno, orario_partenza__lt=giorno_succ).distinct('id_percorso')
			id_percorsi = [p.id_percorso for p in pcs]
		for id_percorso in id_percorsi:
			#print percorso.id_percorso
			pcs = PartenzeCapilinea.objects.filter(id_percorso=id_percorso, orario_partenza__gte=giorno, orario_partenza__lt=giorno_succ).order_by('orario_partenza')
			sum = [0.0 for i in range(24)]
			cnt = [0 for i in range(24)]
			da = [0 for i in range(24)]
			a = [59 for i in range(24)]
			old = None
			pcs = [x for x in pcs] + [None]
			for p in pcs:
				sx = False
				dx = False
				if p is None:
					dx = True
					op = date2datetime(giorno_succ)
				else:
					op = p.orario_partenza
				if old is None:
					sx = True
					old = date2datetime(giorno)
				diff = op - old
				if sx or dx:
					diff = 2 * diff
				h1 = old.hour
				m1 = old.minute
				h2 = op.hour
				m2 = op.minute
				if dx and sx:
					# Percorso non attivo per tutto il giorno
					da = [-1 for i in range(24)]
					a = [-1 for i in range(24)]
					break
				if diff <= MAX_PERIODO_PERCORSO_ATTIVO:
					if dx:
						h2 = 23
					"""
					if True: # id_percorso == '51035':
						print "%d - %d" % (h1, h2)
					"""
					for i in range(h1, h2 + 1):
						sum[i] += diff.seconds
						cnt[i] += 1
				else:
					if m1 > 0:
						a[h1] = m1
					else:
						da[h1] = -1
						a[h1] = -1
					if dx:
						h2 = 24
					for i in range(h1 + 1, h2):
						da[i] = -1
						a[i] = -1
					if not dx:
						da[h2] = m2
				old = op
			"""
			if True: # id_percorso == '51035':
				print cnt
				print sum
			"""
			for h in range(24):
				if cnt[h] > 0:
					f = sum[h] / cnt[h]
				else:
					f = -1
				fp = FrequenzaPercorso(
					id_percorso=id_percorso,
					ora_inizio=h,
					giorno_settimana=giorno_settimana,
					frequenza=f,
					da_minuto=da[h],
					a_minuto=a[h],
				)
				#print fp.ora_inizio
				fp.save()


def calcola_frequenze(percorsi_da_rete=True):
	def cerca_giorno(i):
		if i < 0 or i > 6:
			raise Exception("Il giorno deve variare tra 0 (lunedi') e 6 (domenica)")
		d = date.today()
		while True:
			if Festivita.get_weekday(d, compatta_feriali=True) == i:
				return d
			d += timedelta(days=1)

	giorni = set([0, 5, 6])
	for gi in giorni:
		g = cerca_giorno(gi)
		print g
		calcola_frequenze_giorno(g, gi, percorsi_da_rete)


def elabora_statistiche(data_inizio, data_fine, min_weight=5, elabora_tempi_archi=True, elabora_tempi_attesa=True):
	pas = list(StatPeriodoAggregazione.objects.all())
	weekdays = {}
	def stas_init():
		return [0.0, 0.0, 0]
	stas = defaultdict(stas_init)
	if elabora_tempi_archi:
		StatTempoArcoNew.objects.all().delete()
		print "Calcolo statistiche tempi percorrenza archi"
		d = data_inizio
		while d <= data_fine:
			print "[{}] ".format(datetime2mysql(datetime.now())) + str(d)
			wd = Festivita.get_weekday(d)
			ltas = LogTempoArco.objects.filter(data=d)
			for lta in batch_qs(ltas):
				for pa in pas:
					if pa.ora_inizio <= lta.ora < pa.ora_fine and getattr(pa, 'wd%d' % wd):
						sta = stas[lta.id_palina_s, lta.id_palina_t, pa.pk]
						peso = lta.peso
						sta[0] += lta.tempo * peso
						sta[1] += peso
						sta[2] += 1
			d += timedelta(days=1)
		for key in stas:
			ids, idt, pk = key
			tempo, peso, cnt = stas[key]
			if peso > min_weight:
				StatTempoArcoNew(
					id_palina_s=ids,
					id_palina_t=idt,
					tempo=tempo / peso,
					numero_campioni=cnt,
					periodo_aggregazione_id=pk,
				).save()
	if elabora_tempi_attesa:
		StatTempoAttesaPercorsoNew.objects.all().delete()
		print "Calcolo statistiche tempi attesa percorsi"
		ltas = LogTempoAttesaPercorso.objects.filter(data__gte=data_inizio, data__lte=data_fine)
		stas = defaultdict(stas_init)
		with mostra_avanzamento(ltas.count()) as conta:
			for lta in batch_qs(ltas):
				conta()
				d = lta.data
				if d in weekdays:
					wd = weekdays[d]
				else:
					wd = Festivita.get_weekday(d)
					weekdays[d] = wd
				for pa in pas:
					if pa.ora_inizio <= lta.ora < pa.ora_fine and getattr(pa, 'wd%d' % wd):
						sta = stas[lta.id_percorso, pa.pk]
						sta[0] += lta.tempo
						sta[2] += 1
		for key in stas:
			idp, pk = key
			tempo, peso, cnt = stas[key]
			if cnt > min_weight:
				StatTempoAttesaPercorsoNew(
					id_percorso=idp,
					tempo=tempo / cnt,
					numero_campioni=cnt,
					periodo_aggregazione_id=pk,
				).save()


# Analisi
class Avg(object):
	def __init__(self):
		object.__init__(self)
		self.cnt = 0
		self.tot = 0
		self.min = None
		self.max = None

	def aggiungi(self, k):
		self.cnt +=1
		self.tot += k

	def aggiungi_percentuale(self, a1, a2):
		print a1, a2
		diff = float(abs(a1 - a2))
		self.aggiungi(diff / max((a1, a2)))
		if self.min is None or diff < self.min:
			self.min = diff
		if self.max is None or diff > self.max:
			self.max = diff

	def media(self):
		print self.tot, self.cnt
		return float(self.tot) / float(self.cnt)

	def media_percentuale(self):
		return self.media() * 100

	def get_statistiche(self):
		return "min: %.0f, max: %.0f, media: %.0f%%" % (self.min, self.max, self.media_percentuale())

def organizza_arrivi_ricalcolati(palina):
	a = {}
	for k in palina.fermate:
		arr = palina.fermate[k].arrivi
		for el in arr:
			a[el['id_veicolo']] = el
	return a


def confronta_arrivi(paline):
	tot = 0
	trov = 0
	errore_numero = Avg()
	errore_tempo = Avg()
	for palina in paline:
		ar = organizza_arrivi_ricalcolati(palina)
		palina.aggiorna_arrivi()
		for id_veicolo in palina.arrivi:
			tot += 1
			if id_veicolo in ar:
				trov += 1
				a1 = palina.arrivi[id_veicolo]
				a2 = ar[id_veicolo]
				f1 = a1['fermate']
				f2 = a2['fermate']
				errore_numero.aggiungi_percentuale(f1, f2)
				t1 = a1['tempo']
				t2 = a2['tempo']
				if t1 != -1 and t2 != -1:
					errore_tempo.aggiungi_percentuale(t1, t2)
	print "Trovate: %d su %d" % (trov, tot)
	print "Errore numero femate: %s" % errore_numero.get_statistiche()
	print "Errore tempi attesa: %s" % errore_tempo.get_statistiche()


def _get_or_create_arco_percorrenza_treno(g, tratto_percorso_s, id_palina_t):
	"""
	Return a single or multiple ArcoPercorrenzaTreno

	:param g: Grafo
	:param tratto_percorso_s: source tratto_percorso
	:param id_palina_t: target id_palina
	:return: (ArcoPercorrenzaTreno, next tratto_percorso)
	"""
	f1 = tratto_percorso_s.s.id_fermata
	tps = []
	tp = tratto_percorso_s
	while tp.t.rete_palina.id_palina != id_palina_t:
		tps.append(tp)
		tp = tp.t.tratto_percorso_successivo
	tps.append(tp)
	f2 = tp.t.id_fermata
	tp = tp.t.tratto_percorso_successivo
	key = (5, f1, f2)
	if key in g.archi:
		return g.archi[key], tp
	ns = g.nodi[(2, f1)]
	nt = g.nodi[(2, f2)]
	apt = ArcoPercorrenzaTreno(tps, ns, nt)
	g.add_arco(apt)
	return apt, tp


def carica_orari_fl_da_db(r, g):
	def converti_ora_giorno(s, d):
		h, m, sec = s.split(':')
		today = date.today()
		h = int(h)
		while h > 23:
			d += 1
			h -= 24
			today += timedelta(days=1)
		t = time(h, int(m))
		return t, d, dateandtime2datetime(today, t)

	print "Carico orari FL"

	ots = OrarioTreno.objects.all()
	for ot in ots:
		id_percorso = ot.id_percorso
		try:
			if id_percorso in r.percorsi:
				if id_percorso == 'RM73692':
					print id_percorso, ot.giorno, ot.orari
				p = r.percorsi[id_percorso]
				day = ot.giorno
				orari = ot.orari.split(",")
				id_paline = ot.id_paline.split(",")
				i = 0
				tp = p.tratti_percorso[0]
				for i in range(len(orari) - 1):
					t1, d1, dt1 = converti_ora_giorno(orari[i], day)
					t2, d2, dt2 = converti_ora_giorno(orari[i + 1], day)
					f1 = tp.s.id_fermata
					perc = (dt2 - dt1).seconds
					#print f1, f2, perc
					aat = g.archi[(3, f1)]
					apt, tp = _get_or_create_arco_percorrenza_treno(g, tp, id_paline[i + 1])
					if id_percorso == 'RM73692':
						print "Aggiunto arco ", apt
					# apt = g.archi[(5, f1, f2)]
					aat.aggiungi_partenza(t1, d1)
					apt.aggiungi_partenza(t1, perc, d2)
			else:
				print "Percorso {} non trovato!".format(id_percorso)
		except BaseException as e:
			print("Errore nel caricamento orari per percorso", id_percorso)
			traceback.print_exc()


def test_ferrovia(r, g):
	for id_percorso in ['51305', '51306']:
		perc = r.percorsi[id_percorso]
		for t in perc.tratti_percorso:
			f = t.s
			aat = g.archi[(3, f.id_fermata)]
			apt = g.archi[(5, f.id_fermata, t.t.id_fermata)]
			print f.id_fermata
			tod = date2datetime(date.today())
			tom = tod + timedelta(days=1)
			while tod < tom:
				#print tod
				aat.aggiungi_partenza(tod)
				apt.aggiungi_partenza(tod, 55)
				tod += timedelta(minutes=1)


def get_weekday_caching(t, opz):
	if t.day == opz['giorno']:
		return opz['wd_giorno']
	return opz['wd_giorno_succ']


def salva_archi_tomtom_su_db(grafo, num=1, den=1):
	n = len(grafo.archi)
	dim = n / den
	start = (num - 1) * dim
	stop = num * dim
	i = 0
	with transaction():
		for eid in grafo.archi:
			i += 1
			if i % 100 == 0:
				print "%d%%" % int(100 * float(i) / n)
			if start <= i-1 and i-1 < stop and eid[0] == 12:
				a = grafo.archi[eid]
				s = a.to_model()
				s.save()


def analisi_velocita_archi(r, g, opz=None):
	if opz is None:
		opz = r.get_opzioni_calcola_percorso(True, True, True, True, 1)
	# dijkstra = DijkstraPool(g, 1)
	# opz['dijkstra'] = dijkstra
	n = datetime.now()
	d = defaultdict(int)
	for eid in g.archi:
		tipo = eid[0]
		if tipo not in [12, 16, 97, 98, 99]:
			e = g.archi[eid]
			cs = e.s.get_coordinate()
			ct = e.t.get_coordinate()
			if cs is not None and ct is not None:
				ip, tv = e.get_tempo(n, opz)
				dist = geomath.distance(cs[0], ct[0])
				if ip > 0:
					v = dist / tv
					if v > d[tipo]:
						d[tipo] = v
					if v > 18:
						print v, eid, e, e.s.rete_fermata.rete_palina.nome
	return d


def grafo2shape(g, path, filename):
	"""
	Esporta il grafo g come shapefile

	path: cartella nella quale creare gli shapefile
	Il nome degli shapefile ha lo schema seguente:
	LINEA_PERCORSO_percorso.shp/dbf/...
	LINEA_PERCORSO_fermate.shp/dbf/...
	"""
	base_file_name = "grafo"
	with geomath.zipped_shapefile(shapefile.POLYLINE, path, filename, gbfe=True) as shp_p:
		shp_p.autoBalance = 1
		shp_p.field('EID', 'C', '80')
		shp_p.field('ID_S', 'C', '80')
		shp_p.field('ID_T', 'C', '80')
		shp_p.field('DESC', 'C', '80')
		for eid in g.archi:
			e = g.archi[eid]
			if e.id[0] == 12:
				line = e.get_coordinate()
				desc = ""
				if e.id[0] != 12:
					print eid, line
				else:
					desc = e.get_nome().encode('iso-8859-1')
				shp_p.line(parts=[line])
				shp_p.record(
					EID=str(e.id),
					ID_S=str(e.s.id),
					ID_T=str(e.t.id),
					DESC=desc,
				)


def esporta_tratti_ferroviari():
	def cond_is_ferro(tp):
		p = tp.percorsi.values()[0].rete_percorso
		return p.tipo in {'ME', 'FR', 'FC'}

	rete = Rete()
	rete.carica()
	fp = os.path.join(settings.TROVALINEA_PATH_RETE, settings.TROVALINEA_FILE_TRATTI_PERCORSI)
	rete.esporta_tratti_percorsi(fp, cond_is_ferro)

