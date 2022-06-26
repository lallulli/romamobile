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

TOKEN_APP_LENGTH = 42


class ServiziUser(User):
	secret = models.CharField(max_length=127, unique=True, db_index=True)
	daily_credits = models.IntegerField(null=True, blank=True, default=None)


class ServiziUserDailyCredits(models.Model):
	user = models.ForeignKey(ServiziUser)
	date = models.DateField(db_index=True)
	used_credits = models.IntegerField(default=0)

	def __unicode__(self):
		return u"[{}] {}: {}".format(self.date, self.user, self.used_credits)

	
class MuoversiaromaUser(User):
	user_id = models.CharField(max_length=20, unique=True, db_index=True)


class LocalizzazioneUser(User):
	restype = models.IntegerField(db_index=True)
	resid = models.CharField(max_length=40, db_index=True)


class LogAutenticazioneServizi(models.Model):
	orario = models.DateTimeField(db_index=True)
	user = models.ForeignKey(ServiziUser)
	token = models.CharField(max_length=40, db_index=True)
	id_utente_interno = models.CharField(max_length=128)
	
	def __unicode__(self):
		return "%s, %s" % (self.orario, self.user)


class TokenApp(models.Model):
	token_app = models.CharField(max_length=TOKEN_APP_LENGTH, db_index=True)
	user = models.ForeignKey(User)
	ultimo_accesso = models.DateTimeField(db_index=True)


class Telefono(models.Model):
	user = models.ForeignKey(User)
	numero = models.CharField(max_length=31)


class Sottosito(models.Model):
	id_sottosito = models.IntegerField(db_index=True)
	nome = models.CharField(max_length=31)
	url_login = models.CharField(max_length=127)
	url_logout = models.CharField(max_length=127)
	
	def __unicode__(self):
		return self.nome
	
	class Meta:
		verbose_name_plural = 'Sottositi'
		
