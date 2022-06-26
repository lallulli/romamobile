# coding: utf-8

#
#    Copyright 2013-2016 Roma servizi per la mobilit� srl
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

from ztl.models import *
from servizi.models import GiornoSettimana
from log_servizi.models import ServerVersione, Versione, convert_times_to_string
import errors
import re
from datetime import date, datetime, timedelta, time
from django.template.response import TemplateResponse
from django.http import HttpResponse
from django.template.defaultfilters import time as timefilter
from django.template.defaultfilters import date as datefilter
from django.utils.translation import ugettext as _
from servizi.utils import dow2string, dateandtime2datetime, date2mysql
from collections import defaultdict
from pprint import pprint

def valid_date(data):
	# presa una stringa, verifica che sia una data nel formato yyyy-mm-dd
	r = re.compile('^(19|20)\d\d[- /.](0[1-9]|1[012])[- /.](0[1-9]|[12][0-9]|3[01])$')
	if r.match(data):
		return True
	else:
		return False

def timestamp2date(timestamp):
	datasplit = re.split('-', timestamp)
	return date(int(datasplit[0]), int(datasplit[1]), int(datasplit[2]))

def str2time(ora):
	# prende l'ora in formato hh:mm e restituisce un oggetto time
	timesplit = re.split(':', ora)
	return time(int(timesplit[0]), int(timesplit[1]))

def check_ztl_attiva(codice):
	data = date.today()
	ora = datetime.now().time()
	dow = int(data.strftime('%w'))+1
	ztl = ZTL.objects.get(codice=codice)
	gs = GiornoSettimana.objects.get(codice=dow)
	# verifico se ci sono modifiche straordinarie attive da ieri o in calendario
	modifica_str_attiva = ModificaStraordinaria.objects.filter(ztl=ztl, giorno=data - timedelta(1), attiva=True, fine_domani=True, ora_fine__gte=ora).exists() or ModificaStraordinaria.objects.filter(ztl=ztl, giorno=data, attiva=True, ora_inizio__lte=ora, ora_fine__gte=ora).exists()
	modifica_str_disattiva = ModificaStraordinaria.objects.filter(ztl=ztl, giorno=data - timedelta(1), attiva=False, fine_domani=True, ora_fine__gte=ora).exists() or ModificaStraordinaria.objects.filter(ztl=ztl, giorno=data, attiva=False, ora_inizio__lte=ora, ora_fine__gte=ora).exists()
	cal = Calendario.objects.filter(ztl=ztl, giorno=gs, ora_inizio__lte=ora, ora_fine__gte=ora).exists()
	return (modifica_str_attiva or cal) and not modifica_str_disattiva


ztl4 = ServerVersione("ztl", 4)

@ztl4.metodo("Lista")
def Lista(request, token):
	lista = ZTL.objects.all()
	ret = []
	for l in lista:
		ret.append({
				'id_ztl': l.codice,
				'toponimo': l.descrizione,
				})
	
	return ret

