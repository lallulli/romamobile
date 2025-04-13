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
from servizi.utils import RPyCAllowRead, modifica_url_con_storia, getdef
from django.utils.safestring import mark_safe
from servizi.utils import ricapitalizza
from geomath import gbfe_to_wgs84, segment_point_dist, distance, piede_perpendicolare
from django.utils.translation import ugettext as _
from django.template.defaultfilters import date as datefilter
from pprint import pprint
import cPickle as pickle

class Tratto(RPyCAllowRead):
	def __init__(self, parent, tempo):
		RPyCAllowRead.__init__(self)
		self.sub = []
		self.tempo_attesa = 0
		self.tempo_percorrenza = 0
		self.distanza = 0
		self.poly = []
		self.parent = parent
		self.tempo = tempo
		if parent is not None:
			parent.sub.append(self)
			
	def __getstate__(self):
		state = self.__dict__.copy()
		del state['parent']
		return state
		
	def __setstate__(self, state):
		self.__dict__.update(state)
		for s in self.sub:
			s.__dict__['parent'] = self
		if not 'parent' in self.__dict__:
			self.__dict__['parent'] = None
		
	def get_funzione_ric(self, fun_get, val_init=0, fun_comb=lambda s, v, e: v + e):
		"""
		Estrae ricorsivamente dai figli e combina i risultati
		
		val_init: valore di default
		fun_get(self): estrae i dati dalle foglie (self)
		fun_comb(self, val, ext): estende l'oggetto che contiene i risultati (val) con i nuovi risultati (ext)
		"""
		if len(self.sub) == 0:
			return fun_get(self)
		v = val_init
		for s in self.sub:
			v = fun_comb(self, v, s.get_funzione_ric(fun_get, val_init, fun_comb))
		return v


	def get_bounding_box(self):
		n = w = e = s = None
		ps = self.get_poly()

		for p in ps:
			if n is None:
				n = s = p[1]
				w = e = p[0]
			else:
				n = max(p[1], n)
				s = min(p[1], s)
				w = min(p[0], w)
				e = max(p[0], e)

		if n is not None:
			return (w, n), (e, s)

		return None

	def get_bounding_box_wgs84(self):
		bb = self.get_bounding_box()
		if bb is None:
			return None
		nw, se = bb
		nw_w = gbfe_to_wgs84(nw[0], nw[1])
		se_w = gbfe_to_wgs84(se[0], se[1])
		return (nw_w, se_w)

		
	def get_poly(self):
		return self.get_funzione_ric(
			lambda s: s.poly,
			[],
			lambda s, v, e: v + e,
		)
		
	def get_poly_wgs84(self):
		return [gbfe_to_wgs84(p[0], p[1]) for p in self.get_poly()]
	
	def get_punto(self):
		p = self.get_poly()
		if len(p) > 0:
			return p[0]
		return None
	
	def get_punto_wgs_84(self):
		p = self.get_punto()
		if p is None:
			return None
		return gbfe_to_wgs84(p[0], p[1])
	
	def get_punto_fine(self):
		p = self.get_poly()
		if len(p) > 0:
			return p[-1]
		return None
	
	def get_punto_fine_wgs_84(self):
		p = self.get_punto_fine()
		if p is None:
			return None
		return gbfe_to_wgs84(p[0], p[1])	
		
	def get_tempo_attesa(self):
		return self.get_funzione_ric(lambda s: s.tempo_attesa)
		
	def get_tempo_percorrenza(self):
		return self.get_funzione_ric(lambda s: s.tempo_percorrenza)

	def get_distanza(self):
		return self.get_funzione_ric(lambda s: s.distanza)
	
	def get_tempo_totale(self):
		#print "Tempo attesa:", self.get_tempo_attesa()
		#print "Tempo percorrenza:", self.get_tempo_percorrenza()
		return self.get_tempo_attesa() + self.get_tempo_percorrenza()
	
	def stampa(self, indent=0):
		self.stampa_nric(indent)
		for s in self.sub:
			s.stampa(indent + 1)

	def stampa_nric(self, indent=0):
		spazi = "  " * indent
		print spazi + "Tipo: ", type(self)
		print spazi + "Partenza alle: ", self.tempo
		print spazi + "Tempo attesa: ", self.tempo_attesa
		print spazi + "Tempo percorrenza: ", self.tempo_percorrenza
		print spazi + "Tempo attesa ric.:", self.get_tempo_attesa()
		print spazi + "Tempo percorrenza ric.:", self.get_tempo_percorrenza()
		print spazi + "Tempo totale ric.:", self.get_tempo_totale()
		print spazi + "Arrivo alle: ", self.tempo + timedelta(seconds=self.get_tempo_totale())
		print
			
	def ricalcola_tempi(self, rete, grafo, opz):
		pass
			
	def attualizza(self, tempo, rete, grafo, opz):
		self.tempo = tempo
		for s in self.sub:
			s.attualizza(tempo, rete, grafo, opz)
			tempo += timedelta(seconds=s.get_tempo_totale())
		self.ricalcola_tempi(rete, grafo, opz)

	def piu_vicino(self, punto):
		"""
		Trova il sottotratto più vicino al punto.

		Restituisce la tupla (dist, indici, progressive, lunghezze, proiez_punto)
		dist: distanza punto-segmento più vicino (None se il tratto non ha alcun segmento)
		indici: lista di indici (riferiti all'array sub) che definisce un cammino radice-foglia dell'albero dei tratti
		progressive: lista delle distanze della proiezione del punto sul segmento, a partire dal primo punto
			di ciascuno dei sottotratti del percorso radice-foglia
		lunghezze: lista delle lunghezze totali dei tratti del cammino radice-foglia. Può essere usato, ad esempio,
			insieme alle progressive per calcolare le progressive inverse, cioè le progressive fino alla fine dei tratti
		proiez_punto: proiezione del punto sul tratto
		"""
		if len(self.sub) == 0:
			mindist, minprog, minpp = None, None, None
			a = None
			prog = 0
			for b in self.poly:
				if a is not None:
					dist = segment_point_dist(a, b, punto)
					if mindist is None or dist < mindist:
						mindist = dist
						pp = piede_perpendicolare(a, b, punto)
						minprog, minpp = prog + distance(a, pp), pp
					prog += distance(a, b)
				a = b
			return mindist, [], [minprog], [prog], minpp
		else:
			mindist, minind, minprog, minlung, minpp = None, None, None, None, None
			disttot = 0
			# Cerca il figlio più vicino
			i = 0
			n = len(self.sub)
			for i in range(n):
				s = self.sub[i]
				dist, ind, prog, lung, pp = s.piu_vicino(punto)
				if dist is not None and (mindist is None or dist < mindist):
					mindist, minind, minprog, minlung, minpp = dist, [i] + ind, [disttot + prog[0]] + prog, lung, pp
				disttot += lung[0]
			return mindist, minind, minprog, [disttot] + minlung, minpp




