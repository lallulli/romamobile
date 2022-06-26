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
from autenticazione.models import LogAutenticazioneServizi
from log_servizi.models import Invocazione
from paline.models import Disservizio, DisservizioPalinaElettronica as DPE
from datetime import datetime, timedelta, date
from django.db import connections, transaction
from servizi.utils import mysql2date, datetime2date, date2mysql
from paline.jobs import *

class Command(BaseCommand):
	args = '[<data>] [deleteonly]'
	help = 'Aggrega i dati statistici per ora'
	
	
	def handle(self, *args, **options):
		if len(args) == 0:
			data = datetime2date(datetime.now() - timedelta(days=30))
		else:
			data = mysql2date(args[0])
				
		print data
				
		aggrega_stat(data)
	