def Orari(request, token, modifiche, data):
	ret = []

	if type(data) == date:
		data_richiesta = data
	else:
		data_richiesta = timestamp2date(data)
	data_prec = data_richiesta - timedelta(1)
	
	ztls = ZTL.objects.all()
	
	for ztl in ztls:
	
		fasce = []
		modificato = 0
		
		# verifico che non ci siano modifiche straordinarie, se richiesto
		if modifiche:
			# modifiche iniziate ieri e finite oggi
			mods = ModificaStraordinaria.objects.select_related().filter(ztl=ztl, giorno=data_prec, fine_domani=True)

			for m in mods:
				# ci sono modifiche
				modificato = 1
				
				fasce.append({
					'ora_inizio': m.ora_inizio,
					'ora_fine': m.ora_fine,
					'inizio_ieri': True,
					'fine_domani': False,
					'attiva': m.attiva,
				})
			
			# modifiche iniziate oggi
			mods = ModificaStraordinaria.objects.select_related().filter(ztl=ztl, giorno=data_richiesta)
			for m in mods:
				# ci sono modifiche
				modificato = 1

				fasce.append({
					'ora_inizio': m.ora_inizio,
					'ora_fine': m.ora_fine,
					'inizio_ieri': False,
					'fine_domani': m.fine_domani,
					'attiva': m.attiva,
				})
			
		
		# se le modifiche non sono state trovate o non sono richieste, procedo col calendario
		
		if not modificato:
		
			# verifico ztl iniziate ieri e finite oggi
			dow = int(data_prec.strftime('%w'))+1
			cal = Calendario.objects.select_related().filter(ztl=ztl, giorno=GiornoSettimana.objects.get(codice=dow), fine_domani=True)
			for c in cal:
				fasce.append({
					'ora_inizio': c.ora_inizio,
					'ora_fine': c.ora_fine,
					'inizio_ieri': True,
					'fine_domani': False,
					'attiva': True
					})
			
			# verifico ztl per oggi
			dow = int(data_richiesta.strftime('%w'))+1
			cal = Calendario.objects.select_related().filter(ztl=ztl, giorno=GiornoSettimana.objects.get(codice=dow))
			for c in cal:
				# la ztl finisce il giorno dopo, inizio_ieri=0, fine_domani=1
				fasce.append({
					'ora_inizio': c.ora_inizio,
					'ora_fine': c.ora_fine,
					'inizio_ieri': False,
					'fine_domani': c.fine_domani,
					'attiva': True
					})
		ret.append({
			'id_ztl': ztl.codice,
			'toponimo': ztl.descrizione,
			'modificato': modificato,
			'fasce': fasce,
			})
	return ret

OrariWS = ztl4.metodo("Orari")(convert_times_to_string(Orari))

def orari_per_ztl(giorno_inizio, giorno_fine, modifiche=True):
	"""
	Restituisce gli orari di tutte le ZTL, da giorno_inizio a giorno_fine compresi
	"""
	giorno = giorno_inizio
	zs = {}

	while giorno <= giorno_fine:
		ieri = giorno - timedelta(days=1)
		domani = giorno + timedelta(days=1)
		res = Orari(None, '', modifiche, giorno)
		for r in res:
			id = r['id_ztl']
			fasce = set()
			if not id in zs:
				fs = r['fasce']
				zs[id] = r
				zs[id]['fasce'] = set()
			else:
				fs = r['fasce']
			for f in fs:
				g_i = giorno
				g_f = giorno
				if f['inizio_ieri']:
					g_i = ieri
				if f['fine_domani']:
					g_f = domani
				fasce.add((dateandtime2datetime(g_i, f['ora_inizio']), dateandtime2datetime(g_f, f['ora_fine'])))
			zs[id]['fasce'].update(fasce)
		giorno = domani
	return zs



def ModifichePerData(request, token, data, intervallo):			

	ret = []
	
	data_inizio = timestamp2date(data)
	
	for i in range(0, intervallo+1):
	
		data_corrente = data_inizio + timedelta(i)
		ztls = ZTL.objects.all()
		for ztl in ztls:
		
			fasce = []
			trovato = False
			
			# verifico la presenza di modifiche per il giorno precedente
			mods = ModificaStraordinaria.objects.select_related().filter(ztl=ztl, giorno=data_corrente - timedelta(1), fine_domani=True)
			for m in mods:
				trovato = True
				fasce.append({
					'ora_inizio': m.ora_inizio,
					'ora_fine': m.ora_fine,
					'inizio_ieri': True,
					'fine_domani': False,
				})
			
			# verifico la presenza di modifiche per il giorno corrente
			mods = ModificaStraordinaria.objects.select_related().filter(ztl=ztl, giorno=data_corrente)
			for m in mods:
				trovato = True
				fasce.append({
					'ora_inizio': m.ora_inizio,
					'ora_fine': m.ora_fine,
					'inizio_ieri': False,
					'fine_domani': m.fine_domani,
				})
			
			if trovato:
				ret.append({
					'id_ztl': ztl.codice,
					'toponimo': ztl.descrizione,
					'data': data_corrente.strftime("%Y-%m-%d"),
					'fasce': fasce,
				})
	return ret	
ModifichePerDataWS = ztl4.metodo("Modifiche.PerData")(convert_times_to_string(ModifichePerData))

