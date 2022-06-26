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


from dbf import *
from datetime import date, time, datetime, timedelta 
import sys
from paline.models import *
from servizi.models import Festivita
from django import db
from django.db import transaction
from django.core import serializers
from servizi.utils import transaction as autotransaction
import traceback
from zipfile import ZipFile
from servizi.utils import mysql2datetime, datetime2compact, multisplit, date2mysql, xmlrpc2datetime
import os, os.path, shutil
import settings
import xmlrpclib
from paline import tpl
import subprocess
import paline.grafo as graph
from django.core.mail import send_mail
from pprint import pprint

#Configuration
carteggiFile = 'carteggi.DBF'
palineFile = 'paline.DBF'
gestoriFile = 'gestori.DBF'
lineeFile = 'linee.DBF'
fermateFile = 'fermate.DBF'
percorsiFile = 'percorsi.DBF'
transcodificaFile = 'transcod.DBF'
descrizionePercorsiFile = 'descrizioni.DBF'
percorsiNoOrariFile = 'eccezione_orari.DBF'


def lancia_processo_caricamento_rete():
	cmd = "python manage.py carica_rete_new email"
	p = subprocess.Popen(cmd.split())
	
def scarica_rete():
	print "Autenticazione"
	sa = xmlrpclib.Server('%s/ws/xml/autenticazione/1' % settings.WS_BASE_URL)
	sp = xmlrpclib.Server('%s/ws/xml/paline/7' % settings.WS_BASE_URL)
	token = sa.autenticazione.Accedi(settings.DEVELOPER_KEY, '')	
	print "Download rete"
	res = sp.paline.GetRete(token)['risposta']
	print "Salvataggio rete"
	try:
		os.mkdir(os.path.join(settings.TROVALINEA_PATH_RETE, 'temp'))
	except:
		pass
	f = open(os.path.join(settings.TROVALINEA_PATH_RETE, 'temp/rete.zip'), 'wb')
	f.write(res['rete'].data)
	f.close()
	f = open(os.path.join(settings.TROVALINEA_PATH_RETE, 'temp/shp.zip'), 'wb')
	f.write(res['shp'].data)
	f.close()
	print "Rete scaricata"


def carica_rete_auto():
	try:
		versione = carica_rete()
		if versione is None:
			# Nessuna rete nuova da caricare, in quanto l'ultima rete uploadata ha lo stesso orario di inizio validità
			# di una rete già caricata. Esco senza mandare messaggi per email
			return
		#self.scheduler.insert(versione, self.on_aggiorna_versione)
		subj = u"Rete caricata con successo"
		msg = u"Buone notizie: la rete è stata caricata con successo su muoversiaroma.it\n"
		msg += u"La rete è attiva a partire dal seguente orario: %s" % datetime2mysql(versione)
	except Exception, e:
		subj = u"Errore caricamento rete"
		msg = u"Muoversiaroma.it non ha potuto caricare la rete a causa del seguente errore:\n\n"
		msg += traceback.format_exc()
	send_mail(subj, msg, 'muoversiaroma@muoversiaroma.it', settings.DESTINATARI_MAIL_CARICA_RETE, fail_silently=True)


def carica_rete(no_load=False, no_validate=False):
	versione = processa_file_zip(no_load)
	if versione is None:
		return None
	transaction.enter_transaction_management()
	transaction.managed(True)
	if not no_load:
		if len(VersionePaline.objects.filter(inizio_validita=versione)) > 0:
			# raise Exception(u"Esiste gia' una rete con l'inizio di validita' indicato")
			return None
		base = os.path.join(settings.TROVALINEA_PATH_RETE, '%s/rete' % datetime2compact(versione))
		path = lambda f: os.path.join(base, f)
		generaRete(versione)
		caricaCarteggi(path(carteggiFile))
		caricaPaline(path(palineFile))
		caricaGestori(path(gestoriFile))
		caricaLinee(path(lineeFile))
		caricaPercorsi(path(percorsiFile), path(descrizionePercorsiFile), percorsiNoOrariFile=path(percorsiNoOrariFile))
		caricaFermate(path(fermateFile))
		attivaNuovaRete()
		transaction.commit()
		db.reset_queries()
	if not no_validate:
	# Validazione
		try:
			print "Validazione caricamento rete"
			r = tpl.Rete()
			r.carica(versione=versione)
			print "Validazione distanza tratti percorso"
			out = r.valida_distanze()
			if out != "":
				raise Exception(out)
			print "Validazione connessione rete a grafo"
			g = graph.Grafo()
			tpl.registra_classi_grafo(g)
			#tomtom.load_from_shp(g, 'C:\\Users\\allulll\\Desktop\\grafo\\cpd\\RM_nw%s' % ('_mini' if retina else ''))
			g.deserialize(os.path.join(settings.TROVALINEA_PATH_RETE, '%s.v3.dat' % settings.GRAPH))
			tpl.carica_rete_su_grafo(r, g, False, versione=versione)
		
		except Exception, e:
			print "Validazione fallita"
			traceback.print_exc()
			v = VersionePaline.objects.ultima()
			v.attiva = False
			v.save()
			transaction.commit()
			raise e

	print "Rete aggiornata con successo"
	return versione


