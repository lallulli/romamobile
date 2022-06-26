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

from models import *
from django.db import models, connections, transaction
from servizi.utils import dict_cursor, project, datetime2mysql, group_required
from datetime import datetime, timedelta, time, date
from jsonrpc import jsonrpc_method
from servizi.models import GiornoSettimana
from time import strptime, strftime

@jsonrpc_method('ztl_get_lista')
#@group_required('operatori')
def get_lista(request):
	"""
	Restituisce la lista delle ztl censite
	
	[
		{
			'id_ztl': pk,
			'descrizione': descrizione
		}
	]
	"""
	ret = []
	ztls = ZTL.objects.all()
	for z in ztls:
		ret.append({
			'id_ztl': z.codice,
			'descrizione': z.descrizione
		})
	return ret

@jsonrpc_method('ztl_get_calendario')
#@group_required('operatori')
def get_calendario(request, codice):
	"""
	Restituisce il calendario per una ztl
	
	[{
		'id_ztl': pk,
		'toponimo': descrizione,
		'giorno_settimana': dow,
		'fasce': [{
			'ora_inizio': ora_inizio,
			'ora_fine': ora_fine,
			'inizio_ieri': inizio_ieri,
			'fine_domani': fine_domani
		}]
	}]
	"""
	
	ret = []
	
	ztl = ZTL.objects.get(codice=codice)
	
	dow = 1 # parto sempre dal lunedi
	
	for i in range(0,7):
		
		fasce = []
		
		# verifico ztl iniziate ieri e finite oggi
		
		dow += 1
		if dow > 7:
			dow = 1
		dow_prec = dow -1
		if dow_prec < 1:
			dow_prec = 7
		#
		#cal = Calendario.objects.select_related().filter(ztl=ztl, giorno=GiornoSettimana.objects.get(codice=dow_prec), fine_domani=True)
		#for c in cal:
	#		fasce.append({
	#			'ora_inizio': c.ora_inizio,
	#			'ora_fine': c.ora_fine,
	#			'inizio_ieri': True,
	#			'fine_domani': False,
	#			})
	
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
		
		g = GiornoSettimana.objects.get(codice=dow)
		ret.append({
			'id_ztl': ztl.codice,
			'toponimo': ztl.descrizione,
			'giorno_settimana': g.nome,
			'codice_giorno_settimana': g.codice,
			'fasce': fasce,
		})
	
	return ret

@jsonrpc_method('ztl_set_calendario')
#@group_required('operatori')
def set_calendario(request, dati):
	"""
	Salva un calendario
	"""
	
	ztl = ZTL.objects.get(pk=dati['id_ztl'])
	giorno = GiornoSettimana.objects.get(codice=dati['gs'])
	cgc = Calendario.objects.get_or_create(ztl=ztl, giorno=giorno)
	c = cgc[0]
	c.ora_inizio = dati['ora_inizio']
	c.ora_fine = dati['ora_fine']
	c.fine_domani = dati['fine_domani']
	c.save()

@jsonrpc_method('ztl_get_giorno_calendario')
#@group_required('operatori')
def get_giorno_calendario(request, dati):
	"""
	Restituisce un giorno specifico del calendario per una ztl
	
	{
		'id_ztl': id_ztl,
		'giorno_settimana': dow,
		'ora_inizio': ora_inizio,
		'ora_fine': ora_fine,
		'fine_domani': fine_domani
	}
	"""
	ztl = ZTL.objects.get(pk=dati['id_ztl'])
	giorno = GiornoSettimana.objects.get(codice=dati['gs'])
	try:
		c = Calendario.objects.get(ztl=ztl, giorno=giorno)
		return {
			'ora_inizio': c.ora_inizio,
			'ora_fine': c.ora_fine,
			'fine_domani': c.fine_domani
		}

	except:
		# il giorno non esiste in calendario
		return {
			'ora_inizio': '',
			'ora_fine': '',
			'fine_domani': ''
		}


@jsonrpc_method('ztl_del_giorno_calendario')
#@group_required('operatori')
def del_giorno_calendario(request, codice, gs):
	ztl = ZTL.objects.get(codice=codice)
	giorno = GiornoSettimana.objects.get(codice=gs)
	c = Calendario.objects.get(ztl=ztl, giorno=giorno)
	c.delete()

@jsonrpc_method('ztl_set_modifica')
#@group_required('operatori')
def set_modifica_straordinaria(request, dati):
	"""
	Crea una modifica straordinaria
	"""
	ztl = ZTL.objects.get(codice=dati['id_ztl'])
	msgc = ModificaStraordinaria.objects.get_or_create(ztl = ztl,	giorno = dati['giorno'])
	ms = msgc[0]
	ms.ora_inizio = dati['ora_inizio']
	ms.ora_fine = dati['ora_fine']
	ms.attiva = dati['attiva']
	ms.fine_domani = dati['fine_domani']
	ms.save()

@jsonrpc_method('ztl_get_modifiche')
#@group_required('operatori')
def get_modifica_straordinaria(request, codice):
	"""
	Lista delle modifiche straordinarie
	"""
	ztl = ZTL.objects.get(codice=codice)
	ms = ModificaStraordinaria.objects.filter(ztl=ztl, giorno__gte=date.today()).order_by('giorno')
	ret = []
	for m in ms:
		r = {
			'giorno': m.giorno.strftime('%Y-%m-%d'),
			'ora_inizio': m.ora_inizio,
			'ora_fine': m.ora_fine,
			'attiva': m.attiva,
			'fine_domani': m.fine_domani,
		}
		ret.append(r)
	return ret

@jsonrpc_method('ztl_del_modifica')
#@group_required('operatori')
def del_modifica_straordinaria(request, data):
	"""
	Lista delle modifiche straordinarie
	"""
	ztl = ZTL.objects.get(codice=data['id_ztl'])
	m = ModificaStraordinaria.objects.get(ztl=ztl, giorno=data['giorno'])
	m.delete()