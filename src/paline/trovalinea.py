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

import tpl
import pyximport; pyximport.install()
from rpyc.utils.server import ThreadedServer
import rpyc
import pyproj
import tratto
from time import sleep
from datetime import date, time, timedelta, datetime
from mapstraction import BoundingBox
from geomath import gbfe_to_wgs84, wgs84_to_gbfe
import grafo as graph
import osm
import geocoder
import gmaps
from paline.caricamento_rete.caricamento_rete import lancia_processo_caricamento_rete
from django.core.mail import send_mail
import traceback
from servizi.utils import datetime2mysql, mysql2datetime, model2contenttype, contenttype2model, getdef
from servizi.autocomplete import Autocomplete
import settings
from threading import Thread, Lock 
from Queue import PriorityQueue, Queue
from time import sleep
from paline import models as paline
from carpooling import models as carpoolingmodels
from paline.gtfs_rt_upload import gtfs_realtime_uploader
import cPickle as pickle
from IPython import embed
from copy import copy, deepcopy
import logging
import carpoolinggraph
import tomtom
from mercury.models import MercuryListener, autopickle, queued, Peer, autostored, DaemonControl
from django import db
from ztl.models import ZTL
from pprint import pprint
from paline.models import LogAvm, Gestore, IndirizzoAutocompl
from constance import config
import os, os.path
import json


PERCORSI_INTERSEZIONE = [
	('56082', '50819', 'MEBCom11', 'MEBCom1', 'ME', 'Metro B - B1'), # B1, B Direz. Bologna
	('56083', '50820', 'MEBCom12', 'MEBCom1', 'ME', 'Metro B - B1'), # B1, B Direz. Laurentina
]
FATTORE_AVANZAMENTO_TEMPO = 0.8
N_ISTANZE_PARALLELE = 3
WATCHDOG_RESTART_GRACE_PERIOD = timedelta(minutes=20)
WATCHDOG_MAX_UPDATE_AGE = timedelta(minutes=7)


class PalineVicine(object):
	"""
	Contenitore per la ricerca di paline vicine
	"""
	def __init__(self, npaline, nlinee):
		self.npaline = npaline
		self.nlinee = nlinee
		self.paline = []
		self.linee = set([])
		self.linee_ord = []
		
	def aggiungi_palina(self, p, dist, x, y):
		self.paline.append((p, dist, x, y))
		
	def aggiungi_linee(self, ls):
		for l in ls:
			if not l in self.linee:
				self.linee.add(l)
				self.linee_ord.append((l, ls[l][0], ls[l][1]))
		
	def completo(self):
		return (len(self.paline) >= self.npaline) and (len(self.linee) >= self.nlinee)


class RisorseVicine(object):
	"""
	Contenitore per la ricerca di risorse vicine
	"""
	def __init__(self, n_ris):
		self.n_ris = n_ris
		self.ris = []
		
	def aggiungi_risorsa(self, r, dist):
		print "Aggiungo risorsa"
		self.ris.append((r, dist))
		
	def completo(self):
		# print "Numero luoghi: %d su %d" % (len(self.luoghi), self.n_luoghi)
		return len(self.ris) >= self.n_ris


class PuntiVicini(object):
	"""
	Contenitore per la ricerca di punti vicini
	"""
	def __init__(self, n_ris, nodi):
		self.n_ris = n_ris
		self.ris = []
		self.nodi = nodi

	def aggiungi_punto(self, r, dist, tempo):
		print "Aggiungo punto"
		self.ris.append((r, dist, tempo))

	def completo(self):
		# print "Numero luoghi: %d su %d" % (len(self.luoghi), self.n_luoghi)
		return len(self.ris) >= self.n_ris


class Scheduler(Thread):
	def __init__(self, granularity=timedelta(minutes=1)):
		Thread.__init__(self)
		self.pq = PriorityQueue()
		self.granularity = granularity
		
	def insert(self, dt, callback):
		self.pq.put((dt, callback))
		
	def run(self):
		while True:
			dt, cb = self.pq.get()
			if dt > datetime.now():
				self.pq.put((dt, cb))
				sleep(self.granularity.seconds)
			else:
				cb()


class ShellThread(Thread):
	def __init__(self, cls):
		Thread.__init__(self)
		self.cls = cls
	
	def run(self):
		embed()


class WatchdogAggiornamentoRete(Thread):
	def __init__(self, rete):
		print("Watchdog init")
		Thread.__init__(self)
		self.rete = rete

	def run(self):
		print("Watchdog running")
		sleep(WATCHDOG_RESTART_GRACE_PERIOD.seconds)
		while True:
			print("Watchdog checking")
			if self.rete.ultimo_aggiornamento is None or datetime.now() - self.rete.ultimo_aggiornamento > WATCHDOG_MAX_UPDATE_AGE:
				print("Watchdog restarting!!!")
				dc = DaemonControl.objects.get(name=settings.MERCURY_GIANO)
				if dc.action == 'N':
					dc.action = 'R'
					dc.save()
			sleep(60)