def carica_rete_incrementale(no_load=False, no_validate=False):
	versione = processa_file_zip(no_load)
	if versione is None:
		return None
	transaction.enter_transaction_management()
	transaction.managed(True)
	if not no_load:
		base = os.path.join(settings.TROVALINEA_PATH_RETE, '%s/rete' % datetime2compact(versione))
		path = lambda f: os.path.join(base, f)
		print "---Carico versione precedente di rete"
		rete_base = tpl.Rete()
		rete_base.carica()
		print "---Estendo validità rete attuale"
		generaRete(versione)
		Carteggio.extend_to_current_version()
		Palina.extend_to_current_version()
		Gestore.extend_to_current_version()
		Linea.extend_to_current_version()
		Percorso.extend_to_current_version()
		Fermata.extend_to_current_version()
		print "---Carico elementi nuovi o modificati"
		caricaCarteggi(path(carteggiFile), sovrascrivi=True)
		caricaPaline(path(palineFile), sovrascrivi=True)
		caricaGestori(path(gestoriFile), sovrascrivi=True)
		caricaLinee(path(lineeFile), sovrascrivi=True)
		caricaPercorsi(path(percorsiFile), path(descrizionePercorsiFile), percorsiNoOrariFile=path(percorsiNoOrariFile), sovrascrivi=True)
		caricaFermate(path(fermateFile), sovrascrivi=True)
		attivaNuovaRete()
		transaction.commit()
		db.reset_queries()
		print "---Carico nuovi elementi geografici"

	if not no_validate:
	# Validazione
		try:
			print "Validazione caricamento rete"
			r = tpl.Rete()
			r.carica(versione=versione, rete_base=rete_base)
			print "Validazione distanza tratti percorso"
			out = r.valida_distanze()
			if out != "":
				raise Exception(out)
			print "Validazione connessione rete a grafo"
			g = graph.Grafo()
			tpl.registra_classi_grafo(g)
			#tomtom.load_from_shp(g, 'C:\\Users\\allulll\\Desktop\\grafo\\cpd\\RM_nw%s' % ('_mini' if retina else ''))
			g.deserialize(os.path.join(settings.TROVALINEA_PATH_RETE, '%s.v3.dat' % settings.GRAPH))
			tpl.carica_rete_su_grafo(r, g, False, versione=versione)

		except Exception, e:
			print "Validazione fallita"
			traceback.print_exc()
			v = VersionePaline.objects.ultima()
			v.attiva = False
			v.save()
			transaction.commit()
			raise e
	print "Rete aggiornata con successo"
	return versione


def carica_rete_in_memoria(path_base):
	path = lambda f: os.path.join(path_base, f)
	carteggi = caricaCarteggi(path(carteggiFile), True)
	paline = caricaPaline(path(palineFile), True)
	#caricaGestori(path(gestoriFile))
	linee = caricaLinee(path(lineeFile), True)
	percorsi = caricaPercorsi(path(percorsiFile), path(descrizionePercorsiFile), True, carteggi=carteggi)
	fermate = caricaFermate(path(fermateFile), True)
	return {
		'paline': paline,
		'linee': linee,
		'percorsi': percorsi,
		'fermate': fermate,
	}


