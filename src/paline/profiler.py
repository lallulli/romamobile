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

import pstats, cProfile, threading, rpyc
from datetime import date, time, datetime, timedelta
import percorso.views
import settings
import random
from mercury.models import Mercury
import cPickle as pickle
from parcheggi import models as parcheggi
from servizi.utils import model2contenttype

import tpl
import pyximport
pyximport.install()

import grafo


class Profiler(object):
	def __init__(self, retina=False):
		object.__init__(self)
		self.retina = retina
		self.r, self.g = tpl.carica_rete_e_grafo(retina)
		#tpl.test_ferrovia(self.r, self.g)
		self.dp = grafo.DijkstraPool(self.g, 2)
		
	def profile(self):
		with self.dp.get_dijkstra() as d:
			if self.retina:
				s = self.g.nodi[(1, '71502')]
				t = self.g.nodi[(1, 'BP8')]
				# s = self.g.nodi[(1, '90122')]
				#t = self.g.nodi[(1, '90128')]
			else:
				#s = self.g.nodi[(11, 1396215581)]
				#t = self.g.nodi[(11, 298921845)]
				s = self.g.nodi[(1, '70221')]
				t = self.g.nodi[(1, '78272')]

			s_context = {
			'primo_tratto_bici': False,
			'max_distanza_bici': 25000,
			'nome_strada': -1,
			'distanza_piedi': 0,
			}

			opz = self.r.get_opzioni_calcola_percorso(True, True, True, False, 1, primo_tratto_bici=False)
			s_context = {
				'primo_tratto_bici': False,
				'max_distanza_bici': 25000,
				'nome_strada': -1,
				'distanza_piedi': 0,
			}
			cProfile.runctx("d.calcola_e_stampa(s, t, opz, s_context=s_context)", globals(), locals(), "Profile.prof")
			s = pstats.Stats("Profile.prof")
			s.strip_dirs().sort_stats("time").print_stats()
		
	def test(self):
		with self.dp.get_dijkstra() as d:
			if self.retina:
				s = self.g.nodi[(1, '71502')]
				t = self.g.nodi[(1, 'BP8')]
			else:
				s = self.g.nodi[(1, '70221')]
				t = self.g.nodi[(1, '78272')]
				
			s_context = {
				'primo_tratto_bici': False,
				'max_distanza_bici': 25000,
				'nome_strada': -1,
				'distanza_piedi': 0,
			}
	
			opz = self.r.get_opzioni_calcola_percorso(True, True, True, False, 1, primo_tratto_bici=False)
			#opz = self.r.get_opzioni_calcola_percorso(False, False, False, False, 1, primo_tratto_bici=True)
			d.calcola_e_stampa(s, t, opz, s_context=s_context)
			
			
	def test_cerca_vicini_tragitto(self):
		with self.dp.get_dijkstra() as d1:
			with self.dp.get_dijkstra() as d2:
				if self.retina:
					s = self.g.nodi[(1, '71502')]
					t = self.g.nodi[(1, 'BP8')]
				else:
					s = self.g.nodi[(1, '70221')]
					t = self.g.nodi[(1, '78272')]
					
				s_context = {
					'primo_tratto_bici': False,
					'max_distanza_bici': 25000,
					'nome_strada': -1,
					'distanza_piedi': 0,
				}
				
				opz = self.r.get_opzioni_calcola_percorso(True, True, True, False, 1, primo_tratto_bici=False)
				opz['cerca_vicini'] = 'luoghi'
				opz['tipi_luogo'] = [model2contenttype(parcheggi.Autorimessa)]
				#opz = self.r.get_opzioni_calcola_percorso(False, False, False, False, 1, primo_tratto_bici=True)
				grafo.cerca_vicini_tragitto(d1, d2, s, t, opt=opz,  s_context=s_context)


class TestCaricoCP(threading.Thread):
	def __init__(self, n):
		threading.Thread.__init__(self)
		self.n = n
	
	def run(self):
		i = [
			'Via Vasi',
			'Via Ostiense 131',
			'Via Columbia 1',
			'Via Cassia 1036',
			'Piazzale degli Archivi 40',
			'Via Sondrio 10',
			'Via Igino Giordani 5'
		]
		random.shuffle(i)
		print i[:2]
		start = percorso.views.infopoint_to_cp(i[0])
		stop = percorso.views.infopoint_to_cp(i[1])
		c = Mercury.rpyc_connect_any_static(settings.MERCURY_WEB)
		t1 = datetime.now()
		print "Invoco %d" % self.n
		trs = c.root.calcola_percorso([start, stop], 1, True, True, True, True, pickle.dumps(datetime.now()), True)
		print "Fatto %d" % self.n

#self, punti, piedi, bus, metro, fc, fr, pickled_date, bici=False, max_distanza_bici=5000, linee_escluse=None, auto=False, carpooling=False, carpooling_vincoli=None, teletrasporto=False):
		

class TestCaricoOV(threading.Thread):
	def run(self):
		i = [
			'Via Vasi',
			'Via Ostiense 131',
			'Via Columbia 1',
			'Via Cassia 1036',
			'Piazzale degli Archivi 40',
			'Via Sondrio 10',
			'Via Igino Giordani 5'
		]
		random.shuffle(i)
		print i[:1]
		start = percorso.views.infopoint_to_cp(i[0])

		c = Mercury.rpyc_connect_any_static(settings.MERCURY_WEB)
		c.root.oggetti_vicini(self, start)
		
		
def test_carico_cp(n=10):
	for a in range(n):
		TestCaricoCP(a).start()
		#TestCaricoOV().start()