def ModifichePerGiornoSettimana(request, token, dow, data, intervallo):
	
	ret = []
	
	data_inizio = timestamp2date(data)
	
	for i in range(0, (intervallo*7)+1):
	
		data_corrente = data_inizio + timedelta(i)
		
		if dow == int(data_corrente.strftime('%w'))+1:
		
			ztls = ZTL.objects.all()
			for ztl in ztls:
		
				fasce = []
			
				# verifico la presenza di modifiche per il giorno precedente
				mods = ModificaStraordinaria.objects.select_related().filter(ztl=ztl, giorno=data_corrente - timedelta(1), fine_domani=True)
				for m in mods:
					fasce.append({
						'ora_inizio': m.ora_inizio,
						'ora_fine': m.ora_fine,
						'inizio_ieri': True,
						'fine_domani': False,
						'attiva': m.attiva,
					})
			
				# verifico la presenza di modifiche per il giorno corrente
				mods = ModificaStraordinaria.objects.select_related().filter(ztl=ztl, giorno=data_corrente)
				for m in mods:
					fasce.append({
						'ora_inizio': m.ora_inizio,
						'ora_fine': m.ora_fine,
						'inizio_ieri': False,
						'fine_domani': m.fine_domani,
						'attiva': m.attiva,
					})
			
				ret.append({
					'id_ztl': ztl.codice,
					'toponimo': ztl.descrizione,
					'data': data_corrente.strftime("%Y-%m-%d"),
					'fasce': fasce,
				})
	return ret	
ModifichePerGiornoSettimanaWS = ztl4.metodo("Modifiche.PerGiornoSettimana")(convert_times_to_string(ModifichePerGiornoSettimana))

def ModifichePerZTL(request, token, codice, data, intervallo):

	ret = []
	
	data_inizio = timestamp2date(data)
	
	ztl = ZTL.objects.get(codice=codice)
	
	for i in range(0, intervallo+1):
	
		data_corrente = data_inizio + timedelta(days=i)
		
		fasce = []
		
		# verifico la presenza di modifiche per il giorno precedente
		mods = ModificaStraordinaria.objects.select_related().filter(ztl=ztl, giorno=data_corrente - timedelta(1), fine_domani=True)
		for m in mods:
			fasce.append({
				'ora_inizio': m.ora_inizio,
				'ora_fine': m.ora_fine,
				'inizio_ieri': True,
				'fine_domani': False,
				'attiva': m.attiva,
			})
		
		# verifico la presenza di modifiche per il giorno corrente
		mods = ModificaStraordinaria.objects.select_related().filter(ztl=ztl, giorno=data_corrente)
		for m in mods:
			fasce.append({
				'ora_inizio': m.ora_inizio,
				'ora_fine': m.ora_fine,
				'inizio_ieri': False,
				'fine_domani': m.fine_domani,
				'attiva': m.attiva,
			})
		
		ret.append({
			'id_ztl': ztl.codice,
			'toponimo': ztl.descrizione,
			'data': data_corrente.strftime("%Y-%m-%d"),
			'fasce': fasce,
		})
	return ret
ModifichePerZTLWS = ztl4.metodo("Modifiche.PerZtl")(convert_times_to_string(ModifichePerZTL))

def CalendarioZTL(request, token, codice):
	
	ret = []
	
	ztl = ZTL.objects.get(codice=codice)
	
	data = date.today()
	dow = int(data.strftime('%w'))
	
	for i in range(0,7):
		
		fasce = []
		
		# verifico ztl iniziate ieri e finite oggi
		
		dow += 1
		if dow > 7:
			dow = 1
		dow_prec = dow -1
		if dow_prec < 1:
			dow_prec = 7
		
		cal = Calendario.objects.select_related().filter(ztl=ztl, giorno=GiornoSettimana.objects.get(codice=dow_prec), fine_domani=True)
		for c in cal:
			fasce.append({
				'ora_inizio': c.ora_inizio,
				'ora_fine': c.ora_fine,
				'inizio_ieri': True,
				'fine_domani': False,
				})
	
		# verifico ztl per oggi
		cal = Calendario.objects.select_related().filter(ztl=ztl, giorno=GiornoSettimana.objects.get(codice=dow))
		for c in cal:
			# la ztl finisce il giorno dopo, inizio_ieri=0, fine_domani=1
			fasce.append({
				'ora_inizio': c.ora_inizio,
				'ora_fine': c.ora_fine,
				'inizio_ieri': False,
				'fine_domani': c.fine_domani,
				})
		
		ret.append({
			'id_ztl': ztl.codice,
			'toponimo': ztl.descrizione,
			'giorno_settimana': dow,
			'fasce': fasce,
		})
	
	return ret
