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

config = {
	'allow_public_attrs': True,
	'allow_pickle': True,
}

class Command(BaseCommand):
	args = "port [daemon_name]"
	help = 'Lancia un server RPyC che permette di creare proxy client Mercury'

	def handle(self, *args, **options):
		port = int(args[0])
		print "Proxy started"
		if len(args) > 1:
			daemon = Daemon.get_process_daemon(args[1])
			daemon.set_ready()
		ThreadedServer(MercuryProxy, port=port, protocol_config=config, hostname='localhost').start()
