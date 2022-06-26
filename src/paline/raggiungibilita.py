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

from grafo import DijkstraPool
import datetime

def test_raggiungibilita(g, s_id):
	dq = DijkstraPool(g, 1)
	
	with dq.get_dijkstra() as d:
	
		unr = set()
		s = g.nodi[s_id]
		
		opzioni_cp = {
			'metro': False,
			'bus': False,
			'fc': False,
			'fr': False,
			'v_piedi': 1,
			'v_bici': 1,
			't_sal_bus': 1,
			't_disc_bus': 1,
			't_sal_metro': 1,
			't_disc_metro': 1,
			't_sal_treno': 1,
			't_disc_treno': 1,
			't_sal_fc': 1,
			't_disc_fc': 1,
			't_disc_bici': 1,
			'indici_stat': [],
			'penalizzazione_bus': 1,
			'penalizzazione_metro': 1,
			'penalizzazione_fc': 1,
			'penalizzazione_treno': 1,
			'coeff_penal_pedonale': 0,
			'primo_tratto_bici': False,
			't_bici_cambio_strada': 1,
			'linee_escluse': [],
			'auto': True,
			'car_pooling': False,
			'utente': -1,
			'penalizzazione_auto': 1,
			'rete': None,
			'ztl': set(),
			'tpl': True,
		} 
		
		
		s.context_i = 0
		d.context[0] = {
			'primo_tratto_bici': False,
			'max_distanza_bici': 0,
			'nome_strada': -1,
		}
		
		unr = d.dijkstra(s, [], complete=True, opt=opzioni_cp, get_unreachable=True)
		unr.update(d.rev_dijkstra(s, [], complete=True, opt=opzioni_cp, get_unreachable=True))
				
		print "%d unreachable nodes found out of %d" % (len(unr), len(g.nodi))
		return unr

def elimina_nodi_non_raggiungibili(g, unr):
	tbd = []
	print "Before: %d edges id's" % len(g.archi)
	cnt = 0
	for eid in g.archi:
		e = g.archi[eid]
		if (e.s in unr) or (e.t in unr):
			tbd.append(eid)
			cnt += 1
	for eid in tbd:
		del g.archi[eid]
	print "After: %d edges id's" % len(g.archi)
	print "%d edges deleted" % cnt		
		
	tbd = []
	for nid in g.nodi:
		v = g.nodi[nid]
		if v in unr:
			tbd.append(nid)
		else:
			# Il nodo è raggiungibile, ma occorre ripulire le sue fstar e bstar
			es = v.fstar
			tbd2 = []
			for e in es:
				if (not e.id in g.archi):
					tbd2.append(e)
			for e in tbd2:
				v.fstar.remove(e)
			es = v.bstar
			tbd2 = []
			for e in es:
				if (not e.id in g.archi):
					tbd2.append(e)
			for e in tbd2:
				v.bstar.remove(e)
	for nid in tbd:
		del g.nodi[nid]
	print "Unreachable nodes deleted"
	
def rendi_fortemente_connesso(g, sid=(11, 247845823)):
	print "Estrazione componente fortemente connessa"
	unr = test_raggiungibilita(g, sid)
	elimina_nodi_non_raggiungibili(g, unr)
		