CalendarioZTLWS = ztl4.metodo("Calendario")(convert_times_to_string(CalendarioZTL))
	
def ListaAccessi(request, token, codice):
	
	varchi = []
	
	attivo = check_ztl_attiva(codice)
	ztl = ZTL.objects.get(codice=codice)
	vs = Varco.objects.filter(ztl=ztl)
	for v in vs:
		varchi.append({
			'id_varco': v.pk,
			'toponimo': v.toponimo,
			'descrizione': v.descrizione,
			'attivo': attivo,
		})
	return{
		'toponimo_ztl': ztl.descrizione,
		'lista_varchi': varchi,
	}
	
	return ret
ListaAccessiWS = ztl4.metodo("ListaAccessi")(ListaAccessi)

def giorni_settimana(escludi=0):
	# costruisce una lista di giorni internazionalizzati, 1=domenica
	gs = []
	# prendo un sabato
	data_iniziale = timestamp2date('2011-11-05')
	for i in range(1, 8):
		if i == escludi:
			pass
		else:
			data = data_iniziale + timedelta(days=i)
			gs.append({
				'codice': i,
				'nome': datefilter(data, _("l"))
			})
	return gs

def giorni_prossima_settimana(escludi=0):
	# costruisce una lista di giorni internazionalizzati della prossima settimana, 1=domenica
	gs = []
	# prendo un sabato
	dt = date.today()
	wd = (dt.weekday() + 2) % 7
	for i in range(7):
		wd_mod = 7 if wd == 0 else wd
		if wd_mod != escludi:
			gs.append({
				'codice': wd_mod,
				'nome': formatta_giorno(dt)
			})
		dt += timedelta(days=1)
		wd = (wd + 1) % 7
	return gs

def per_sito(request):
	orari = Orari(None, "", True, date.today().strftime("%Y-%m-%d"))
	curtime = datetime.today().time()
	modificato = False
	# internazionalizzo gli orari e trovo se ci sono modifiche straordinarie
	for o in orari:
		modificato = modificato or o['modificato']
		fasce_filtrate = []
		for f in o['fasce']:
			# il campo "stato" viene aggiunto e puo' avere 3 valorizzazioni
			# attiva: la ztl e' attiva in questo momento
			# passata: l'orario di fine e' precedente all'orario corrente
			# futura: l'orario di inizio e' successivo all'orario corrente
			if o['modificato']:
				if f['attiva']:
					f['stato'] = "attiva"
				else:
					f['stato'] = "passata"
			else:
				if f['inizio_ieri']:
					if f['ora_fine'] >= curtime:
						f['stato'] = "attiva"
					else:
						f['stato'] = "passata"
				if f['fine_domani']:
					if f['ora_inizio'] > curtime:
						f['stato'] = "futura"
					else:
						f['stato'] = "attiva"

				if not(f['inizio_ieri']) and not(f['fine_domani']):
					if f['ora_inizio'] <= curtime and f['ora_fine'] >= curtime:
						f['stato'] = "attiva"
					elif f['ora_inizio'] > curtime:
						f['stato'] = "futura"
					elif f['ora_fine'] < curtime:
						f['stato'] = "passata"
			#else:
			#	f['stato'] = "passata"
			f['ora_inizio'] = timefilter(f['ora_inizio'], _("H:i"))
			f['ora_fine'] = timefilter(f['ora_fine'], _("H:i"))
			if not f['stato'] == "passata":
				fasce_filtrate.append(f)
		o['fasce'] = fasce_filtrate

	ctx = {'orari': orari, 'modificato': modificato}
	return TemplateResponse(request, 'ztl_per_sito.html', ctx)


