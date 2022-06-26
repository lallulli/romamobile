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
from datetime import date, time, datetime, timedelta
from carpooling.models import *


class Command(BaseCommand):
	args = ""
	help = """
		Ripete i passaggi offerti nella settimana attuale per la prossima settimana.
		
		Lo script deve essere lanciato il venerdì notte (ad esempio alle 00:00 di venerdì), e considera i passaggi
		offerti in una settimana, che ha termine il giorno successivo (es. sabato, 00:00). 
	"""
	def handle(self, *args, **options):
		jobs.ripeti()
