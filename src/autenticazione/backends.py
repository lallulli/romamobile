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


from models import *
from django.contrib.auth.backends import ModelBackend

class ServiziBackend(ModelBackend):
	def authenticate(self, secret=None):
		try:
			s = ServiziUser.objects.get(secret=secret)
			return s
		except ServiziUser.DoesNotExist:
			return None

	def get_user(self, user_id):
		try:
			return ServiziUser.objects.get(pk=user_id)
		except ServiziUser.DoesNotExist:
			return None
	
class MuoversiaromaBackend(ModelBackend):
	def authenticate(self, user_data):
		try:
			u = MuoversiaromaUser.objects.get(user_id=user_data['UserName'])
			u.first_name = user_data['Nome']
			u.last_name = user_data['Cognome']
			u.email = user_data['Email']
			u.save()			
		except MuoversiaromaUser.DoesNotExist:
			user_id = user_data['UserName']
			username = user_id
			n = MuoversiaromaUser.objects.filter(username=username).count()
			i = 0
			while n > 0:
				i += 1
				username = user_id + str(i)
				n = MuoversiaromaUser.objects.filter(username=username).count()
			u = MuoversiaromaUser(
				username=username,
				user_id=user_id,
				first_name=user_data['Nome'],
				last_name=user_data['Cognome'],
				email=user_data['Email'],
			)
			u.save()
		return u
	
	def get_user(self, user_id):
		try:
			return MuoversiaromaUser.objects.get(pk=user_id)
		except MuoversiaromaUser.DoesNotExist:
			return None

	
class LocalizzazioneBackend(ModelBackend):
	def authenticate(self, restype, resid):
		try:
			u = LocalizzazioneUser.objects.get(restype=restype, resid=resid)
			return u
		except LocalizzazioneUser.DoesNotExist:
			return None
	
	def get_user(self, user_id):
		try:
			return LocalizzazioneUser.objects.get(pk=user_id)
		except LocalizzazioneUser.DoesNotExist:
			return None