class TrattoRoot(Tratto):
	def __init__(self, tempo):
		Tratto.__init__(self, None, tempo)
		self.partenza = None
		self.arrivo = None

class TrattoBus(Tratto):
	def __init__(self, parent, tempo, rete_fermata_s, tempo_attesa, tipo_attesa, attesa_salita):
		Tratto.__init__(self, parent, tempo)
		fermata = rete_fermata_s
		palina = fermata.rete_palina
		self.id_percorso = fermata.rete_percorso.id_percorso
		self.descrizione_percorso = ricapitalizza(fermata.rete_percorso.descrizione)
		self.id_linea = fermata.rete_percorso.id_linea
		self.destinazione = ricapitalizza(fermata.rete_percorso.tratti_percorso[-1].t.rete_palina.nome)		
		self.id_palina_s = palina.id_palina
		self.nome_palina_s = ricapitalizza(palina.nome)
		self.coordinate_palina_s = (palina.x, palina.y)
		self.id_palina_t = None
		self.nome_palina_t = None
		self.coordinate_palina_t = None
		TrattoBusSalita(self, tempo, attesa_salita)
		self.tratto_attesa = TrattoBusAttesa(self, tempo + timedelta(seconds=attesa_salita), tempo_attesa, tipo_attesa)
		
	def imposta_fermata_t(self, f):
		p = f.rete_palina
		self.id_palina_t = p.id_palina
		self.nome_palina_t = ricapitalizza(p.nome)
		self.coordinate_palina_t = (p.x, p.y)
				
class TrattoBusSalita(Tratto):
	def __init__(self, parent, tempo, tempo_salita):
		Tratto.__init__(self, parent, tempo)		
		self.tempo_percorrenza = tempo_salita
		
		
class TrattoBusDiscesa(Tratto):
	def __init__(self, parent, tempo, rete_fermata, tempo_discesa):
		Tratto.__init__(self, parent, tempo)
		parent.imposta_fermata_t(rete_fermata)
		self.tempo_percorrenza = tempo_discesa

class TrattoBusAttesa(Tratto):
	def __init__(self, parent, tempo, tempo_attesa, tipo_attesa="P"):
		"""
		Inizializzatore
		
		tipo_attesa può assumere i seguenti valori:
			'P': prevista da InfoTP
			'S': dedotta dalle statistiche
			'O': dedotta dall'orario
		"""
		Tratto.__init__(self, parent, tempo)		
		self.tempo_attesa = tempo_attesa
		self.tipo_attesa = tipo_attesa
		
	def ricalcola_tempi(self, rete, grafo, opz):
		fermata = rete.fermate_da_palina[(self.parent.id_palina_s, self.parent.id_percorso)]
		a = grafo.archi[(3, fermata.id_fermata)]
		self.tempo_attesa, self.tipo_attesa = a.get_tempo_vero(self.tempo, opz)
			
		
class TrattoBusArcoPercorso(Tratto):
	"""
	Inizializzatore
	
	tipo_percorrenza può assumere i seguenti valori:
		'P': prevista da InfoTP
		'S': dedotta dalle statistiche
		'D': dedotta in base alla distanza
	"""	
	def __init__(self, parent, tempo, rete_tratto_percorso, tempo_percorrenza, tipo_percorrenza, poly):
		Tratto.__init__(self, parent, tempo)
		if not isinstance(rete_tratto_percorso, list):
			rete_tratto_percorso = [rete_tratto_percorso]
		palina = rete_tratto_percorso[0].s.rete_palina
		self.id_palina_s = palina.id_palina
		self.nome_palina_s = ricapitalizza(palina.nome)
		self.coordinate_palina_s = (palina.x, palina.y)
		palina = rete_tratto_percorso[-1].t.rete_palina
		self.id_palina_t = palina.id_palina
		self.nome_palina_t = ricapitalizza(palina.nome)
		self.coordinate_palina_t = (palina.x, palina.y)
		self.tempo_percorrenza = tempo_percorrenza
		self.tipo_percorrenza = tipo_percorrenza
		self.poly = poly
		self.distanza = 0
		for tp in rete_tratto_percorso:
			self.distanza += tp.rete_tratto_percorsi.distanza()
		
	def ricalcola_tempi(self, rete, grafo, opz):
		fermata_s = rete.fermate_da_palina[(self.id_palina_s, self.parent.id_percorso)]
		fermata_t = rete.fermate_da_palina[(self.id_palina_t, self.parent.id_percorso)]
		a = grafo.archi[(5, fermata_s.id_fermata, fermata_t.id_fermata)]
		self.tempo_percorrenza, self.tipo_percorrenza = a.get_tempo_vero(self.tempo, opz)