def processa_file_zip(no_load=False):
	"""
	Estrae i file zip nel path corretto, e restituisce l'orario di inizio validità della rete
	"""
	rete_zip_path = os.path.join(settings.TROVALINEA_PATH_RETE, 'temp/rete.zip')
	shp_zip_path = os.path.join(settings.TROVALINEA_PATH_RETE, 'temp/shp.zip')
	rete = ZipFile(rete_zip_path)
	versione = mysql2datetime(rete.read('validita.txt')[:19])
	if no_load:
		return versione
	if len(VersionePaline.objects.filter(inizio_validita=versione)) > 0:
		# raise Exception(u"Esiste gia' una rete con l'inizio di validita' indicato")
		return None
	prefix = os.path.join(settings.TROVALINEA_PATH_RETE, datetime2compact(versione))
	rete_path = os.path.join(prefix, 'rete')
	shp_path = os.path.join(prefix, 'shp')
	shutil.rmtree(prefix, ignore_errors=True)
	os.makedirs(rete_path)
	os.makedirs(shp_path)
	shutil.copy(rete_zip_path, prefix)
	shutil.copy(shp_zip_path, prefix)	
	rete.extractall(rete_path)
	rete.close()
	shp = ZipFile(shp_zip_path)
	path = os.path.join(settings.TROVALINEA_PATH_RETE, 'temp/shp')
	shutil.rmtree(path, ignore_errors=True)
	os.mkdir(path)
	shp.extractall(path)
	sub = os.path.join(path, os.listdir(path)[0])
	ls = os.listdir(sub)
	for l in ls:
		shutil.move(os.path.join(sub, l), shp_path)
	shp.close()
	return versione

def time2sec(time):
	return time.hour * 3600 + time.minute * 60 + time.second


def datetime2mysql(dt):
	return "%04d-%02d-%02d %02d:%02d:%02d" % (dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second)

def date2mysql(dt):
	return "%04d-%02d-%02d" % (dt.year, dt.month, dt.day)


def generateColumnExtractor(description):
	k = 0
	cols = {}
	for item in description:
		cols[item[0]] = k
		k = k + 1
		
	def extractor(row, col):
		return row[cols[col]]

	return extractor

def caricaCarteggi(carteggiFile, in_memoria=False, sovrascrivi=False):
	dbf = Dbf()
	dbf.openFile(carteggiFile)
	print "Carico carteggi"
	cs = {}
	for row in dbf:
		if not in_memoria:
			codice = row['CODICE']
			if sovrascrivi:
				Carteggio.objects.delete_queryset(Carteggio.objects.by_date().filter(codice=codice))
			Carteggio(
				codice=codice,
				descrizione=row['DESCRIZ'],
			).save()
		else:
			cs[row['CODICE']] = row['DESCRIZ']
	return cs

	
def caricaPaline(palineFile, in_memoria=False, sovrascrivi=False):
	dbf = Dbf()
	dbf.openFile(palineFile)
	ps = []
	print "Carico paline"
	for row in dbf:
		nome = row['NOME']
		if not in_memoria:
			id_palina = row['ID_PALINA']
			if sovrascrivi:
				Palina.objects.delete_queryset(Palina.objects.by_date().filter(id_palina=id_palina))
			p = Palina(
				id_palina=id_palina,
				nome=nome,
				descrizione=row['DESCRIZION'],
				soppressa=(row['SOPPRESSA'] == 'TRUE'),
			)
			p.save()
			parti = multisplit(nome, [" ", "/"])
			for parte in parti:
				NomePalina(
					parte=parte,
					palina=p
				).save()
		else:
			ps.append({
				'id_palina': row['ID_PALINA'],
				'nome': nome,
				'descrizione': row['DESCRIZION'],
				'soppressa': (row['SOPPRESSA'] == 'TRUE'),
			})
	if in_memoria:
		return ps

def caricaGestori(gestoriFile, sovrascrivi=False):
	dbf = Dbf()
	dbf.openFile(gestoriFile)
	print "Carico gestori"
	for row in dbf:
		nome = row['GESTORE']
		if sovrascrivi:
			Gestore.objects.delete_queryset(Gestore.objects.by_date().filter(nome=nome))
		Gestore(
			nome=nome,
			descrizione=row['DESCRIZION'],
		).save()

