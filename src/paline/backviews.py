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

from models import *
from django.db import models, connections, transaction
from django.core.cache import cache
from servizi.utils import dict_cursor, project, datetime2mysql, group_required, autodump
from servizi.utils import model2contenttype, generate_key
from servizi import infopoint
from servizi.models import Luogo
from parcheggi import models as parcheggi
from mercury.models import Mercury
from risorse import models as risorse
from datetime import datetime, timedelta, time, date
from django.template.defaultfilters import date as datefilter, urlencode
from jsonrpc import jsonrpc_method
import rpyc
import cPickle as pickle
import gmaps
import views
from paline.views import paline7, _dettaglio_paline, _dettaglio_paline_app
from pprint import pprint
from percorso.views import infopoint_to_cp
from django.utils import translation
from servizi.views import get_fav
from copy import copy
import logging
import settings


@jsonrpc_method('palinePercorsoMappa', safe=True)
def percorso_mappa(request, id_percorso, *args, **kwargs):
	c = Mercury.rpyc_connect_any_static(settings.MERCURY_WEB)
	out = pickle.loads(c.root.percorso_su_mappa_special(id_percorso, '/paline/s/img/'))
	return out


@jsonrpc_method('paline_percorso_fermate', safe=True)
def percorso_fermate(request, id_percorso, id_veicolo, lang):
	translation.activate(lang)
	return views.percorso_per_json(request, id_percorso, id_veicolo)


@jsonrpc_method('paline_orari', safe=True)
def percorso_orari(request, id_percorso, data, lang):
	translation.activate(lang)
	orari = views.trovalinea_orari(None, '', id_percorso, data)
	return orari


@jsonrpc_method('stato_traffico', safe=True)
def stato_traffico(request, verso):
	if verso == 'out':
		percorsi = [
			'53771',
			'2598',
			'502A',
			'11436',
			'11592',
			'766A',
			'12115',
			'7288',
			'53422',
			'53670',
			'11574',
			'53715',
			'53762',
			'10273',
			'50329',
			'53554',
			'51668',
			'13085',
			'53466',
			'50046',
			'52265',
			'701A',
			'52968',
			'51828',
			'55446',
			'51907',
			'54243',
			'55767',
			'55771',
			'55449',
		]
	else:
		percorsi = [
			'50595',
			'53770',
			'2597',
			'502R',
			'52632',
			'11591',
			'5404',
			'12118',
			'7287',
			'53423',
			'53671',
			'11573',
			'53864',
			'10274',
			'50594',
			'53553',
			'50963',
			'13084',
			'53464',
			'50047',
			'808A',
			'701R',
			'52969',
			'51829',
			'55444',
			'50983',
			'54244',
			'55769',
			'55770',
			'55450',
		]

	c = Mercury.rpyc_connect_any_static(settings.MERCURY_WEB_CL)

	mappa = {
		'markers': [],
		'polylines': [],
		'sublayers': [],
	}
	
	for id_percorso in percorsi:
		try:
			m = pickle.loads(c.root.percorso_su_mappa(id_percorso, None, '/paline/s/img/', con_stato=True, con_fermate=False, con_bus=False, fattore_thickness=1.6))
			mappa['markers'].extend(m['markers'])
			mappa['polylines'].extend(m['polylines'])
			mappa['sublayers'].append(('traffico_bus', id_percorso))			
		except Exception, e:
			logging.error("Mappa centrale: Errore percorso %s" % id_percorso)
			
	out = {
		'mappa': mappa,
	}
	
	return out	