class TrattoMetro(TrattoBus):
	def __init__(self, parent, tempo, rete_fermata_s, tempo_attesa, tipo_attesa, attesa_salita, interscambio=False):
		Tratto.__init__(self, parent, tempo)
		fermata = rete_fermata_s
		palina = fermata.rete_palina
		self.interscambio = interscambio
		self.destinazione = ricapitalizza(fermata.rete_percorso.tratti_percorso[-1].t.rete_palina.nome)
		self.id_percorso = fermata.rete_percorso.id_percorso
		self.descrizione_percorso = ricapitalizza(fermata.rete_percorso.descrizione)
		self.id_linea = fermata.rete_percorso.id_linea		
		self.id_palina_s = palina.id_palina
		self.nome_palina_s = ricapitalizza(palina.nome)
		self.coordinate_palina_s = (palina.x, palina.y)
		self.id_palina_t = None
		self.nome_palina_t = None
		self.coordinate_palina_t = None
		if interscambio:
			TrattoMetroInterscambio(self, tempo, attesa_salita)
		else:
			TrattoMetroSalita(self, tempo, attesa_salita)
		self.tratto_attesa = TrattoMetroAttesa(self, tempo + timedelta(seconds=attesa_salita), tempo_attesa, tipo_attesa)

class TrattoMetroAttesa(TrattoBusAttesa):
	pass

class TrattoMetroSalita(TrattoBusSalita):
	pass

class TrattoMetroDiscesa(TrattoBusDiscesa):
	pass

class TrattoMetroInterscambio(TrattoMetroSalita):
	pass

class TrattoMetroArcoPercorso(TrattoBusArcoPercorso):
	pass

# begin teletrasporto

class TrattoTeletrasporto(TrattoMetro):
	pass

class TrattoTeletrasportoSalita(TrattoBusSalita):
	pass

class TrattoTeletrasportoDiscesa(TrattoBusDiscesa):
	pass

class TrattoTeletrasportoArcoPercorso(Tratto):
	"""
	Inizializzatore
	
	tipo_percorrenza può assumere i seguenti valori:
		'P': prevista da InfoTP
		'S': dedotta dalle statistiche
		'D': dedotta in base alla distanza
	"""	
	def __init__(self, parent, tempo, palina_s, palina_t, tempo_percorrenza):
		Tratto.__init__(self, parent, tempo)
		palina = palina_s
		self.id_palina_s = palina.id_palina
		self.nome_palina_s = ricapitalizza(palina.nome)
		self.coordinate_palina_s = (palina.x, palina.y)
		palina = palina_t
		self.id_palina_t = palina.id_palina
		self.nome_palina_t = ricapitalizza(palina.nome)
		self.coordinate_palina_t = (palina.x, palina.y)
		self.tempo_percorrenza = tempo_percorrenza
		self.tipo_percorrenza = ''
		self.poly = [self.coordinate_palina_s, self.coordinate_palina_t]
		self.distanza = 0

# end teletrasporto

class TrattoInterscambio(Tratto):
	def __init__(self, parent, tempo, palina_s, tempo_percorrenza):
		Tratto.__init__(self, parent, tempo)
		self.id_palina_s = palina_s.id_palina
		self.nome_palina_s = ricapitalizza(palina_s.nome)
		self.id_palina_t = ''
		self.nome_palina_t = ''
		self.poly = [(palina_s.x, palina_s.y)]
		self.tempo_percorrenza = tempo_percorrenza

	def set_palina_t(self, palina_t):
		self.id_palina_t = palina_t.id_palina
		self.nome_palina_t = ricapitalizza(palina_t.nome)
		self.poly.append((palina_t.x, palina_t.y))


class TrattoFC(TrattoMetro):
	pass

class TrattoFCAttesa(TrattoMetroAttesa):
	pass

class TrattoFCSalita(TrattoMetroSalita):
	pass

class TrattoFCDiscesa(TrattoMetroDiscesa):
	pass

class TrattoFCInterscambio(TrattoMetroInterscambio):
	pass

class TrattoFCArcoPercorso(TrattoMetroArcoPercorso):
	pass

class TrattoTreno(TrattoMetro):
	pass

class TrattoTrenoAttesa(TrattoMetroAttesa):
	pass

class TrattoTrenoSalita(TrattoMetroSalita):
	pass

class TrattoTrenoDiscesa(TrattoMetroDiscesa):
	pass

class TrattoTrenoInterscambio(TrattoMetroInterscambio):
	pass

class TrattoTrenoArcoPercorso(TrattoMetroArcoPercorso):
	pass


class TrattoPiedi(Tratto):
	pass

class TrattoPiediArco(Tratto):
	def __init__(self, parent, tempo, arco, tempo_percorrenza):
		Tratto.__init__(self, parent, tempo)
		self.nome_arco = arco.get_nome()
		self.distanza = arco.w
		self.tempo_percorrenza = tempo_percorrenza
		self.id = arco.id
		self.id_arco = "%d-%d" % (arco.id[1], arco.id[2])
		self.tipo = arco.id[0]
		self.poly = arco.get_coordinate()

class TrattoPiediArcoDistanzaPaline(Tratto):
	def __init__(self, parent, tempo, distanza, tempo_percorrenza):
		Tratto.__init__(self, parent, tempo)
		self.nome_arco = ""
		self.distanza = distanza
		self.tempo_percorrenza = tempo_percorrenza
			
class TrattoBici(Tratto):
	pass

class TrattoBiciArco(TrattoPiediArco):
	pass

class TrattoBiciArcoDistanzaPaline(TrattoPiediArcoDistanzaPaline):
	pass

class TrattoAuto(Tratto):
	def __init__(self, parent, tempo, carsharing=False):
		Tratto.__init__(self, parent, tempo)
		self.carsharing = carsharing

class TrattoAutoAttesaZTL(Tratto):
	def __init__(self, parent, tempo, tempo_attesa):
		Tratto.__init__(self, parent, tempo)
		self.tempo_attesa = tempo_attesa

class TrattoAutoArco(TrattoPiediArco):
	pass

class TrattoCarPooling(Tratto):
	def __init__(self, parent, tempo, offset):
		Tratto.__init__(self, parent, tempo)
		self.offset = offset

class TrattoCarPoolingArco(TrattoPiediArco):
	pass