def caricaLinee(lineeFile, in_memoria=False, sovrascrivi=False):
	dbf = Dbf()
	dbf.openFile(lineeFile)
	ls = {}
	print "Carico linee"
	for row in dbf:
		tipo = 'BU'
		if row['FERR_CONCE'] == 'TRUE':
			tipo = 'FC'
		elif row['FERR_REGIO'] == 'TRUE':
			tipo = 'FR'			
		elif row['METRO'] == 'TRUE':
			tipo = 'ME'
		elif row['TRAM'] == 'TRUE':
			tipo = 'TR'				
		if not in_memoria:
			try:
				g = Gestore.objects.with_latest_version().get(nome=row['GESTORE'])
			except Gestore.DoesNotExist:
				raise Exception("%s: il gestore con id %s non esiste" % (lineeFile, row['GESTORE']))
			id_linea = row['ID_LINEA']
			if sovrascrivi:
				Linea.objects.delete_queryset(Linea.objects.by_date().filter(id_linea=id_linea))
			Linea(
				id_linea=id_linea,
				monitorata=row['ABILITATA'],
				gestore=g,
				tipo=tipo,
			).save()
		else:
			ls[row['ID_LINEA']] = {
				'id_linea': row['ID_LINEA'],
				'monitorata': row['ABILITATA'],
				'id_gestore': row['GESTORE'],
				'tipo': tipo,
			}
	if in_memoria:
		return ls
		
		
def caricaPercorsi(percorsiFile, descrizionePercorsiFile, in_memoria=False, linee=None, carteggi=None, percorsiNoOrariFile=None, sovrascrivi=False):
	# Carico descrizione percorsi
	dbf = Dbf()
	dbf.openFile(descrizionePercorsiFile)
	ps = []
	print "Carico descrizione percorsi"
	descrizioni = {}
	for row in dbf:
		descrizioni[str(row['ID_PERCORS'])] = row['DESCRIZION']
	# Carico percorsi		
	percorsi_no_orario = {}
	if percorsiNoOrariFile is not None:
		print "Carico percorsi senza orario"
		dbf = Dbf()
		dbf.openFile(percorsiNoOrariFile)
		for row in dbf:
			percorsi_no_orario[row['IDPERCORSO']] = row['NOTEUTENTE']
	print "Carico percorsi e associazione carteggi"
	dbf = Dbf()
	dbf.openFile(percorsiFile)	
	for row in dbf:
		carteggio = row['CARTEGGIO']
		soppresso = row['ATTIVO'] == 'FALSE'
		if row['VERSO'] == 'Asc':
			verso = 'A'
			precart = 'A'
		else:
			verso = 'R'
			precart = 'R'
		id_percorso = str(row['IDPERCORSO'])		
		if not in_memoria:
			try:
				linea = Linea.objects.with_latest_version().get(id_linea=row['ID_LINEA'])
			except Linea.DoesNotExist:
				raise Exception("%s: la linea con id %s non esiste" % (percorsiFile, row['ID_LINEA']))
			try:
				partenza = Palina.objects.with_latest_version().get(id_palina=row['PARTENZA'])
			except Palina.DoesNotExist:
				raise Exception("%s: la palina di partenza con id %s non esiste" % (percorsiFile, row['PARTENZA']))
			try:
				arrivo = Palina.objects.with_latest_version().get(id_palina=row['ARRIVO'])
			except Palina.DoesNotExist:
				raise Exception("%s: la palina di arrivo con id %s non esiste" % (percorsiFile, row['ARRIVO']))
			if partenza == arrivo:
				verso = 'C'
				precart = ''
			if sovrascrivi:
				if sovrascrivi:
					Fermata.objects.delete_queryset(Fermata.objects.by_date().filter(percorso__id_percorso=id_percorso))
					Percorso.objects.delete_queryset(Percorso.objects.by_date().filter(id_percorso=id_percorso))
			Percorso(
				id_percorso=id_percorso,
				linea=linea,
				partenza=partenza,
				arrivo=arrivo,
				verso=verso,
				carteggio=precart + carteggio,
				carteggio_quoz=carteggio,
				descrizione=None if id_percorso not in descrizioni else descrizioni[id_percorso],
				no_orari=id_percorso in percorsi_no_orario,
				note_no_orari=percorsi_no_orario[id_percorso] if id_percorso in percorsi_no_orario else '',
				soppresso=soppresso,
			).save()
		else:
			id_linea = row['ID_LINEA']
			if id_percorso in descrizioni:
				descrizione = descrizioni[id_percorso]
			else:
				descrizione = "%s %s" % (id_linea, " ".join([carteggi[x] for x in carteggio]), )
			ps.append({
				'id_percorso': str(id_percorso),
				'carteggio': carteggio,
				'id_linea': id_linea,
				'descrizione': descrizione,
				'soppresso': soppresso,
			})	
	if in_memoria:
		return ps
			

