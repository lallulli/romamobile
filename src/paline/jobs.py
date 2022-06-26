# coding: utf-8

#
#    Copyright 2015-2016 Roma servizi per la mobilità srl
#    Developed by Luca Allulli
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

from stats.models import get_data_limite
from servizi.models import sospendi_servizi
from paline.models import LogTempoArco, LogTempoAttesaPercorso, ArcoRimosso, VersionePaline
from paline.models import PartenzeCapilinea
from paline import tpl
from datetime import datetime, date, time, timedelta
from django.db import connections, transaction
from django.db.models import Min, Sum
from django.contrib.sessions.models import Session
from servizi.utils import datetime2date, date2datetime, mysql2datetime, date2mysql, dateandtime2datetime
from servizi.utils import transaction_commit_manually, template_to_mail
from mercury.models import DaemonControl
from paline.caricamento_rete.caricamento_rete import carica_rete_auto, scarica_orari_partenza_giorno, scarica_rete
from gtfs import parse_static
import traceback
import os, os.path, shutil
import settings


MANTIENI_GIORNI_PARTENZE = timedelta(days=30)
MANTIENI_SESSIONI_SCADUTE = timedelta(days=30)


@transaction_commit_manually
def _aggrega_stat_data(job=None, data=None):
	"""
	Metodo interno invocato da aggrega_stat
	"""
	connection = connections['default']
	cursor = connection.cursor()
	print "Elaboro statistiche"
	cursor.execute('''
		insert ignore into paline_logtempoarcoaggr(id_palina_s, id_palina_t, data, ora, tempo, peso)
		select id_palina_s, id_palina_t, data, hour(ora) as ora, sum(peso*tempo)/sum(peso) as tempo, sum(peso) as peso
		from paline_logtempoarco
		where data = %s
		group by hour(ora), id_palina_s, id_palina_t;
	''', (data, ))
	transaction.commit()


def aggrega_stat(job=None, data_limite=None):
	"""
	Aggrega i log_tempo_arco per fascia oraria

	Non cancella i log dal db, calcola solo le statistiche.
	Pertanto usa la data annotata nel job come data di partenza per le statistiche
	"""
	assert job is not None, "Il job non puo' essere None"

	d = job.last_element_ts
	while not esci:
		d = d + timedelta(days=1)
		if d <= data_limite:
			_aggrega_stat_data(job, d)
			job.last_element_ts = d
			job.keep_alive()
		else:
			esci = True


def elimina_file_rete_obsoleti(job=None):
	"""
	Elimina i file della rete più vecchi di 15 giorni.

	Mantiene comunque le ultime 5 reti
	"""
	RETI_DA_MANTENERE = 5
	GIORNI_DA_MANTENERE = 15

	path = settings.TROVALINEA_PATH_RETE
	fs = os.listdir(path)
	fs = [f for f in fs if f.startswith('20')]
	fs.sort()
	print fs
	fs = fs[:-RETI_DA_MANTENERE]
	data_limite = (datetime.now() - timedelta(days=GIORNI_DA_MANTENERE)).strftime('%Y%m%d')
	print "Cancello fino alla data limite: %s" % data_limite
	for f in fs:
		if f < data_limite:
			print "Deleting %s" % f
			shutil.rmtree(os.path.join(path, f))

	return (0, 'OK')


def _db_cleanup(job=None):
	now = datetime.now()
	print "Cleaning up old departures"
	PartenzeCapilinea.objects.filter(orario_partenza__lte=now - MANTIENI_GIORNI_PARTENZE).delete()
	print "Cleaning up old sessions"
	Session.objects.filter(expire_date__lte=now - MANTIENI_SESSIONI_SCADUTE).delete()
	# connection = connections['default']
	# cursor = connection.cursor()
	# print "Vacuuming db"
	# cursor.execute("vacuum")
	print "Cleanup done"
	return 0, "OK"


def db_cleanup(job=None):
	return _db_cleanup(job)


def scarica_rete_tpl(job=None):
	print "Updating network from GTFS"
	try:
		print "Loading last update time"
		last_update = VersionePaline.attuale().inizio_validita
	except:
		print "Error while loading last update time, starting from scratch"
		last_update = None
	print "Suspending Giano daemons"
	dc = DaemonControl.objects.get(name=settings.MERCURY_GIANO)
	code = '0'
	msg = ''
	with sospendi_servizi():
		with dc.suspend_all_daemons():
			_db_cleanup(job)
			print("Downloading GTFS and loading network")
			try:
				parse_static.download_gtfs_and_map(last_update)
				tpl.calcola_frequenze()
			except:
				code = -1
				msg = traceback.format_exc()
	print "Updating network from GTFS: done", code, msg
	return code, msg