class TrattoCarPoolingAttesa(Tratto):
	def __init__(self, parent, tempo, tempo_attesa):
		Tratto.__init__(self, parent, tempo)
		self.tempo_attesa = tempo_attesa
		
class TrattoRisorsa(Tratto):
	def __init__(self, parent, tempo, ct_ris, id_ris, icon, icon_size, nome, descrizione, poly):
		Tratto.__init__(self, parent, tempo)
		self.id_ris = id_ris
		self.ct_ris = ct_ris
		self.icon = icon
		self.icon_size=icon_size
		self.nome_luogo=nome
		self.descrizione=descrizione
		self.poly = poly

# Formattatori
tipi_formattatore = {}

def to_min(sec, hide_zero=False):
	m = round(sec / 60.0)
	if m == 1:
		return _("1 minuto")
	if m == 0:
		if hide_zero:
			return ""
		else:
			return _("meno di 1 minuto")
	if m < 60:
		return _("%(tempo)d minuti") % {'tempo': m}
	h = int(m / 60)
	if h > 1:
		ore_pl = _("ore")
	else:
		ore_pl = _("ora")
	return _("%(ore)d %(ore_pl)s %(minuti)s") % {
		'ore': h,
		'ore_pl': ore_pl,
		'minuti': to_min((m % 60) * 60, True)
	}


def formattatore(tipo, tratti, post=False):
	def decoratore(k):
		for t in tratti:
			tipi_formattatore[(tipo, t.__name__, post)] = k
		return k
	return decoratore

def arrotonda_distanza(n, step=50, short=False):
	k = round(n / float(step)) * step
	if k == 0:
		if short:
			return _("%(dist).0f m") % {'dist': step}
		else:
			return _("meno di %(dist).0f metri") % {'dist': step}
	if k > 1000:
		return _("%(dist).1f km") % {'dist': (k / 1000.0)}
	if short:
		return _("%(dist).0f m") % {'dist': k}
	else:
		return _("%(dist).0f metri") % {'dist': k}

def arrotonda_tempo(t):
	if t.second > 30:
		t += timedelta(minutes=1)
	return datefilter(t, _("H:i"))

def formatta_percorso(tratto, tipo, ft, opzioni, posizione=None):
	"""
	Visita l'albero dei tratti, e formatta gli elementi di interesse

	tratto: radice del tratto da formattare
	tipo: tipo di formattatore da usare
	ft: oggetto di lavoro su cui è costruito l'output, dipendente dal tipo di formattatore
	opzioni: opzioni da passare ai formattatori
	posizione: eventuale tupla che rappresenta la posizione dell'utente, come restituita dal metodo piu_vicino,
		relativizzata rispetto al tratto corrente; None se non è disponibile o se il tratto corrente non è nel
		cammino radice-foglia della posizione dell'utente
	"""
	indice = -1
	if posizione is not None:
		distanza, indici, progressiva, lunghezza, piede_perp = posizione
		if len(indici) > 0:
			indice = indici[0]
		posizione_ric = (distanza, indici[1:], progressiva[1:], lunghezza[1:], piede_perp)
	try:
		nome = tratto.clsname
	except Exception:
		nome = tratto.__class__.__name__
	if (tipo, nome, False) in tipi_formattatore:
		ft = tipi_formattatore[(tipo, nome, False)](tratto, ft, opzioni, posizione)
	i = 0
	for s in tratto.sub:
		if i == indice:
			formatta_percorso(s, tipo, ft, opzioni, posizione_ric)
		else:
			formatta_percorso(s, tipo, ft, opzioni, None)
		i += 1
	if (tipo, nome, True) in tipi_formattatore:
		ft = tipi_formattatore[(tipo, nome, True)](tratto, ft, opzioni, posizione)
	return ft

class PercorsoIndicazioni(object):
	def __init__(self):
		object.__init__(self)
		self.indicazioni = []
	
	def aggiungi(self, tempo, desc, id=None, dettagli=None, punto=None):
		self.indicazioni.append({
			'tempo': arrotonda_tempo(tempo),
			'desc': desc,
			'id': id,
			'dettagli': dettagli,
			'punto': {'x': "%f" % punto[0], 'y': "%f" % punto[1]}
		})
		
class PercorsoIndicazioniIcona(object):
	def __init__(self):
		object.__init__(self)
		self.indicazioni = []
		self.ricevi_nodo = True
		self.numero_nodi = 0
		self.numero_archi = 0
		self.posizione_corrente = -1
		
	def aggiungi_nodo(self, t, nome, id, tipo, punto, url='', icona='nodo.png', overwrite=False, info_exp=''):
		"""
		Tipi:
			F: fermata
			I: indirizzo
			L: luogo
		"""
		if self.ricevi_nodo or overwrite:
			nodo = {'nodo': {
				't': arrotonda_tempo(t),
				'nome': nome,
				'id': id,
				'tipo': tipo,
				'punto': {'x': "%f" % punto[0], 'y': "%f" % punto[1]} if punto is not None else '',
				'url': url,
				'icona': icona,
				'numero': self.numero_nodi,
				'info_exp': info_exp,
			}}
			if self.ricevi_nodo:
				self.indicazioni.append(nodo)
				self.numero_nodi += 1
			else:
				nodo['nodo']['numero'] -= 1
				self.indicazioni[-1] = nodo
		self.ricevi_nodo = False
	
	
	def aggiungi_tratto(
		self,
		mezzo,
		linea,
		id_linea,
		dest,
		url='',
		id='',
		tipo_attesa='',
		tempo_attesa='',
		info_tratto='',
		info_tratto_exp='',
		icona='',
		bb=None,
		info_tratto_short='',
		linea_short=None,
		dist=0,
		info_posizione_corrente=None,
	):
		"""
		Mezzi:
			P: piedi
			B: bus/tram
			M: metro
			T: treno
			
		Tipo attesa:
			O: da orario (tempo_attesa è la stringa dell'orario)
			S: stimata
			P: prevista
		"""
		self.indicazioni.append({'tratto': {
			'mezzo': mezzo,
			'linea': linea,
			'id_linea': id_linea,
			'dest': dest,
			'url': url,
			'id': id,
			'tipo_attesa': tipo_attesa,
			'tempo_attesa': tempo_attesa,
			'info_tratto': info_tratto,
			'info_tratto_exp': info_tratto_exp,
			'icona': icona,
			'numero': self.numero_archi,
			'bounding_box': bb,
			'info_tratto_short': info_tratto_short,
			'linea_short': linea if linea_short is None else linea_short,
			'dist': dist,
			'info_posizione_corrente': info_posizione_corrente,
		}})
		self.numero_archi += 1
		self.ricevi_nodo = True
		if info_posizione_corrente is not None:
			self.posizione_corrente = len(self.indicazioni) - 1
		
	def mark_safe(self):
		for i in self.indicazioni:
			if 'tratto' in i:
				a = i['tratto']
				a['info_tratto_exp'] = mark_safe(a['info_tratto_exp'])


