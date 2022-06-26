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
from paline.caricamento_rete.caricamento_rete import carica_rete, carica_rete_auto, scarica_rete

class Command(BaseCommand):
	args = """
		email: send email after loading
		no_load: skip loading (incompatible with email)
		no_validate: skip validation (incompatible with email)
		download: download network from muoversiaroma server
	"""

	help = 'TODO'

	def handle(self, *args, **options):
		if 'download' in args:
			scarica_rete()
			carica_rete()
		elif 'email' in args:
			carica_rete_auto()
		else:
			carica_rete('no_load' in args, 'no_validate' in args)
