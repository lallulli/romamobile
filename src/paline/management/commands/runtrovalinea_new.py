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

from django.core.management.base import BaseCommand, CommandError
import settings
from mercury.models import *
from datetime import date, time, datetime, timedelta
from paline.trovalinea import TrovalineaFactory

config = {
	'allow_public_attrs': True,
}

class Command(BaseCommand):
	args = ""
	help = 'Nuovo trovalinea'

	def handle(self, *args, **options):
		"""
		Usage: python manage.py runtrovalinea_new [arguments] [datetime]

		Arguments may be the following:

		mini: load reduced version of network
		cpd: load graph to enable route planner
		tr: get bus data from public transport operators, in real-time
		shell: open shell
		special: (deprecated)
		download: download real-time data from muovi.roma.it public server

		datetime is the timestamp that determines network validity
		"""
		commands = ['mini', 'cpd', 'tr', 'shell', 'special', 'download', 'tr_percorsi', 'in_docker']
		dt = None
		for k in args:
			if not k in commands:
				dt = k.replace('T', ' ')

		name = settings.MERCURY_CL
		if 'cpd' in args:
			name = settings.MERCURY_CPD
		if 'tr' in args:
			name = settings.MERCURY_GIANO
		if 'tr_percorsi' in args:
			name = settings.MERCURY_GIANO_PERCORSI

		print "Cerco demone " + name
		giano = PeerType.objects.get(name=name)
		giano_daemon = Daemon.get_process_daemon(name, 'in_docker' in commands)
		print("Demone trovato")

		Trovalinea = TrovalineaFactory(
			'mini' in args,
			'cpd' in args,
			'tr' in args,
			'shell' in args,
			'special' in args,
			dt,
			'download' in args,
			daemon=giano_daemon,
			tempo_reale_percorsi='tr_percorsi' in args,
		)

		m = Mercury(giano, Trovalinea, daemon=giano_daemon, watchdog_daemon=giano_daemon)
		if not 'tr' in args:
			try:
				print "Richiedo serializzazione"
				Trovalinea.rete.deserializza_dinamico_db()
				print "Serializzazione richiesta effettuata"
			except Exception, e:
				print "Serializzazione richiesta fallita"
		
		giano_daemon.set_ready()