def default(request):
	orari = Orari(None, "", True, date.today().strftime("%Y-%m-%d"))
	curtime = datetime.today().time()
	ztl = ZTL.objects.all()
	modificato = False
	# internazionalizzo gli orari e trovo se ci sono modifiche straordinarie
	for o in orari:
		modificato = modificato or o['modificato']
		fasce_filtrate = []
		for f in o['fasce']:
			# il campo "stato" viene aggiunto e puo' avere 3 valorizzazioni
			# attiva: la ztl e' attiva in questo momento
			# passata: l'orario di fine e' precedente all'orario corrente
			# futura: l'orario di inizio e' successivo all'orario corrente
			if o['modificato']:
				if f['attiva']:
					f['stato'] = "attiva"
				else:
					f['stato'] = "passata"
			else:
				if f['inizio_ieri']:
					if f['ora_fine'] >= curtime:
						f['stato'] = "attiva"
					else:
						f['stato'] = "passata"
				if f['fine_domani']:
					if f['ora_inizio'] > curtime:
						f['stato'] = "futura"
					else:
						f['stato'] = "attiva"
		
				if not(f['inizio_ieri']) and not(f['fine_domani']):
					if f['ora_inizio'] <= curtime and f['ora_fine'] >= curtime:
						f['stato'] = "attiva"
					elif f['ora_inizio'] > curtime:
						f['stato'] = "futura"
					elif f['ora_fine'] < curtime:
						f['stato'] = "passata"	
			#else:
			#	f['stato'] = "passata"
			f['ora_inizio'] = timefilter(f['ora_inizio'], _("H:i"))
			f['ora_fine'] = timefilter(f['ora_fine'], _("H:i"))
			if not f['stato'] == "passata":
				fasce_filtrate.append(f)
		o['fasce'] = fasce_filtrate	
	
	gs = giorni_prossima_settimana()
	
	ctx = {'orari': orari, 'modificato': modificato, 'ztl': ztl, 'gs': gs}
	return TemplateResponse(request, 'ztl.html', ctx)

def varchi_menu(request):

	ztl = ZTL.objects.all()
	ctx = {'ztl': ztl}
	return TemplateResponse(request, 'ztl_varchi_menu.html', ctx)

def varchi_dettaglio(request, codice):
	accessi = ListaAccessi(None, '', codice)
	altre_ztl = ZTL.objects.exclude(codice=codice)
	ztl = ZTL.objects.get(codice=codice)
	
	ctx = {'accessi': accessi, 'altre_ztl': altre_ztl}
	return TemplateResponse(request, 'ztl_varchi_dettaglio.html', ctx)

def info(request):
	return TemplateResponse(request, 'ztl_info.html', None)

def prossimo_giorno(dow):
	"""
	Restituisce, come data, il prossimo giorno avente dow come giorno della settimana
	"""
	dow = (dow - 2) % 7
	dt = date.today()
	while dt.weekday() != dow:
		dt = dt + timedelta(days=1)
	return dt

def formatta_giorno(dt):
	"""
	Formatta internazionalmente la data dt nel formato Giorno_settimana Numero (es. Domenica 14)
	"""
	return datefilter(dt, _("l j")).capitalize()