class PercorsoStat(object):
	def __init__(self):
		self.distanza_totale = 0.0
		self.distanza_piedi = 0.0
		self.tempo_totale = 0.0
		
	def finalizza(self):
		self.distanza_totale_format = arrotonda_distanza(self.distanza_totale)
		self.distanza_piedi_format = arrotonda_distanza(self.distanza_piedi)
		self.tempo_totale_format = to_min(self.tempo_totale)
		


# Formattatori indicazioni testuali nuovo tipo
def fermate_intermedie(tratto):
	fermate = []
	old = None
	for s in tratto.sub:
		if isinstance(s, TrattoBusArcoPercorso):
			old = s
			fermate.append((arrotonda_tempo(s.tempo), s.nome_palina_s, s.id_palina_s, s.tipo_percorrenza))
	if old is not None:
		s = old
		fermate.append((arrotonda_tempo((s.tempo + timedelta(seconds=s.tempo_percorrenza))), s.nome_palina_t, s.id_palina_t, s.tipo_percorrenza))
	return fermate

@formattatore('indicazioni_icona', [TrattoRoot])
def format_indicazioni_icona_root(tratto, ft, opz, posizione):
	if 'address' in tratto.partenza:
		ft.aggiungi_nodo(
			tratto.tempo,
			tratto.partenza['address'],
			'',
			'I',
			punto=tratto.get_punto_wgs_84()
		)
	
	elif 'id_palina' in tratto.partenza:
		id_palina = tratto.partenza['id_palina']
		ft.aggiungi_nodo(
			t=tratto.tempo,
			nome="%s (%s)" % (ricapitalizza(tratto.partenza['nome_palina']), id_palina),
			tipo='F',
			id=id_palina,
			punto=tratto.get_punto_wgs_84(),
		)		
	return ft


@formattatore('indicazioni_icona', [TrattoRoot], True)
def format_indicazioni_icona_root_post(tratto, ft, opz, posizione):
	if 'address' in tratto.arrivo:
		ft.aggiungi_nodo(
			tratto.tempo + timedelta(seconds=tratto.get_tempo_totale()),
			tratto.arrivo['address'],
			'',
			'I',
			punto=tratto.get_punto_fine_wgs_84()
		)
	
	elif 'id_palina' in tratto.arrivo:
		id_palina = tratto.arrivo['id_palina']
		ft.aggiungi_nodo(
			t=tratto.tempo,
			nome="%s (%s)" % (ricapitalizza(tratto.arrivo['nome_palina']), id_palina),
			tipo='F',
			id=id_palina,
			punto=tratto.get_punto_fine_wgs_84(),
		)		
	return ft

@formattatore('indicazioni_icona', [TrattoInterscambio])
def format_indicazioni_icona_tratto_interscambio(tratto, ft, opz, posizione):
	versione = getdef(opz, 'versione', 2)
	mezzo = 'I'
	icona = 'interscambio.png'
	if versione == 1:
		mezzo = 'P'
		icona = 'piedi.png'
	ft.aggiungi_nodo(
		t=tratto.tempo,
		nome=tratto.nome_palina_s,
		tipo='F',
		id=tratto.id_palina_s,
		punto=tratto.get_punto_wgs_84(),
		url='',
		overwrite=True,
	)
	ft.aggiungi_tratto(
		mezzo=mezzo,
		linea='',
		id_linea='',
		dest='',
		url='',
		id='',
		tipo_attesa='',
		tempo_attesa='',
		info_tratto='',
		info_tratto_exp='',
		icona=icona,
		bb=tratto.get_bounding_box_wgs84(),
		info_posizione_corrente={} if posizione is not None else None,
	)
	ft.aggiungi_nodo(
		t=tratto.tempo + timedelta(seconds=tratto.tempo_percorrenza),
		nome=tratto.nome_palina_t,
		tipo='F',
		id=tratto.id_palina_t,
		punto=tratto.get_punto_fine_wgs_84(),
		url='',
		overwrite=True,
	)



