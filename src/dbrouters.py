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

import settings

def get_model_database(model):
	try:
		return model.database_name
	except:
		pass
	if settings.DATABASE_APPS_MAPPING.has_key(model._meta.app_label):
		return settings.DATABASE_APPS_MAPPING[model._meta.app_label]
	return None

class DatabaseAppsRouter(object):
	"""
	A router to control all database operations on models for different
	databases.

	In case an app is not set in settings.DATABASE_APPS_MAPPING, the router
	will fallback to the `default` database.
 
	Settings example:
 
	DATABASE_APPS_MAPPING = {'app1': 'db1', 'app2': 'db2'}
	"""
 
	def db_for_read(self, model, **hints):
		""""Point all read operations to the specific database."""
		return get_model_database(model)
 
	def db_for_write(self, model, **hints):
		"""Point all write operations to the specific database."""
		return get_model_database(model)
 
	def allow_relation(self, obj1, obj2, **hints):
		"""Allow any relation between apps that use the same database."""
		db_obj1 = get_model_database(obj1)
		db_obj2 = get_model_database(obj2)
		if db_obj1 and db_obj2:
			if db_obj1 == db_obj2:
				return True
			else:
				return False
		return None
 
	def allow_syncdb(self, db, model):
		"""Make sure that apps only appear in the related database."""
		no_sync = [] #'news']
		if model._meta.app_label in no_sync:
			return False
		db_model = get_model_database(model)
		if db_model is None:
			return False
		return db_model == db
