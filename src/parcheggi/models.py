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
from gis import models as gis
import datetime
from risorse import models as risorse

try:
	AUTORIMESSE = risorse.TipoRisorsa.objects.get(nome='Autorimesse').pk
	PARCHEGGI = risorse.TipoRisorsa.objects.get(nome='Parcheggi di scambio').pk
except Exception:
	AUTORIMESSE = -1
	PARCHEGGI = -1

@risorse.registra_modello_risorsa
class Autorimessa(risorse.Risorsa):
	GeoModel = gis.Punto
	tipo_auto = 'Autorimesse'
	indirizzo = models.CharField(max_length=255)
	telefono = models.CharField(max_length=100)
	icon_auto = 'parcheggi.gif'
	icon_size_auto = (16, 16)
	
	def __unicode__(self):
		return self.nome_luogo
	
	def descrizione(self):
		return """
			<b>Indirizzo</b>: %(indirizzo)s<br />
			<b>Tel.</b>: %(telefono)s<br />
		""" % {
			'indirizzo': self.indirizzo,
			'telefono': self.telefono,
		}
	
	class Meta:
		verbose_name = u'Autorimessa'
		verbose_name_plural = u'Autorimesse'

@risorse.registra_modello_risorsa
class ParcheggioScambio(risorse.Risorsa):
	GeoModel = gis.Punto
	tipo_auto = 'Parcheggi di scambio'
	indirizzo = models.CharField(max_length=255)
	posti = models.IntegerField()
	icon_auto = 'parcheggi.gif'
	icon_size_auto = (16, 16)
	
	def __unicode__(self):
		return self.nome_luogo
	
	def descrizione(self):
		return """
			<b>Indirizzo</b>: %(indirizzo)s<br />
			<b>Posti</b>: %(posti)s<br />
		""" % {
			'indirizzo': self.indirizzo,
			'posti': self.posti,
		}
	
	class Meta:
		verbose_name = u'Parcheggio di scambio'
		verbose_name_plural = u'Parcheggi di scambio'
		


class Parcheggio(models.Model):
	id_parcheggio = models.IntegerField(primary_key=True)
	nome = models.CharField(max_length=100)
	posti_disponibili_non_abbonati = models.IntegerField()
	posti_disponibili_abbonati = models.IntegerField()
	posti_totali = models.IntegerField()
	ultimo_aggiornamento = models.DateTimeField()
	x = models.FloatField()
	y = models.FloatField()
	pubblicato = models.BooleanField()
	fuori_servizio = models.BooleanField()
	
	def valido(self):
		interval = datetime.timedelta(minutes=10)
		return self.ultimo_aggiornamento + interval > datetime.datetime.now()
	
	class Meta:
		db_table = u'parcheggi'
		verbose_name_plural = u'Parcheggi'		