@formattatore('indicazioni_icona', [TrattoBus, TrattoMetro, TrattoTreno, TrattoFC, TrattoTeletrasporto])
def format_indicazioni_icona_tratto_bus(tratto, ft, opz, posizione):
	numero_fermate = len([x for x in tratto.sub if isinstance(x, TrattoBusArcoPercorso)])
	fermate = _("fermata") if numero_fermate==1 else _("fermate")
	id_veicolo = None
	url = ''
	nome_fermata_s = tratto.nome_palina_s
	nome_fermata_t = tratto.nome_palina_t
	tempo_attesa = to_min(tratto.get_tempo_attesa())
	tempo_s = tratto.tempo
	tempo_t = tratto.tempo + timedelta(seconds=tratto.get_tempo_totale())
	linea_short = None
	info_posizione_corrente = None
	if posizione is not None:
		distanza, indici, progressiva, lunghezza, piede_perp = posizione
		i = indici[0]
		rimanenti = 0
		for x in tratto.sub:
			if i > 0:
				i -= 1
			elif isinstance(x, TrattoBusArcoPercorso):
				rimanenti += 1
		info_posizione_corrente = {
			'fermate_rimanenti': rimanenti,
		}

	if isinstance(tratto, TrattoFC):
		mezzo = 'T'
		icona = 'treno'
		tipo = 'S'
	elif isinstance(tratto, TrattoTreno):
		mezzo = 'T'
		icona = 'treno'
		tipo = 'O'
		tratti_intermedi = [x for x in tratto.sub if isinstance(x, TrattoBusArcoPercorso)]
		tempo_attesa = arrotonda_tempo(tratti_intermedi[0].tempo)
	elif isinstance(tratto, TrattoTeletrasporto):
		mezzo = 'Z'
		icona = 'teletrasporto'
		tipo = 'S'			
	elif isinstance(tratto, TrattoMetro):
		mezzo = 'M'
		icona = 'metro'
		tipo = 'S'
		if tratto.descrizione_percorso is not None and tratto.descrizione_percorso != '':
			linea_short = tratto.descrizione_percorso
	elif isinstance(tratto, TrattoBus):
		mezzo = 'B'
		icona = 'bus'
		tipo = tratto.tratto_attesa.tipo_attesa
		nome_fermata_s += " (%s)" % tratto.id_palina_s
		nome_fermata_t += " (%s)" % tratto.id_palina_t
		if tipo == 'O':
			tipo = 'S'
		url = '/paline/percorso/%s?id_palina=%s' % (tratto.id_percorso, tratto.id_palina_s)
		if tipo[0] == 'P':
			if len(tipo) > 1:
				id_veicolo = tipo[1:]
				url = '/paline/percorso/%s?id_veicolo=%s&amp;id_palina=%s' % (tratto.id_percorso, id_veicolo, tratto.id_palina_s)
			else:
				url = '/paline/percorso/%s?id_palina=%s' % (tratto.id_percorso, tratto.id_palina_s)
			tipo = 'P'		

	id = "T-%s-%s" % (tratto.id_palina_s, tratto.id_percorso)
	dettagli = u''
	if 'espandi_tutto' in opz or ('espandi' in opz and opz['espandi']) == id:
		dettagli = u"<br />".join([u"&nbsp;%s %s" % (x[0], x[1]) for x in fermate_intermedie(tratto)])
			
	ft.aggiungi_nodo(
		t=tempo_s,
		nome=nome_fermata_s,
		tipo='F',
		id=tratto.id_palina_s,
		punto=tratto.get_punto_wgs_84(),
		url=('/paline/palina/%s' % tratto.id_palina_s) if mezzo == 'B' else '',
		overwrite=True,
	)
	ft.aggiungi_tratto(
		mezzo=mezzo,
		linea=tratto.descrizione_percorso,
		id_linea=tratto.id_linea,
		dest=tratto.destinazione,
		url=url,
		id=id,
		tipo_attesa=tipo,
		tempo_attesa=tempo_attesa,
		info_tratto=_("Per %(numero)d %(fermate)s (%(tempo)s)") % {
			'numero': numero_fermate,
			'fermate': fermate,
			'tempo': to_min(tratto.get_tempo_percorrenza()),
		},
		info_tratto_short=_("%(numero)d ferm.") % {'numero': numero_fermate},
		info_tratto_exp=dettagli,
		icona=icona + '.png',
		bb=tratto.get_bounding_box_wgs84(),
		linea_short=linea_short,
		dist=tratto.get_distanza(),
		info_posizione_corrente=info_posizione_corrente,
	)
	ft.aggiungi_nodo(
		t=tempo_t,
		nome=nome_fermata_t,
		tipo='F',
		id=tratto.id_palina_t,
		punto=tratto.get_punto_fine_wgs_84(),
		url=('/paline/palina/%s' % tratto.id_palina_t) if mezzo == 'B' else '',
	)	
	return ft


@formattatore('indicazioni_icona', [TrattoPiedi, TrattoBici, TrattoAuto])
def format_indicazioni_icona_tratto_piedi(tratto, ft, opz, posizione):
	sub = [s for s in tratto.sub if isinstance(s, TrattoPiediArco)]
	if len(sub) > 0:
		distanza_tratto = tratto.get_distanza()
		distanza = arrotonda_distanza(distanza_tratto).capitalize()
		distanza_short = arrotonda_distanza(distanza_tratto, short=True).capitalize()
		id = "O-%s" % sub[0].id_arco
		dettagli = u''
		ta = tratto.get_tempo_attesa()
		attesa_ztl = None if ta == 0 else tratto.tempo + timedelta(seconds=ta)
		prima_strada = None
		nome_corr = None
		for s in sub:
			if s.nome_arco != "" and s.nome_arco != nome_corr:
				dettagli += u"&nbsp;%s<br />" % s.nome_arco
				nome_corr = s.nome_arco
				if prima_strada is None:
					prima_strada = nome_corr
		dettagli += u"<br />".join([u"&nbsp;%s %s" % (x[0], x[1]) for x in fermate_intermedie(tratto)])
		if not('espandi_tutto' in opz or ('espandi' in opz and opz['espandi']) == id):
			dettagli = ''
		bici = isinstance(tratto, TrattoBici)
		auto = isinstance(tratto, TrattoAuto)
		if bici:
			mezzo = 'C'
			icona = 'bici.png'
		elif auto:
			if tratto.carsharing:
				mezzo = 'CS'
				icona = 'carsharing.png'
			else:
				mezzo = 'A'
				icona = 'auto.png'
		else:
			mezzo = 'P'
			icona = 'piedi.png'
		ft.aggiungi_nodo(tratto.tempo, prima_strada, '', 'I', tratto.get_punto_wgs_84())
		ft.aggiungi_tratto(
			mezzo=mezzo,
			linea='',
			id_linea='',
			dest='',
			url='',
			id=id,
			tipo_attesa='Z' if attesa_ztl is not None else '',
			tempo_attesa=arrotonda_tempo(attesa_ztl) if attesa_ztl is not None else '',
			info_tratto=_("%(distanza)s (%(tempo)s)" % {
				'distanza': distanza,
				'tempo': to_min(tratto.get_tempo_percorrenza()),
			}),
			info_tratto_short=distanza_short,
			info_tratto_exp=dettagli,
			icona=icona,
			bb=tratto.get_bounding_box_wgs84(),
			dist=distanza_tratto,
			info_posizione_corrente={} if posizione is not None else None,
		)
	return ft