def giorno(request, giorno):
	
	ztl = ZTL.objects.all()
	
	orari = []
	
	modificato_globale = False
	
	# nome del giorno selezionato, internazionalizzato
	dow = int(giorno)
	dt = prossimo_giorno(dow)
	nome_giorno = formatta_giorno(dt)
	nome_giorno_prec = formatta_giorno(dt - timedelta(days=1))
	nome_giorno_succ = formatta_giorno(dt + timedelta(days=1))
	
	gs = giorni_prossima_settimana(escludi=int(giorno))
	
	# recupero le modifiche straordinarie
	mods = ModifichePerGiornoSettimana(None, '', int(giorno), date.today().strftime("%Y-%m-%d"), 1)
	
	for z in ztl:
	
		fasce = []
		fasce_mod = []
		
		modificato = False
		
		# se esistono modifiche straordinarie per il giorno, uso solo quelle
		for m in mods:
			if m['id_ztl'] == z.codice:
				for f in m['fasce']:
					# esistono modifiche straordinarie
					modificato = True
					modificato_globale = True
					fasce_mod.append({
						'ora_inizio': timefilter(f['ora_inizio'], _("H:i")),
						'ora_fine': timefilter(f['ora_fine'], _("H:i")),
						'inizio_ieri': f['inizio_ieri'],
						'fine_domani': f['fine_domani'],
						'attiva': f['attiva'],
					})
				
				
		# verifico ztl iniziate ieri e finite oggi
		giorno_prec = int(giorno) - 1
		if giorno_prec < 1:
			giorno_prec = 7
		cal = Calendario.objects.select_related().filter(ztl=z, giorno__codice=giorno_prec, fine_domani=True)
		for c in cal:
			fasce.append({
				'ora_inizio': timefilter(c.ora_inizio, _("H:i")),
				'ora_fine': timefilter(c.ora_fine, _("H:i")),
				'inizio_ieri': True,
				'fine_domani': False,
				})

		# verifico ztl per oggi
		cal = Calendario.objects.select_related().filter(ztl=z, giorno__codice=giorno)
		for c in cal:
			# la ztl finisce il giorno dopo, inizio_ieri=0, fine_domani=1
			fasce.append({
				'ora_inizio': timefilter(c.ora_inizio, _("H:i")),
				'ora_fine': timefilter(c.ora_fine, _("H:i")),
				'inizio_ieri': False,
				'fine_domani': c.fine_domani,
				})
		
		orari.append({
			'id_ztl': z.codice,
			'toponimo': z.descrizione,
			'modificato': modificato,
			'fasce': fasce,
			'fasce_mod': fasce_mod,
		})
		
		
	ctx = {'orari': orari, 'modificato_globale': modificato_globale, 'gs': gs, 'nome_giorno': nome_giorno, 'nome_giorno_prec': nome_giorno_prec, 'nome_giorno_succ': nome_giorno_succ, 'ztl': ztl}
	return TemplateResponse(request, 'ztl_giorno.html', ctx)

def ztl(request, codice):
	
	ztl = ZTL.objects.get(codice=codice)
	altre_ztl = ZTL.objects.exclude(codice=codice)
	
	# recupero il calendario della settimana per la ztl ed internazionalizzo
	cal = CalendarioZTL(None, '', codice)

	# recupero le modifiche per la prossima settimana ed internazionalizzo
	mods = ModifichePerZTL(None, '', codice, date.today().strftime("%Y-%m-%d"), 7)
	mods = {m['data']: m for m in mods}

	for c in cal:
		# nome del giorno selezionato, internazionalizzato
		dow = int(c['giorno_settimana'])
		dt = prossimo_giorno(dow)
		c['giorno_settimana'] = formatta_giorno(dt).capitalize()
		c['giorno_succ'] = formatta_giorno(dt + timedelta(days=1)).capitalize()
		c['giorno_prec'] = formatta_giorno(dt - timedelta(days=1)).capitalize()
		for f in c['fasce']:
			f['ora_inizio'] = timefilter(f['ora_inizio'], _("H:i"))
			f['ora_fine'] = timefilter(f['ora_fine'], _("H:i"))
		m = mods[date2mysql(dt)]
		c['modificato'] = len(m['fasce']) > 0
		for f in m['fasce']:
			f['ora_inizio'] = timefilter(f['ora_inizio'], _("H:i"))
			f['ora_fine'] = timefilter(f['ora_fine'], _("H:i"))
		c['fasce_mod'] = m['fasce']
	


	ctx = {'cal': cal, 'ztl': ztl, 'altre_ztl': altre_ztl}
	return TemplateResponse(request, 'ztl_cal.html', ctx)
	
def modifiche(request):
	
	data = date.today()
	mods = ModifichePerData(None, '', data.strftime("%Y-%m-%d"), 14)
	# internazionalizzo la data e gli orari
	for m in mods:
		m['data'] = datefilter(timestamp2date(m['data']), _("d-m-Y"))
		for f in m['fasce']:
			f['ora_inizio'] = timefilter(f['ora_inizio'], _("H:i"))
			f['ora_fine'] = timefilter(f['ora_fine'], _("H:i"))
	gs = giorni_prossima_settimana()
	ztl = ZTL.objects.all()
	ctx = {'mods': mods, 'gs': gs, 'ztl': ztl}
	return TemplateResponse(request, 'ztl_modifiche.html', ctx)