def caricaFermate(fermateFile, in_memoria=False, sovrascrivi=False):
	dbf = Dbf()
	dbf.openFile(fermateFile)
	fs = {}
	print "Carico fermate"
	for row in dbf:
		if not in_memoria:
			try:
				percorso = Percorso.objects.with_latest_version().get(id_percorso=row['IDPERCORSO'])
			except Percorso.DoesNotExist:
				raise Exception("%s: il percorso con id %s non esiste" % (fermateFile, row['IDPERCORSO']))
			try:
				palina = Palina.objects.with_latest_version().get(id_palina=row['ID_PALINA'])
			except Palina.DoesNotExist:
				raise Exception("%s: la palina con id %s non esiste" % (fermateFile, row['ID_PALINA']))
			# Non è necessario eliminare le fermate vecchie perché sono già state eliminate con i vecchi percorsi
			Fermata(
				percorso=percorso,
				palina=palina,
				progressiva=row['PROG'],
			).save()
		else:
			id_percorso = row['IDPERCORSO']
			if not id_percorso in fs:
				fs[id_percorso] = []
			fs[id_percorso].append({
				'id_percorso': id_percorso,
				'id_palina': row['ID_PALINA'],
				'progressiva': row['PROG'],
			})
	return fs


def generaRete(inizio_validita):
	print "Creazione nuova versione della rete..."
	v = VersionePaline.auto_create(inizio_validita)
	v.save()
	print "Creata versione %d" % v.numero
		
def attivaNuovaRete():
	print "Attivazione nuova rete..."
	v = VersionePaline.objects.ultima()
	v.attiva = True
	v.save()


def scarica_orari_partenza_giorno(giorno):
	print "Autenticazione"
	sa = xmlrpclib.Server('%s/ws/xml/autenticazione/1' % settings.WS_BASE_URL)
	sp = xmlrpclib.Server('%s/ws/xml/paline/7' % settings.WS_BASE_URL)
	token = sa.autenticazione.Accedi(settings.DEVELOPER_KEY, '')
	print "Download orari", giorno
	os2 = sp.paline.GetPartenzeCapilinea(token, date2mysql(giorno))['risposta']
	print "Aggiornamento orari nel database"
	ok = 0
	added = 0
	deleted = 0
	with autotransaction():
		giorno_succ = giorno + timedelta(days=1)
		os1 = PartenzeCapilinea.objects.filter(orario_partenza__gte=giorno, orario_partenza__lt=giorno_succ)
		os1 = set([(o.id_percorso, o.orario_partenza) for o in os1])
		for o in os2:
			k = (o['id_percorso'], xmlrpc2datetime(o['orario_partenza']))
			if k in os1:
				os1.remove(k)
				ok += 1
			else:
				PartenzeCapilinea(
					id_percorso=k[0],
					orario_partenza=k[1],
				).save()
				added += 1
		for k in os1:
			PartenzeCapilinea.objects.filter(id_percorso=k[0], orario_partenza=k[1]).delete()
			deleted += 1
	print "Aggiornamento completato: {} invariati, {} inseriti, {} eliminati".format(ok, added, deleted)


def scarica_orari_partenza():
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
		scarica_orari_partenza_giorno(g)


def scarica_stat_passaggi():
	print "Autenticazione"
	sa = xmlrpclib.Server('%s/ws/xml/autenticazione/1' % settings.WS_BASE_URL)
	sp = xmlrpclib.Server('%s/ws/xml/paline/7' % settings.WS_BASE_URL)
	token = sa.autenticazione.Accedi(settings.DEVELOPER_KEY, '')	
	print "Download statistiche passaggi"
	stat = sp.paline.GetStatPassaggi(token)['risposta']
	print "Caricamento statistiche nel database"
	with autotransaction():
		StatPeriodoAggregazione.objects.all().delete()
		StatTempoAttesaPercorso.objects.all().delete()
		for obj in serializers.deserialize("json", stat['periodi_aggregazione'].data):
			obj.save()
		for obj in serializers.deserialize("json", stat['tempi_attesa_percorsi'].data):
			obj.save()