@jsonrpc_method('mappa_layer', safe=True)
def mappa_layer(request, nome, lang):
	#pprint(nome)
	translation.activate(lang)
	tipo = nome[0]
	id = nome[1]
	merc = get_web_cl_mercury()
	
	if tipo == 'traffico_bus':
		out = merc.sync_any('percorso_su_mappa_ap', {
			'id_percorso': id,
			'mappa': None, # TODO: Provvisorio, si può tranquillamente eliminare
			'path_img': '/paline/s/img/',
			'con_stato': True,
			'con_fermate': False,
			'con_percorso': False,
			'con_bus': False
		})
		out['refresh'] = 2 * 60
		
	if tipo == 'traffico_bus_tiny':
		out = merc.sync_any('percorso_su_mappa_ap', {
			'id_percorso': id,
			'mappa': None,  # TODO: Provvisorio, si può tranquillamente eliminare
			'path_img': '/paline/s/img/',
			'con_stato': True,
			'con_fermate': False,
			'con_percorso': False,
			'con_bus': False,
			'fattore_thickness': 0.5
		})
		out['refresh'] = 2 * 60		
		
	elif tipo == 'palina':
		return views.trovalinea_veicoli_locale(request, *id)
	
	elif tipo == 'palina-singola':
		# workaround WA01 for webapp client bug begin
		if id.endswith('_departure'):
			id = id[:-10]
		# workaround WA01 for webapp client bug end

		palina = Palina.objects.by_date().get(id_palina=id)
		out = merc.sync_any('palina_su_mappa_ap', {'id_palina': id, 'path_img': '/paline/s/img/'})
		out['descrizione'] = u"%s (%s)" % (palina.nome_ricapitalizzato(), palina.id_palina)
	
	elif tipo == 'posizione_bus':
		out = merc.sync_any('percorso_su_mappa_ap', {
			'id_percorso': id,
			'mappa': None,  # TODO: Provvisorio, si può tranquillamente eliminare
			'path_img': '/paline/s/img/',
			'con_stato': False,
			'con_fermate': False,
			'con_percorso': False,
			'con_bus': False,
			'con_bus_immediato': True
		})
		out['refresh'] = 30
		
	elif tipo == 'arrivi_veicolo':
		p = Percorso.objects.by_date().get(id_percorso=id[1])
		vs = p.get_veicoli(True, id[0])
		out = ''
		if len(vs) > 0:
			out = vs[0]['infobox']
	
	elif tipo == 'percorso':
		p = Percorso.objects.by_date().get(id_percorso=id)
		out = merc.sync_any('percorso_su_mappa_ap', {
			'id_percorso': id,
			'mappa': None,  # TODO: Provvisorio, si può tranquillamente eliminare
			'path_img': '/paline/s/img/',
			'con_stato': False,
			'con_bus': False,
			'con_fermate': True
		})
		out['sublayers'] = [
			('traffico_bus', id),
			('posizione_bus', id),
		]
		out['descrizione'] = p.getNomeCompleto()
		
	elif tipo == 'percorso_tiny':
		p = Percorso.objects.by_date().get(id_percorso=id)
		out = merc.sync_any('percorso_su_mappa_ap', {
			'id_percorso': id,
			'mappa': None,  # TODO: Provvisorio, si può tranquillamente eliminare
			'path_img': '/paline/s/img/',
			'con_stato': False,
			'con_bus': False,
			'con_fermate': False,
			'fattore_thickness': 0.3
		})
		out['sublayers'] = [
			('traffico_bus_tiny', id),
			('posizione_bus', id),
		]
		out['descrizione'] = p.getNomeCompleto()
		
	elif tipo == 'risorsa':
		# print "Cerco una risorsa"
		pprint(id)
		address = id[0]
		tipi_ris = id[1]
		start = infopoint_to_cp(request, address)
		if start['stato'] != 'OK':
			out = {'errore': start}
		else:
			max_distanza = id[2]
			out = get_web_cpd_mercury().sync_any('risorse_vicine_ap', {
				'start': start,
				'tipi_ris': tipi_ris,
				'num_ris': 5,
				'max_distanza': max_distanza,
			})
			out['descrizione'] = 'Luoghi trovati'

	elif tipo == 'pannelli':
		out = pannellibw.mappa_layer(request, nome)

	# pprint(out)
	return out


@jsonrpc_method('paline_smart_search', safe=True)
def paline_smart_search(request, query, lang):
	translation.activate(lang)
	#print "Smart"
	ctx = {
		'errore': False,
		'tipo': '',
		'id_palina': '',
		'indirizzi': [],
		'paline_semplice': [],
		'paline_extra': [],
		'percorsi': [],
		'query': query,
	}
	out = views._default(request, query, ctx, True, dett_paline=True)
	# pprint(out)
	return out


@paline7.metodo("Mappa")
def ws_mappa(request, token, tipo, id):
	return mappa_layer(request, (tipo, id), 'it')


@jsonrpc_method('paline_previsioni', safe=True)
def previsioni(request, id_palina, lingua):
	# workaround WA01 for webapp client bug begin
	if id_palina.endswith('_departure'):
		id_palina = id_palina[:-10]
	# workaround WA01 for webapp client bug end

	translation.activate(lingua)
	try:
		p = Palina.objects.by_date().get(id_palina=id_palina)
	except:
		raise errors.XMLRPC['XRE_NO_ID_PALINA']
	return _dettaglio_paline_app(request, p)


@jsonrpc_method('paline_preferiti', safe=True)
def preferiti(request, tipo, nome, descrizione, esiste):
	out = {}
	if esiste:
		g = GruppoPalinePreferite(user=request.user, nome=descrizione, singleton=True)
		g.save()
		p = PalinaPreferita(id_palina=nome, nome=descrizione, gruppo=g)
		p.save()
	else:
		p = PalinaPreferita.objects.filter(gruppo__user=request.user, id_palina=nome)[0]
		g = p.gruppo
		if g.palinapreferita_set.count() == 1:
			g.delete()
		else:
			p.delete()

	# Get new favorites
	fav = get_fav(request)
	fav_list = [(k, fav[k][0], fav[k][1]) for k in fav]
	fav_list.sort(key=lambda x: x[2])
	out['fav'] = fav_list

	return out


