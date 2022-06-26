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

from django.db import models
from django.contrib.auth.models import User
from paline.models import LogCercaPercorso

"""
# TODO: Questa tabella era presente sul vecchio server web, nel db 'mobile'.
#       Deve essere ricreata nel nuovo server db

class StazioneRfi(models.Model):
	id_palina = models.IntegerField(primary_key=True)
	nome_stazione = models.CharField(max_length=30)
	codice_rfi_stazione = models.CharField(max_length=40)
	
	class Meta:
		db_table = u'stazioni_rfi'	
"""

# Preferiti
class IndirizzoPreferito(models.Model):
	user = models.ForeignKey(User)
	nome = models.CharField(max_length=63)
	indirizzo = models.CharField(max_length=127)
	luogo = models.CharField(max_length=63)

	def __unicode__(self):
		return self.nome
	
	def indirizzo_composito(self):
		if self.luogo == '':
			return self.indirizzo
		return u"%s, %s" % (self.indirizzo, self.luogo)