@formattatore('indicazioni_icona', [TrattoCarPooling])
def format_indicazioni_icona_tratto_car_pooling(tratto, ft, opz, posizione):
	sub = [s for s in tratto.sub if isinstance(s, TrattoCarPoolingArco)]
	nome_primo_arco = None
	if len(sub) > 0:
		distanza_tratto = tratto.get_distanza()
		distanza = arrotonda_distanza(distanza_tratto).capitalize()
		id = "O-%s" % sub[0].id_arco
		dettagli = u''
		nome_corr = None
		for s in sub:
			if s.nome_arco != "" and s.nome_arco != nome_corr:
				dettagli += u"&nbsp;%s<br />" % s.nome_arco
				nome_corr = s.nome_arco
				if nome_primo_arco is None:
					nome_primo_arco = nome_corr
		dettagli += u"<br />".join([u"&nbsp;%s %s" % (x[0], x[1]) for x in fermate_intermedie(tratto)])
		ta = tratto.get_tempo_attesa()
		tp = tratto.get_tempo_percorrenza()
		tempo_attesa = to_min(ta)
		nome_ultimo_arco = nome_corr		
		ft.aggiungi_nodo(
			tratto.tempo,
			nome_primo_arco,
			'',
			'I',
			punto=tratto.get_punto_wgs_84()
		)
		ft.aggiungi_tratto(
			mezzo='CP',
			linea='',
			id_linea='',
			dest='',
			url='',
			id=id,
			tipo_attesa='E',
			tempo_attesa=tempo_attesa,
			info_tratto=_("%(distanza)s (%(tempo)s)" % {
				'distanza': distanza,
				'tempo': to_min(tp),
			}),
			info_tratto_exp=dettagli if 'espandi_tutto' in opz or ('espandi' in opz and opz['espandi']) == id else '',
			info_tratto_short=to_min(tp),
			icona='carpooling.png',
			bb=tratto.get_bounding_box_wgs84(),
			dist=distanza_tratto,
			info_posizione_corrente={} if posizione is not None else None,
		)
		ft.aggiungi_nodo(
			tratto.tempo + timedelta(seconds=ta + tp),
			nome_ultimo_arco,
			'',
			'I',
			punto=tratto.get_punto_fine_wgs_84()
		)			
	return ft


@formattatore('indicazioni_icona', [TrattoRisorsa])
def format_indicazioni_icona_tratto_risorsa(tratto, ft, opz, posizione):
	ft.aggiungi_nodo(
		tratto.tempo,
		tratto.nome_luogo,
		"RIS-%s-%s" % (tratto.ct_ris, tratto.id_ris),
		'L',
		punto=tratto.get_punto_wgs_84(),
		icona=tratto.icon,
		info_exp=tratto.descrizione,
	)
	return ft

	
# Formattatori indicazioni su mappa
@formattatore('mappa', [TrattoBus])
def format_mappa_tratto_bus(tratto, ft, opz, posizione):
	numero_fermate = len([x for x in tratto.sub if isinstance(x, TrattoBusArcoPercorso)])
	fermate = _("fermata") if numero_fermate==1 else _("fermate")
	out = '[%s] ' % arrotonda_tempo(tratto.tempo)
	out += _("Alla fermata %(palina)s (%(id)s), prendi il %(linea)s per %(numero)d %(fermate)s") % {
		'palina': tratto.nome_palina_s,
		'id': tratto.id_palina_s,
		'linea': tratto.id_linea,
		'numero': numero_fermate, 
		'fermate': fermate,
	}	
	ft.add_polyline(tratto.get_poly_wgs84(), 0.7, '#7F0000', 5)
	ft.add_marker(gbfe_to_wgs84(*tratto.coordinate_palina_s), '/paline/s/img/partenza.png', icon_size=(16, 16), infobox=out, anchor=(8, 8))
	tratti_intermedi = [x for x in tratto.sub if isinstance(x, TrattoBusArcoPercorso)]
	for s in tratti_intermedi[:-1]:
		infobox = '[%s] %s' % (arrotonda_tempo(s.tempo), s.nome_palina_t)
		ft.add_marker(gbfe_to_wgs84(*s.coordinate_palina_t), '/paline/s/img/fermata.png', icon_size=(16, 16), infobox=infobox, anchor=(8, 8))
	out = '[%s] ' % arrotonda_tempo(tratto.tempo + timedelta(seconds=tratto.get_tempo_totale()))
	out += _("Scendi alla fermata %(palina)s (%(id)s)") % {
		'palina': tratto.nome_palina_t,
		'id': tratto.id_palina_t,
	}
	ft.add_marker(gbfe_to_wgs84(*tratto.coordinate_palina_t), '/paline/s/img/arrivo.png', icon_size=(16, 16), infobox=out, anchor=(8, 8))
	return ft