def TrovalineaFactory(
		retina=False,
		calcola_percorso=False,
		tempo_reale=False,
		shell=False,
		special=False,
		dt=None,
		download=False,
		daemon=None,
		tempo_reale_percorsi=False,
	):
	"""
	Restituisce una classe Trovalinea, pronta per essere registrata con un server RPyC

	retina: usa una rete limitata per scopi di test
	calcola_percorso: carica il grafo per il cerca percorso e cerca luogo
	tempo_reale: avvia la sincronizzazione della posizione dei veicoli
	shell: avvia shell
	special: rete speciale (deprecato)
	dt: carica la versione della rete attiva all'orario dt
	download: sincronizza i dati in tempo reale scaricandoli dai server di muovi.roma.it
	daemon: demone in ascolto relativo al processo in esecuzione
	"""
	
	class Trovalinea(MercuryListener):
		@classmethod
		def init_rete(cls, pause=None):
			if special:
				cls.rete_special = tpl.Rete()
				cls.rete_special.carica_da_dbf(settings.TROVALINEA_RETE_SPECIALE)
			
			r = tpl.Rete()
			v = None
			if dt is not None:
				v = mysql2datetime(dt)
			r.carica(retina, versione=v)
			for el in PERCORSI_INTERSEZIONE:
				p1, p2, idp, idl, tipo, desc = el
				r.costruisci_percorso_intersezione(p1, p2, idp, idl, tipo, desc)
			if shell:
				ShellThread(cls).start()
			if calcola_percorso:
				g = graph.Grafo()
				tpl.registra_classi_grafo(g)
				g.deserialize(os.path.join(settings.TROVALINEA_PATH_RETE, '%s%s.v3.dat' % (settings.GRAPH, '_mini' if retina else '')))
				tpl.carica_rete_su_grafo(r, g, retina, versione=v)
				# print "Inizializzo geocoder"
				# gcd = geocoder.Geocoder(g)
				now = datetime.now()
				end_cp = now + timedelta(days=carpoolingmodels.CARPOOLING_DAYS)
				cls.dijkstra_queue = graph.DijkstraPool(g, N_ISTANZE_PARALLELE)
				carpoolinggraph.carica_percorsi(r, cls.dijkstra_queue, carpoolingmodels.PassaggioOfferto.objects.filter(orario__gte=now, orario__lte=end_cp, annullato=False))
			
			if tempo_reale: # Rimuovere per abilitare aggiornamento arrivi in modalità esclusivamente push
				aggiorna_arrivi = tpl.Aggiornatore(r, timedelta(seconds=20 if tempo_reale else 60), aggiorna_arrivi=tempo_reale, gtfs_rt_handler=gtfs_realtime_uploader)
				aggiorna_arrivi.start()
				WatchdogAggiornamentoRete(r).start()
			if tempo_reale_percorsi:
				aggiorna_percorsi = tpl.AggiornatorePercorsiAtac(r)
				aggiorna_percorsi.start()
				
			if download:
				aggiorna_download = tpl.AggiornatoreDownload(r, timedelta(seconds=20))
				aggiorna_download.start()

			print "Inizializzo supporto autocompletamento"
			ias = IndirizzoAutocompl.objects.all()
			cls.autocomplete = Autocomplete([("A%d" % ia.pk, ia.indirizzo) for ia in ias])

			print "Inizializzazione completata"
			
			if pause is not None:
				sleep(pause.seconds)
			cls.rete = r

			if tempo_reale:
				try:
					cls.aggiorna_arrivi.stop()
					print "Terminati thread di aggiornamento vecchia versione della rete"
				except Exception:
					pass
			if calcola_percorso:
				cls.grafo = g
				cls.gc = cls.rete.geocoder
			if tempo_reale:
				cls.aggiorna_arrivi = aggiorna_arrivi

		@classmethod
		def init_scheduler(cls):
			vs = paline.VersionePaline.objects.filter(inizio_validita__gt=datetime.now())
			cls.scheduler = Scheduler()
			for v in vs:
				cls.scheduler.insert(v.inizio_validita, cls.on_aggiorna_versione)
			cls.scheduler.start()
				
		@classmethod
		def on_aggiorna_versione(cls):
			cls.init_rete(timedelta(minutes=2))

		def exposed_percorso_su_mappa(
			self,
			id_percorso,
			mappa,
			path_img,
			con_stato=False,
			con_fermate=True,
			con_bus=True,
			fattore_thickness=1,
			con_percorso=True,
			con_bus_immediato=False,
		):
			serialize = False
			if mappa is None:
				serialize = True
				mappa = gmaps.Map()
			p = self.rete.percorsi[id_percorso]
			
			tipo = p.tipo
			"""
			(u"BU", u"Autobus"),
			(u"TR", u"Tram"),
			(u"ME", u"Metropolitana"),
			(u"FR", u"Ferrovia Regionale"),
			(u"FC", u"Ferrovia Concessa"),			
			"""
			arrivi = False
			if tipo in ['BU', 'TR']:
				arrivi = True
				icona_start = 'partenza.png'
				icona_stop = 'arrivo.png'
				icona_fermata = 'fermata.png'
				color = '#666666'
			elif tipo == 'ME':
				icona_start = 'metro.png'
				icona_stop = 'metro.png'
				icona_fermata = 'metro_fermata.png'				
				if p.id_linea == 'MEA':
					color = '#FF0000'
				elif p.id_linea == 'MEC':
					color = '#57B947'
				else:
					# Metro B
					color = '#0000FF'
			else:
				# FC o FR
				icona_start = 'treno.png'
				icona_stop = 'treno.png'
				icona_fermata = 'treno_fermata.png'			
				color = '#000000'

			bb = BoundingBox()
			img = path_img + icona_start
			capolinea = 1
			n = datetime.now()
			punti_wgs = []
			for t in p.tratti_percorso:
				punti_wgs_tratto = []
				palina = t.s.rete_palina
				c = gbfe_to_wgs84(palina.x, palina.y)
				bb.update(*c)
				if con_fermate and not palina.soppressa:
					mappa.add_marker_busstop(
							c,
							img,
							palina.id_palina if arrivi or capolinea else None,
							(16, 16),
							palina.nome,
							palina.nome,
							capolinea,
							anchor=(8, 8),
							id_percorso=id_percorso,
					)
				
				img = path_img + icona_fermata
				capolinea = 0
				punti = t.rete_tratto_percorsi.punti
				for x, y in punti:
					punti_locale = gbfe_to_wgs84(x, y)
					punti_wgs.append(punti_locale)
					punti_wgs_tratto.append(punti_locale)
				if con_stato:
					tp = t.rete_tratto_percorsi
					color_tr = None
					if tp.ultimo_aggiornamento is not None and n - tp.ultimo_aggiornamento < tpl.VALIDITA_TEMPO_ARCHI:
						v = 3.6 * tp.dist / tp.tempo_percorrenza
						if v <= 5:
							color_tr = '#000000'
						elif 5 < v <= 10:
							color_tr = '#FF0000'
						elif 10 < v <= 15:
							color_tr = '#FFFF00' if fattore_thickness > 1 else '#FFAA00'
						else:
							color_tr = '#FF7070' if fattore_thickness > 1 else '#00FF00'
					if con_percorso:
						mappa.add_polyline(punti_wgs_tratto, opacity=0.6, color=color, thickness=5 * fattore_thickness, zIndex=0)
					if color_tr is not None:
						mappa.add_polyline(punti_wgs_tratto, opacity=1, color=color_tr, thickness=2.5 * fattore_thickness, zIndex=1)
			if con_percorso and not con_stato:
				mappa.add_polyline(punti_wgs, opacity=0.8, color=color, thickness=3 * fattore_thickness)
			palina = t.t.rete_palina
			c = gbfe_to_wgs84(palina.x, palina.y)
			bb.update(*c)
			img = path_img + icona_stop
			if con_fermate:
				mappa.add_marker_busstop(
					c,
					img,
					palina.id_palina if arrivi else None,
					(16, 16),
					palina.nome,
					palina.nome,
					capolinea,
					anchor=(8, 8),
					id_percorso=id_percorso,		
				)
			if con_bus:
				mappa.add_realtime_route(id_percorso, path_img + "bus_percorso.png")
			if con_bus_immediato:
				vs = self.rete.get_veicoli_percorso(id_percorso)
				for v in vs:
					try:
						el = v.get_info(False)
						c = gbfe_to_wgs84(el['x'], el['y'])
						mappa.add_marker(
							c,
							path_img + 'bus_percorso.png',
							(16, 16),
							'Caricamento...',
							el['id_veicolo'],
							anchor=(8, 8),
							name=('arrivi_veicolo', (el['id_veicolo'], id_percorso)),
						)
					except:
						pass
			mappa.center_and_zoom(bb.get_center(), 13)
			db.reset_queries()
			if serialize:
				return pickle.dumps(mappa.serialize())

		# does not need autopickle
		def exposed_percorso_su_mappa_ap(self, param):
			param = pickle.loads(param)
			res = self.exposed_percorso_su_mappa(
				param['id_percorso'],
				None,
				param['path_img'],
				getdef(param, 'con_stato', False),
				getdef(param, 'con_fermate', True),
				getdef(param, 'con_bus', True),
				getdef(param, 'fattore_thickness', 1),
				getdef(param, 'con_percorso', True),
				getdef(param, 'con_bus_immediato', False),
			)
			return res

		def exposed_palina_su_mappa(self, id_palina, mappa, path_img):
			serialize = False
			if mappa is None:
				serialize = True
				mappa = gmaps.Map()			
			palina = self.rete.paline[id_palina]
			img = path_img + 'partenza.png'
			c = gbfe_to_wgs84(palina.x, palina.y)
			bb = BoundingBox()
			bb.update(*c)
			mappa.add_marker_busstop(
				c,
				img,
				palina.id_palina,
				(16, 16),
				"Caricamento...",
				palina.nome,
				0,
				anchor=(8, 8),
				open=True,
			)
			mappa.center_and_zoom(bb.get_center(), 12)
			db.reset_queries()
			if serialize:
				return pickle.dumps(mappa.serialize())

		# does not need autopickle
		def exposed_palina_su_mappa_ap(self, param):
			param = pickle.loads(param)
			res = self.exposed_palina_su_mappa(param['id_palina'], None, param['path_img'])
			return res

		@autopickle
		def exposed_carica_percorso_carpooling(self, param):
			pk = param['pk']
			try:
				carpoolinggraph.carica_percorsi(self.rete, self.dijkstra_queue, carpoolingmodels.PassaggioOfferto.objects.filter(pk=pk))		
			except Exception:
				print "Errore nel caricamento car pooling"
				logging.error(traceback.format_exc())

		@autopickle
		def exposed_carica_percorsi_carpooling(self, param):
			pks = param['pks']
			try:
				ps = [x for x in pks]
				carpoolinggraph.carica_percorsi(self.rete, self.dijkstra_queue, carpoolingmodels.PassaggioOfferto.objects.filter(pk__in=ps))		
			except Exception:
				print "Errore nel caricamento car pooling"
				logging.error(traceback.format_exc())

		def _carica_nodo_risorsa(self, ct_ris, id_ris):
			try:
				r = contenttype2model(ct_ris).objects.get(pk=id_ris)
				n = tpl.NodoRisorsa(r)
				self.dijkstra_queue.add_nodo(n)
				archi_conn = self.gc.connect_to_node(n)
				for a in archi_conn:
					self.dijkstra_queue.add_arco(a)
			except Exception:
				print "Errore nel caricamento nodo risorsa"
				logging.error(traceback.format_exc())			
				
		def _elimina_nodo_risorsa(self, ct_ris, id_ris):
			try:
				n = self.grafo.nodi[(6, ct_ris, id_ris)]
				self.dijkstra_queue.rm_nodo(n)
			except Exception:
				print "Errore nell'eliminazione nodo risorsa"
				logging.error(traceback.format_exc())			
		
		@autopickle
		def exposed_carica_nodo_risorsa(self, param):
			print "Aggiungo nodo risorsa"
			ct_ris = param['ct_ris']
			id_ris = param['id_ris']
			self._carica_nodo_risorsa(ct_ris, id_ris)
		
		@autopickle
		def exposed_elimina_nodo_risorsa(self, param):
			print "Elimino nodo risorsa"
			ct_ris = param['ct_ris']
			id_ris = param['id_ris']
			self._elimina_nodo_risorsa(ct_ris, id_ris)
			
		@autopickle
		def exposed_modifica_nodo_risorsa(self, param):
			print "Modifico nodo risorsa"
			ct_ris = param['ct_ris']
			id_ris = param['id_ris']
			self._elimina_nodo_risorsa(ct_ris, id_ris)
			self._carica_nodo_risorsa(ct_ris, id_ris)

		@autopickle
		def exposed_cerca_percorso(self, infopoint):
			# Begin parameters
			punti = infopoint['punti']
			auto = getdef(infopoint, 'mezzo', 1)
			piedi = getdef(infopoint, 'piedi', 1)
			bus = getdef(infopoint, 'bus', True)
			metro = getdef(infopoint, 'metro', True)
			ferro = getdef(infopoint, 'ferro', True)
			fc = ferro
			fr = ferro
			teletrasporto = getdef(infopoint, 'teletrasporto', False)
			max_distanza_bici = getdef(infopoint, 'max_distanza_bici', 5000)
			carpooling = getdef(infopoint, 'carpooling', False)
			data = getdef(infopoint, 'dt', datetime.now())
			linee_escluse = getdef(infopoint, 'linee_escluse', [])
			tipi_ris = getdef(infopoint, 'tipi_ris', [])
			quando = getdef(infopoint, 'quando', 0)
			carpooling_vincoli = getdef(infopoint, 'carpooling_vincoli', None)
			ztl = getdef(infopoint, 'ztl', [])
			bici_sul_tpl = getdef(infopoint, 'bici_sul_tpl', False)
			cerca_punti = getdef(infopoint, 'cerca_punti', False)
			# End parameters

			if auto == 3:
				bici = True
				auto = 1
			else:
				bici = False

			rev = quando == 3

			peer = Peer.objects.filter(daemon=daemon)[0]
			with peer.get_queue():
				print "Calcolo il percorso"
				le = set()
				tipi_ris = [int(t) for t in tipi_ris]
				if linee_escluse is not None:
					for l in linee_escluse:
						if l in self.rete.linee_equivalenti:
							le.update(self.rete.linee_equivalenti[l])
						else:
							le.add(l)
				# modi = ['modo_auto', 'modo_tpl', 'modo_pnr', 'modo_bnr', 'modo_carsharing', 'modo_carpooling']
				if auto == 4:
					ztl = [z.codice for z in ZTL.objects.all()]
				ztl = set(ztl)
				if auto < 2 or auto == 5:
					opzioni_cp = self.rete.get_opzioni_calcola_percorso(metro, bus, fc, fr, piedi, data, bici, le, True if auto==0 else False, carpooling, carpooling_vincoli, teletrasporto, ztl=ztl, bici_sul_tpl=bici_sul_tpl)
				elif auto == 2:
					opzioni_cp1 = self.rete.get_opzioni_calcola_percorso(metro, bus, fc, fr, piedi, data, bici, le, True, carpooling, carpooling_vincoli, teletrasporto, ztl=ztl, bici_sul_tpl=bici_sul_tpl)
					opzioni_cp2 = self.rete.get_opzioni_calcola_percorso(metro, bus, fc, fr, piedi, data, bici, le, False, carpooling, carpooling_vincoli, teletrasporto, ztl=ztl, bici_sul_tpl=bici_sul_tpl)
				elif auto == 4:
					opzioni_cp1 = self.rete.get_opzioni_calcola_percorso(metro, bus, fc, fr, piedi, data, bici, le, False, carpooling, carpooling_vincoli, teletrasporto, ztl=ztl, tpl=True, bici_sul_tpl=bici_sul_tpl)
					opzioni_cp2 = self.rete.get_opzioni_calcola_percorso(metro, bus, fc, fr, piedi, data, bici, le, True, carpooling, carpooling_vincoli, teletrasporto, True, ztl=ztl, tpl=True, bici_sul_tpl=bici_sul_tpl)

				nodi_geo = []
				nodi_del = []

				s_context = {
					'primo_tratto_bici': bici,
					'max_distanza_bici': max_distanza_bici,
					'nome_strada': -1,
					'carpooling_usato': -1,
					'distanza_piedi': 0.0,
				}

				try:
					if cerca_punti:
						# Ricerca di punti vicini
						ds = []
						start = punti[0]
						punti = punti[1:]

						# Begin specific params
						num_ris = getdef(infopoint, 'num_ris', len(punti))
						max_distanza = getdef(infopoint, 'max_distanza', 5000)
						# End specific params

						num_ris = min(num_ris, len(punti))

						s, a = self.get_nodi_from_infopoint(start)
						if len(a) > 0:
							nodi_del.append(s)
						for p in punti:
							d, a = self.get_nodi_from_infopoint(p, tpl.NodoPuntoArrivo)
							d.nome = p['ricerca']
							ds.append(d)
							if len(a) > 0:
								nodi_del.append(d)

						rv = PuntiVicini(num_ris, ds)
						opzioni_cp['cerca_vicini'] = 'punti'
						with self.dijkstra_queue.get_dijkstra() as d:
							d.cerca_vicini(s, rv, max_distanza, dep_time=data, opt=opzioni_cp, s_context=s_context, solo_pedonale=False)

						out = []
						for nodo, dist, tempo in rv.ris:
							out.append({
								'nome': nodo.nome,
								'dist': dist,
								'tempo': (tempo - data).seconds,
							})

					else:
						# Cerca percorso ordinario
						for p in punti:
							s, a = self.get_nodi_from_infopoint(p)
							nodi_geo.append(s)
							if len(a) > 0:
								nodi_del.append(s)

						s = nodi_geo[0]
						percorso = None
						pas = carpoolingmodels.PercorsoAutoSalvato(self.grafo)
						orario_inizio = datetime.now()
						data_partenza = data
						for i in range(1, len(nodi_geo)):
							t = nodi_geo[i]

							if auto not in [2, 4] and len(tipi_ris) == 0:
								with self.dijkstra_queue.get_dijkstra() as d:
									percorso, data = d.calcola_e_stampa(s, t, opzioni_cp, data, percorso, s_context=s_context, rev=rev)
							else:
								with self.dijkstra_queue.get_dijkstra(2) as d:
									d1, d2 = d
									if auto == 2 or auto == 4:
										opzioni_cp1['cerca_vicini'] = 'risorse'
										opzioni_cp1['tipi_ris'] = tipi_ris
										opzioni_cp2['cerca_vicini'] = 'risorse'
										opzioni_cp2['tipi_ris'] = tipi_ris
										percorso, data = graph.calcola_e_stampa_vicini_tragitto(d1, d2, s, t, opt=opzioni_cp1, dep_time=data, tr=percorso, s_context=s_context, opt2=opzioni_cp2, mandatory=False)
									else:
										opzioni_cp['cerca_vicini'] = 'risorse'
										opzioni_cp['tipi_ris'] = tipi_ris
										percorso, data = graph.calcola_e_stampa_vicini_tragitto(d1, d2, s, t, opt=opzioni_cp, dep_time=data, tr=percorso, s_context=s_context)

							percorso.partenza = {}
							percorso.arrivo = {}
							tratto.formatta_percorso(percorso, 'auto_salvato', pas, {'flessibilita': timedelta(0)})
							indicazioni_icona = tratto.PercorsoIndicazioniIcona()
							tratto.formatta_percorso(percorso, 'indicazioni_icona', indicazioni_icona, {})
							s = t
							tempo_calcolo = datetime.now() - orario_inizio
							da = percorso.get_punto_wgs_84()
							a = percorso.get_punto_fine_wgs_84()
							l = paline.LogCercaPercorso(
								orario_richiesta=orario_inizio,
								orario_partenza=data_partenza,
								da=punti[i - 1]['ricerca'],
								a=punti[i]['ricerca'],
								piedi=piedi,
								max_bici=-1 if not bici else max_distanza_bici,
								tempo_calcolo=tempo_calcolo.seconds + tempo_calcolo.microseconds / 1000000.0,
								bus=bus,
								metro=metro,
								fc=fc,
								fr=fr,
								auto=auto,
								carpooling=carpooling,
								linee_escluse=",".join(list(linee_escluse)),
								da_lng=da[0],
								da_lat=da[1],
								a_lng=a[0],
								a_lat=a[1],
								distanza=percorso.get_distanza(),
								tempo=int(percorso.get_tempo_totale()),
							)
							l.save()

						start = punti[0]
						stop = punti[-1]

						if 'palina' in start:
							percorso.partenza['nome_palina'] = self.rete.paline[start['palina']].nome
							percorso.partenza['id_palina'] = start['palina']
						else:
							percorso.partenza['address'] = start['address']
						if 'palina' in stop:
							percorso.arrivo['nome_palina'] = self.rete.paline[stop['palina']].nome
							percorso.arrivo['id_palina'] = stop['palina']
						else:
							percorso.arrivo['address'] = stop['address']

				except Exception:
					print "Errore nel calcola percorso"
					logging.error(traceback.format_exc())

				for n in nodi_del:
					self.dijkstra_queue.rm_nodo(n)

				db.reset_queries()
				if auto < 2 or auto == 5:
					del opzioni_cp['dijkstra']
				else:
					del opzioni_cp1['dijkstra']
					del opzioni_cp2['dijkstra']

				#percorso.attualizza(datetime.now() + timedelta(hours=12), self.rete, self.grafo, opzioni_cp)
				if cerca_punti:
					return out

				else:
					return {
						'percorso': percorso,
						'percorso_auto_salvato': pas.serialize(),
						#'opzioni': opzioni_cp, # Servirà per la profilazione. Bug con opzioni_cp['tipi_luogo'], non riesce a serializzarlo
					}

			
		@autopickle
		def exposed_attualizza_percorsi(self, d):
			pk_percorsi = d['pk_percorsi']
			pss = paline.PercorsoSalvato.objects.filter(pk__in=pk_percorsi)
			out = []
			for ps in pss:
				percorso = ps.percorso
				percorso.attualizza(datetime.now(), self.rete, self.grafo, ps.opzioni)
				out.append({'punti': ps.punti, 'percorso': percorso})
			return out

		def exposed_carica_rete(self):
			print "Caricamento rete in corso"
			lancia_processo_caricamento_rete()
			db.reset_queries()
			
		def get_nodi_from_infopoint(self, info, node_type=geocoder.NodoGeocoder):
			"""
			Restituisce nodi ed archi dal geocoding di infopoint.
			
			Se len(archi) > 0, archi e nodi sono stati aggiunti al grafo e dovranno essere rimossi dopo l'uso.
			Altrimenti, i nodi sono già presenti (e connessi), quindi non dovranno essere rimossi
			"""
			archi_geo = []
			if 'palina' in info:
				s = self.grafo.nodi[(1, info['palina'])]
			elif 'risorsa' in info:
				l = info['risorsa'] # (ct_risorsa, id_risorsa)
				s = self.grafo.nodi[(6, l[0], l[1])]
			else:
				s, archi = self.gc.connect_to_point((info['x'], info['y']), node_type=node_type)
				self.dijkstra_queue.add_nodo(s)
				for a in archi:
					self.dijkstra_queue.add_arco(a)
					archi_geo.append(a)
			return s, archi_geo
			
			
		def exposed_oggetti_vicini(self, start):
			try:
				print "Oggetti vicini"
				rv = PalineVicine(7, 12)
				s, archi_geo = self.get_nodi_from_infopoint(start)
				opt = copy(graph.opzioni_cp)
				opt['cerca_vicini'] = 'paline'
				with self.dijkstra_queue.get_dijkstra() as d:
					try:
						d.cerca_vicini(s, rv, 1000, opt=opt)
					except Exception:
						print "Errore nella ricerca di paline vicine"
						logging.error(traceback.format_exc())
				if len(archi_geo) > 0:
					self.dijkstra_queue.rm_nodo(s)
				return pickle.dumps((rv.paline, rv.linee_ord))
			except Exception:
				traceback.print_exc()

		# does not need autopickle
		def exposed_oggetti_vicini_ap(self, param):
			param = pickle.loads(param)
			return self.exposed_oggetti_vicini(param['start'])

		def exposed_risorse_vicine(self, start, tipi_ris, num_ris, max_distanza=1000):
			print "Risorse vicine"
			mappa = gmaps.Map()
			rv = RisorseVicine(num_ris)
			s, archi_geo = self.get_nodi_from_infopoint(start)
			opt = copy(graph.opzioni_cp)
			opt['cerca_vicini'] = 'risorse'
			opt['tipi_ris'] = [int(t) for t in tipi_ris]
			with self.dijkstra_queue.get_dijkstra() as d:
				try:
					d.cerca_vicini(s, rv, max_distanza, opt=opt)
				except Exception:
					print "Errore nella ricerca di paline vicine"
					logging.error(traceback.format_exc())
			if len(archi_geo) > 0:
				self.dijkstra_queue.rm_nodo(s)
		
			for ln in rv.ris:
				l = ln[0].get_risorsa()
				x, y = l.geom
				#self, point, icon, icon_size=(20, 20), infobox=None, label=None, id_toggle=None, anchor=None, name=None, open=False, drop_callback=''
				mappa.add_marker(
					gbfe_to_wgs84(x, y),
					icon=l.icon,
					icon_size=l.icon_size,
					infobox=l.nome_luogo,
					desc=l.descrizione(),
					distance=tratto.arrotonda_distanza(ln[1]),
				)
			mappa.add_marker(
				gbfe_to_wgs84(start['x'], start['y']),
				icon='/paline/s/img/partenza_percorso.png',
				icon_size=(32, 32),
				anchor=(16, 32),
				infobox="Sono qui",
			)
			db.reset_queries()
			return pickle.dumps(mappa.serialize())

		# does not need autopickle
		def exposed_risorse_vicine_ap(self, param):
			param = pickle.loads(param)
			return self.exposed_risorse_vicine(param['start'], param['tipi_ris'], param['num_ris'], getdef(param, 'max_distanza', 1000))

		def exposed_tempi_attesa(self, id_palina):
			#print "Servo arrivi"
			p = self.rete.paline[id_palina]
			arrivi = []
			for k in p.fermate:
				f = p.fermate[k]
				f.rete_percorso.aggiorna_posizione_veicoli()
				if f.is_valida():
					for a in f.arrivi:
						id_veicolo = a['id_veicolo']
						v = self.rete.veicoli[id_veicolo]
						id_percorso = a['id_percorso']
						if v.is_valido():
							a2 = copy(a)
							dest_zone = self.rete.percorsi[id_percorso].tratti_percorso[-1].t.rete_palina.zona
							a2['dest_zone'] = dest_zone
							if 'tratto_percorso' in a2:
								del a2['tratto_percorso']
							if a2['a_capolinea']:
								if v.orario_partenza_capolinea is not None:
									a2['orario_partenza_capolinea'] = v.orario_partenza_capolinea
							arrivi.append(a2)
			db.reset_queries()
			return pickle.dumps(arrivi)

		# does not need autopickle
		def exposed_tempi_attesa_ap(self, param):
			param = pickle.loads(param)
			return self.exposed_tempi_attesa(param['id_palina'])


		@autopickle
		def exposed_primi_arrivi_per_paline(self, param):
			#print "Servo arrivi"
			out = {}
			for id_palina in param['id_paline']:
				p = self.rete.paline[id_palina]
				arrivi = []
				n = datetime.now()
				for k in p.fermate:
					f = p.fermate[k]
					f.rete_percorso.aggiorna_posizione_veicoli()
					if len(f.arrivi) > 0:
						a = f.arrivi[0]
						a2 = copy(a)
						if 'tratto_percorso' in a2:
							del a2['tratto_percorso']
						if a2['a_capolinea']:
							id_veicolo = a2['id_veicolo']
							v = self.rete.veicoli[id_veicolo]
							if v.orario_partenza_capolinea is not None:
								a2['orario_partenza_capolinea'] = v.orario_partenza_capolinea
						arrivi.append(a2)
				out[id_palina] = arrivi
			db.reset_queries()
			return out

		def exposed_arrivi_veicolo(self, id_veicolo):
			#print "Servo arrivi veicolo"
			if id_veicolo in self.rete.veicoli:
				arrivi = self.rete.veicoli[id_veicolo].get_arrivi()
				return pickle.dumps(arrivi)
			db.reset_queries()
			return None

		# does not need autopickle
		def exposed_arrivi_veicolo_ap(self, param):
			param = pickle.loads(param)
			res = self.exposed_arrivi_veicolo(param['id_veicolo'])
			if res is not None:
				return res
			return pickle.dumps(None)

		def exposed_percorso_fermate(self, id_percorso):
			#print "Servo veicoli percorso"
			db.reset_queries()
			return pickle.dumps(self.rete.percorsi[id_percorso].stato())

		# does not need autopickle
		def exposed_percorso_fermate_ap(self, param):
			param = pickle.loads(param)
			return self.exposed_percorso_fermate(param['id_percorso'])

		def _vehicle_position_comp_key(self, v):
			if v['a_capolinea']:
				inf = float('inf')
				o = v['orario_partenza_capolinea']
				if o is None:
					return (inf, datetime.now() + timedelta(days=100))
				return (inf, o)
			return (v['distanza_capolinea'], None)

		def exposed_veicoli_percorso(self, id_percorso, get_arrivi, get_distanza=False):
			"""
			Vehicles are sorted starting from "oldest" (nearest to final destination)
			"""
			#print "Servo veicoli percorso"
			vs = self.rete.get_veicoli_percorso(id_percorso)
			out = []
			h23 = datetime.now() + timedelta(hours=23)
			d1 = timedelta(days=1)
			for v in vs:
				i = v.get_info(get_arrivi, True)
				# Workaround for correcting error in GTFS: sometimes departure time
				# belongs to the following day
				if i['a_capolinea']:
					op = i['orario_partenza_capolinea']
					while op is not None and op > h23:
						op -= d1
					i['orario_partenza_capolinea'] = op
				out.append(i)
			out.sort(key=self._vehicle_position_comp_key)
			db.reset_queries()
			return pickle.dumps(out)

		@autopickle
		def exposed_route_stats(self, param):
			out = {}
			stats = self.rete.stat_percorsi
			for route_id in param['route_ids']:
				if route_id in stats:
					out[route_id] = stats[route_id]
					r = self.rete.percorsi[route_id]
					p = r.tratti_percorso[-1].t.rete_palina
					out[route_id]['dest_zone'] = p.zona
					if r.id_linea in self.rete.gtfs_alerts:
						out[route_id]['alerts'] = self.rete.gtfs_alerts[r.id_linea]
			return out

		# does not need autopickle
		def exposed_veicoli_percorso_ap(self, param):
			"""
			Vehicles are sorted starting from "oldest" (nearest to final destination)
			"""
			param = pickle.loads(param)
			if not 'get_distanza' in param:
				param['get_distanza'] = False
			return self.exposed_veicoli_percorso(param['id_percorso'], param['get_arrivi'], param['get_distanza'])

		def exposed_veicoli_tutti_percorsi(self, get_arrivi, get_distanza=False):
			#print "Servo veicoli percorso"
			return pickle.dumps(self.rete.get_veicoli_tutti_percorsi(get_arrivi, get_distanza))

		# does not need autopickle
		def exposed_veicoli_tutti_percorsi_ap(self, param):
			param = pickle.loads(param)
			if not 'get_distanza' in param:
				param['get_distanza'] = False
			return self.exposed_veicoli_tutti_percorsi(param['get_arrivi'], param['get_distanza'])

		def exposed_serializza_dinamico(self):
			return pickle.dumps(self.rete.serializza_dinamico(), 2)

		@autopickle
		def exposed_deserializza_dinamico(self, param):
			print "Deserializing..."
			self.rete.deserializza_dinamico(param)
			print "Deserialization done"

		@autostored()
		def exposed_deserializza_dinamico_stored(self, param):
			print "Deserializing stored network..."
			self.rete.deserializza_dinamico(param)
			print "Stored deserialization done"

		def exposed_get_rete_e_grafo(self):
			return self.rete, self.grafo

		@autostored()
		def exposed_deserializza_dinamico_veicoli_stored(self, param):
			print "Deserializing stored vehicles..."
			self.rete.deserializza_dinamico_veicoli(param)
			print "Stored deserialization done"

		@autopickle
		def exposed_deserializza_dinamico_veicoli(self, param):
			print "Deserializing vehicles..."
			self.rete.deserializza_dinamico_veicoli(param)
			print "Deserialization done"

		def exposed_get_rete_e_grafo(self):
			return self.rete, self.grafo

		@autopickle
		def exposed_coordinate_palina(self, res):
			palina = self.rete.paline[res['id_palina']]
			p = gbfe_to_wgs84(palina.x, palina.y)
			return {
				'lat': p[1],
				'lng': p[0]
			}


		@autopickle
		def exposed_log_dati_avm_romatpl(self, dati):
			# Esegue il log dei dati di roma tpl
			print 'Dati arrivati'
			try:
				dt = dati['dataora']
				logavm = LogAvm(
					id_gestore = Gestore.objects.by_date().get(descrizione="Roma TPL"),
					id_veicolo = dati['id_vettura'],
					data = date(year=dt.year, month=dt.month, day=dt.day),
					ora = time(hour=dt.hour, minute=dt.minute, second=dt.second),
					lat = dati['lat'],
					lon = dati['lon'],
					gps_fix = dati['tipo_fix'],
					id_linea = dati['id_linea_attuale'],
					id_percorso = dati['targa_percorso'],
					evento = dati['tipo_evento'],
					numero_passeggeri = dati['numero_passeggeri'],
					carico_passeggeri = dati['carico_passeggeri']
				)
				logavm.save()
			except:
				traceback.print_exc()
			return 'OK'

		@autopickle
		def exposed_qualita(self, dati):
			return {
				'atac': self.rete.qualita_atac.get_qualita()
			}

		@autopickle
		def exposed_analizza_consistenza_rete(self, dati):
			return tpl.analizza_consistenza_rete(self.rete, getdef(dati, 'correggi', False))

		@autopickle
		def exposed_statistiche(self, param):
			percorsi = []
			for id_percorso in self.rete.percorsi:
				p = self.rete.percorsi[id_percorso]
				if not p.soppresso:
					percorsi.append({
						'id_percorso': id_percorso,
						'descrizione': p.descrizione,
						'arrivo': p.get_destinazione(),
						'stat': p.statistiche(),
					})
			return {
				'percorsi': percorsi,
			}

		@autopickle
		def exposed_autocomplete(self, param):
			return self.autocomplete.find(param['lookup'])[:10]

		@autopickle
		def exposed_veicoli_problematici(self, param):
			limite = datetime.now() - timedelta(minutes=5)
			veicoli = []
			for id_veicolo in self.rete.veicoli:
				v = self.rete.veicoli[id_veicolo]
				if v.problematico and v.ultimo_aggiornamento >= limite:
					percorso = v.tratto_percorso_problematico.rete_percorso
					veicoli.append({
						'id_veicolo': v.id_veicolo,
						'id_percorso': percorso.id_percorso,
						'id_linea': percorso.id_linea,
						'destinazione': percorso.destinazione(),
						'fuori_percorso': v.fuori_percorso,
						'lontano_1d': v.lontano_1d,
						'distanza_1d': v.distanza_1d,
						'lontano_2d': v.lontano_2d,
						'distanza_2d': v.distanza_2d,
						'tot_fermate': len(percorso.tratti_percorso) + 1,
						'prog_atac': v.progressiva_atac,
						'prog_ric': v.progressiva_ric,
					})

			return {'veicoli': veicoli}


	Trovalinea.init_rete()
	Trovalinea.init_scheduler()
	return Trovalinea 