def _inizializza_notifica_arrivo_bus(request, id_richiesta, id_palina, linee, tempo):
	p = Palina.objects.by_date().get(id_palina=id_palina)
	arrivi = _dettaglio_paline(request, p.nome, [p], as_service=True)['arrivi']
	linea_min = ''
	veicolo_min = ''
	arr = []
	arr_dict = {}

	for a in arrivi:
		linea = a['linea']
		t = a['tempo_attesa_secondi']
		if t >= tempo and linea in linee:
			id_veicolo = a['id_veicolo']
			a2 = (t, linea, id_veicolo)
			arr.append(a2)
			arr_dict[id_veicolo] = a2

	if len(arr) == 0:
		scheduling = -1
	else:
		arr.sort(key=lambda a: a[0])
		a = arr[0]
		scheduling = a[0] - tempo
		linea_min = a[1]
		veicolo_min = a[2]

	ret = {
		'id_richiesta': id_richiesta,
		'refresh': 60,
		'scheduling': scheduling,
		'id_linea': linea_min,
		'id_veicolo': veicolo_min,
	}

	store = copy(ret)
	store['tempo'] = tempo
	store['id_palina'] = id_palina
	store['linee'] = linee
	store['arr_dict'] = arr_dict

	cache.set('paline_notifarrivo_%s' % id_richiesta, store, 300)
	return ret


@jsonrpc_method('paline_imposta_notifica_arrivo_bus')
def imposta_notifica_arrivo_bus(request, param):
	"""
	Imposta una notifica di arrivo del bus per l'app.

	Param è un dizionario con i seguenti elementi:
	- id_palina: id della palina per cui si richiede la notifica
	- linee: lista delle linee di interesse
	- tempo: distanza temporale (in secondi) dell'autobus nel momento di ricezione della notifica

	Restituisce un dizionario con i seguenti elementi:
	- refresh: distanza in secondi alla quale effettuare la prossima richiesta di aggiornamento
	- id_richiesta: id della richiesta
	- scheduling: distanza di scheduling, in secondi (oppure -1)
	- id_linea: linea in arrivo (oppure stringa vuota)
	- id_veicolo: veicolo in 	arrivo (oppure stringa vuota)
	"""
	id_richiesta = generate_key(40)
	return _inizializza_notifica_arrivo_bus(request, id_richiesta, param['id_palina'], param['linee'], param['tempo'])


@jsonrpc_method('paline_refresh_notifica_arrivo_bus')
def refresh_notifica_arrivo_bus(request, id_richiesta):
	"""
	Restituisce un aggiornamento sugli arrivi relativi alla notifica richiesta

	Il dizionario restituito è analogo a quello del metodo (paline_)imposta_notifica_arrivo_bus
	"""
	old = cache.get('paline_notifarrivo_%s' % id_richiesta)

	if old is None:
		return {'status': 'ERROR'}

	id_palina = old['id_palina']
	linee = old['linee']
	tempo = old['tempo']
	arr_old = old['arr_dict']

	# Nessun autobus precedentemente in arrivo
	if old['scheduling'] < 0:
		return _inizializza_notifica_arrivo_bus(request, id_richiesta, id_palina, linee, tempo)

	p = Palina.objects.by_date().get(id_palina=id_palina)
	arrivi = _dettaglio_paline(request, p.nome, [p], as_service=True)['arrivi']
	arr = []
	arr_dict = {}

	for a in arrivi:
		linea = a['linea']
		t = a['tempo_attesa_secondi']
		if linea in linee:
			id_veicolo = a['id_veicolo']
			a2 = (t, linea, id_veicolo)
			arr.append(a2)
			if t >= tempo:
				arr_dict[id_veicolo] = a2

	arr.sort(key = lambda a: a[0])
	for a in arr:
		t, linea, id_veicolo = a
		if t < tempo and id_veicolo in arr_old and arr_old[id_veicolo][0] > t:
			# Il veicolo si è avvicinato dall'ultima ricerca: notifica immediata e annullamento richiesta
			ret = {
				'id_richiesta': '',
				'refresh': 0,
				'scheduling': 0,
				'id_linea': linea,
				'id_veicolo': id_veicolo,
			}

			cache.delete('paline_notifarrivo_%s' % id_richiesta)
			return ret

		elif t >= tempo:
			# Primo veicolo in arrivo dopo il tempo. Imposto notifica futura
			ret = {
				'id_richiesta': id_richiesta,
				'refresh': 60,
				'scheduling': t - tempo,
				'id_linea': linea,
				'id_veicolo': id_veicolo,
			}

			store = copy(ret)
			store['tempo'] = tempo
			store['id_palina'] = id_palina
			store['linee'] = linee
			store['arr_dict'] = arr_dict
			cache.set('paline_notifarrivo_%s' % id_richiesta, store, 300)
			return ret

	# Nessun veicolo in arrivo, nessuna notifica
	ret = {
		'id_richiesta': id_richiesta,
		'refresh': 60,
		'scheduling': -1,
		'id_linea': '',
		'id_veicolo': '',
	}

	store = copy(ret)
	store['tempo'] = tempo
	store['id_palina'] = id_palina
	store['linee'] = linee
	store['arr_dict'] = arr_dict
	cache.set('paline_notifarrivo_%s' % id_richiesta, store, 300)
	return ret