@formattatore('mappa', [TrattoMetro, TrattoFC, TrattoTreno])
def format_mappa_tratto_metro(tratto, ft, opz, posizione):
	numero_fermate = len([x for x in tratto.sub if isinstance(x, TrattoBusArcoPercorso)])
	fermate = _("fermata") if numero_fermate==1 else _("fermate")
	out = '[%s] ' % arrotonda_tempo(tratto.tempo)
	if tratto.interscambio:
		out += _("Scendi a %(palina)s e cambia con la %(desc)s per %(numero)d %(fermate)s") % {
			'palina': tratto.nome_palina_s,
			'desc': tratto.descrizione_percorso,
			'numero': numero_fermate,
			'fermate': fermate,
		}
	else:
		out += _("A %(palina)s, prendi la %(desc)s per %(numero)d %(fermate)s") %  {
			'palina': tratto.nome_palina_s,
			'desc': tratto.descrizione_percorso,
			'numero': numero_fermate,
			'fermate': fermate,
		}	
	color = '#000000'
	icona = 'treno'
	if tratto.id_linea == 'MEA':
		icona = 'metro'
		color = '#FF0000'
	if tratto.id_linea[:3] == 'MEB':
		icona = 'metro'
		color = '#0000FF'
	if tratto.id_linea == 'MEC':
		icona = 'metro'
		color = '#57B947'
	ft.add_polyline(tratto.get_poly_wgs84(), 0.7, color, 5)
	ft.add_marker(gbfe_to_wgs84(*tratto.coordinate_palina_s), '/paline/s/img/%s.png' % icona, icon_size=(16, 16), infobox=out)
	tratti_intermedi = [x for x in tratto.sub if isinstance(x, TrattoBusArcoPercorso)]
	for s in tratti_intermedi[:-1]:
		infobox = '[%s] %s' % (arrotonda_tempo(s.tempo), s.nome_palina_t)
		ft.add_marker(gbfe_to_wgs84(*s.coordinate_palina_t), '/paline/s/img/%s_fermata.png' % icona, icon_size=(16, 16), infobox=infobox, anchor=(8, 8))	
	out = '[%s] ' % arrotonda_tempo(tratto.tempo + timedelta(seconds=tratto.get_tempo_totale()))
	out += _("Scendi a %(palina)s") % {'palina': tratto.nome_palina_t}
	ft.add_marker(gbfe_to_wgs84(*tratto.coordinate_palina_t), '/paline/s/img/%s.png' % icona, icon_size=(16, 16), infobox=out, anchor=(8, 8))
	return ft


@formattatore('mappa', [TrattoTeletrasporto])
def format_mappa_teletrasporto(tratto, ft, opz, posizione):
	ft.add_marker(tratto.get_punto_wgs_84(), '/paline/s/img/teletrasporto.png', icon_size=(16, 16), infobox='Smaterializzazione Teletrasporto', anchor=(8, 8))
	color = '#B200FF'
	ft.add_polyline([tratto.get_punto_wgs_84(), tratto.get_punto_fine_wgs_84()], 1, color, 0.5)
	ft.add_marker(tratto.get_punto_fine_wgs_84(), '/paline/s/img/teletrasporto.png', icon_size=(16, 16), infobox='Rimaterializzazione Teletrasporto', anchor=(8, 8))
	return ft

@formattatore('mappa', [TrattoPiedi, TrattoInterscambio])
def format_mappa_piedi(tratto, ft, opz, posizione):
	color = '#000000'
	ft.add_polyline(tratto.get_poly_wgs84(), 1, color, 2.5)
	return ft

@formattatore('mappa', [TrattoBici])
def format_mappa_bici(tratto, ft, opz, posizione):
	ft.add_polyline(tratto.get_poly_wgs84(), 1, '#267F00', 3.5)
	return ft

@formattatore('mappa', [TrattoAuto, TrattoCarPooling])
def format_mappa_auto(tratto, ft, opz, posizione):
	ft.add_polyline(tratto.get_poly_wgs84(), 1, '#F600FF', 3.5)
	return ft


@formattatore('mappa', [TrattoRisorsa])
def format_mappa_luogo(tratto, ft, opz, posizione):
	ft.add_marker(
		tratto.get_punto_wgs_84(),
		icon=tratto.icon,
		icon_size=tratto.icon_size,
		infobox=tratto.nome_luogo,
		desc=tratto.descrizione,
	)
	return ft


@formattatore('mappa', [TrattoRoot])
def format_mappa_root(tratto, ft, opz, posizione):
	out = '[%s] ' % arrotonda_tempo(tratto.tempo)
	if tratto.partenza is None or 'address' not in tratto.partenza:
		out += _("Parti")
	else:
		out += _("Parti da %(luogo)s") % {'luogo': tratto.partenza['address']}	
	p = tratto.get_poly_wgs84()
	if len(p) > 0:
		ft.add_marker(p[0], '/paline/s/img/partenza_percorso.png', icon_size=(32, 32), anchor=(16, 32), infobox=out, drop_callback='drop_start')
	return ft

@formattatore('mappa', [TrattoRoot], True)
def format_mappa_root_post(tratto, ft, opz, posizione):
	out = '[%s] ' % arrotonda_tempo(tratto.tempo + timedelta(seconds=tratto.get_tempo_totale()))
	if tratto.arrivo is None or 'address' not in tratto.arrivo:
		out += _("Sei arrivato")
	else:
		out += _("Sei arrivato a %s") % tratto.arrivo['address']
	p = tratto.get_poly_wgs84()
	if len(p) > 0:
		ft.add_marker(p[-1], '/paline/s/img/arrivo_percorso.png', icon_size=(32, 32), anchor=(16, 32), infobox=out, drop_callback='drop_stop')
	return ft

# Formattatori per statistiche percorso
@formattatore('stat', [TrattoRoot])
def format_stat_root(tratto, ft, opz, posizione):
	ft.distanza_totale = tratto.get_distanza()
	ft.tempo_totale = tratto.get_tempo_totale()
	return ft
	
@formattatore('stat', [TrattoPiedi])
def format_stat_piedi(tratto, ft, opz, posizione):
	ft.distanza_piedi += tratto.get_distanza()
	return ft
	
@formattatore('stat', [TrattoRoot], True)
def format_stat_mappa_root_post(tratto, ft, opz, posizione):
	ft.finalizza()
	return ft

# Formattatore percorso auto salvato
@formattatore('auto_salvato', [TrattoAutoArco])
def format_auto_salvato_tratto_auto_arco(tratto, ft, opz, posizione):
	eid = tratto.id
	e = ft.grafo.archi[eid]
	ft.add_arco(
		t=tratto.tempo, 
		eid=eid,
		sid=e.s.id,
		tid=e.t.id,
		tp=tratto.tempo_percorrenza,
	)
	return ft