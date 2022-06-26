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

from copy import copy, deepcopy
from django.http import HttpResponseRedirect
from django.db.models import Q
from django import forms
from django.db.models import DateTimeField
import time, datetime
import exceptions
import math
from paline import geomath
from utils import datetime2time
from django.contrib.gis.geos import Point
from pprint import pprint

def testlist(list, el, value=None):
	return el in list and list[el] == value

def getlist(list, el, default):
	return list[el] if el in list else default	

class ItemException(Exception):
	pass

class Crud(object):
	def __init__(
		self,
		fields,
		deletable=False,
		items_per_page=12,
		queryset=None,
		validator=None,
		creator=None,
		name='',
		name_plural='',
		gender='N',
	):
		"""
		fields: list of pairs (field_name, properties)
			field_name: can be either the name of a field of the model, or anything else
				in the latter case, a callback must be used in order to display a value
			properties: dictionary with the following keys:
				long_name (default: field_name)
				type: one of string, date, time, bool, choice, address, button
				sortable: if defined, list can be sorted by field. If field is in model,
					sortable must be True in order to enable sorting.
					If field is a foreign key, sortable must be the name of the field of
					the related model.
				searchable: if defined, list can be searched by field. If field is in model,
					searchable must be True in order to enable searching.
					If field is a foreign key, searchable must be the name of the field of
					the related model.
				range_searchable: it has the same meaning of searchable, but allows to
					perform range queries
				callback: if defined, a function used to display results;
					it gets the object to be displayied as a parameter
				editable: boolean, defaults False
				newable: boolean, defaults editable
				default: optional default value
				choices: if edit-type is a choice, callback taking pk and returning dict
					{choice_name: choice_value}; for new objects, -1 is passed for pk,
				edit-mandatory: if True, element is mandatory
				icon: if type is 'button', the (relative/absolute) URI of an icon
				subfields: for multiple fields, list of subfields
					if type is 'address': (address, geom)
				help: optional help string explaining the meaning of the field
		queryset: if not None, the queryset where items will be looked for.
			At least one of model_class, queryset must be defined.
		validator: if not None, a callback used to validate an object before saving.
			Must return either {'status': 'OK'} or
			{'status': 'ERROR', 'error': error description, 'error-fields': list of field id's}
		creator: if not None, a callback used to create objects. Receives a dictionary of pairs
			(id, value). Must return either {'status': 'OK', 'pk': pk} or
			{'status': 'ERROR', 'error': error description, 'error-fields': list of field id's},
		name: human-intelligible name of queryset objects,
		name_plural: plural of name,
		gender: gender of name, either 'M', 'F' or 'N' (if it makes sense)		

		return: either a string or a django.http.HttpResponse object.
			Client should test whether isinstance(returned_object, HttpResponse).
			If True, it should just return returned_object.
			If False, it should embed returned_object somewhere in template.
			
		Notice: form ModelForm doc, please refer to:
			http://docs.djangoproject.com/en/dev/topics/forms/modelforms/#topics-forms-modelforms
		"""
		object.__init__(self)
		self.queryset = queryset
		self.opts = self.queryset.model._meta
		self.fields = fields
		self.fields_dict = {}
		for f in fields:
			self.fields_dict[f[0]] = f[1]
		self.deletable = deletable
		self.ipp = items_per_page
		self.validator = validator
		self.creator = creator
		self.name = name
		self.name_plural = name_plural if name_plural is not None else name
		self.gender = gender
		
	def _addParams(self, newparam, oldparam, removeparam=[]):
		param = deepcopy(newparam)
		for p in oldparam:
			if p not in param:
				param[p] = oldparam[p]
		for p in removeparam:
			if p in param:
				del param[p]
		return u"?%s" % u"&".join([u"%s=%s" % (k, param[k]) for k in param])
	
	def update_model(self, request, get, form):
		cd = form.cleaned_data
		o = self.queryset.get(pk=get['pk'])
		for k in cd:
			setattr(o, k, cd[k])
		o.save()
		return HttpResponseRedirect(self._addParams({}, get, ['update', 'pk']))

	def save_model(self, request, get, form):
		cd = form.cleaned_data
		o = self.mc(**cd)
		o.save()
		return HttpResponseRedirect(self._addParams({}, get, ['update', 'pk']))

	def delete_model(self, request, get):
		self.queryset.get(pk=get['delete']).delete()
		return HttpResponseRedirect(self._addParams({}, get, ['delete']))
			
	def _is_datetime(self, field):
		return field[1]['range_searchable'] == True and isinstance(self.opts.get_field(field[0]), DateTimeField)
	
	def _parse(self, text, field):
		if self._is_datetime(field):
			try:
				return datetime.datetime(*(time.strptime(text, '%d/%m/%Y %H:%M')[0:6]))
			except exceptions.ValueError:
				return None
		return text	
	
	def _data_item(self, r):
		row = []
		for f in self.fields:
			type = getlist(f[1], 'type', 'string')
			value = None
			if 'callback' in f[1]:
				value = f[1]['callback'](r)
			elif type == 'choice':
				value = f[1]['choices'](f[0])[getattr(r, f[0])]
			elif type == 'string':
				value = getattr(r, f[0])
				if value is not None:
					value = unicode(value)
				else:
					value = '-'
			elif type == 'date':
				value = getattr(r, f[0])
				value = value.strftime('%d/%m/%Y') if value is not None else '' 
			elif type == 'time':
				value = getattr(r, f[0])
				value = value.strftime('%H:%M') if value is not None else ''
			elif type == 'bool':
				value = getattr(r, f[0])
			elif type == 'address':
				subfields = getlist(f[1], 'subfields', ['address', 'geom'])
				geom = getattr(r, subfields[1])
				x, y = geom
				lng, lat = geomath.gbfe_to_wgs84(x, y)
				value = {
					'address': getattr(r, subfields[0]),
					'lng': lng,
					'lat': lat,
				}
			if value is not None:
				row.append({
					'id': f[0],
					'value': value,
				})
		return [r.pk, row]
	
	def _get_item_to_set(self, name, type, value):
		"""
		Return (value, multi)
		
		If multi is True, value is a dict {name: value}
		"""
		if type == 'date':
			if values == '':
				return None, False
			else:
				try:
					return datetime.datetime.strptime(value, '%d/%m/%Y'), False
				except Exception, e:
					raise ItemException('Data non valida')
		elif type == 'time':
			try:
				return datetime2time(datetime.datetime.strptime(value, '%H:%M'))
			except Exception, e:
				raise ItemException('Ora non valida')
		elif type == 'address':
			f = self.fields_dict[name]
			subfields = getlist(f, 'subfields', ['address', 'geom'])
			x, y = geomath.wgs84_to_gbfe(float(value['lng']), float(value['lat']))
			p = Point(x, y, srid=3004)
			return ({
				subfields[0]: value['address'],
				subfields[1]: p,
			}, True)	
		else:
			return value, False
				
	def list(self, page, search_string, sort):		
		"""
		Return queryset data
		
		page: int, requested page number
		search_string: '', or a search string
		sort: '', or 'id' (asc) or '-id' (desc)
		
		Return a structure like this:
		{
			'page': int,
			'next': boolean,
			'prev': boolean,
			'page_max': int,
			'searchable': boolean,
			'newable': boolean,
			'name': string,
			'name-plural': string,
			'gender': 'M', 'F' or 'N',
			'headers': [{
				'id': column id,
				'name': column name (as it appears in table header),
				'sortable': boolean,
				'sorted': '', '-' or '+',
				'type': one of '', 'string', 'choice', 'date',
				'edit': boolean,
				'new': boolean,
				'button-image': string of (generic) button image, or '' if column will not contain buttons,
				'delete-button': boolean,
				'edit-button': boolean,
			}],
			'data': [[ # one pair for each row
				pk,
				[{ # one item for each data column (not buttons, etc.)
					'id': column id,
					'value': value as string,
				]]
			)]
		}
		"""
		# prepare queryset
		q = self.queryset
		# perform simple search
		if 'search_string' != '':
			for word in search_string.split():
				qtot = None
				for f in self.fields:
					search_field = getlist(f[1], 'searchable', False)
					if search_field != False:
						search_field = "%s%s" % (f[0], "" if search_field == True else "__" + search_field)
						qcond = Q(**{"%s__istartswith" % search_field: word})
						if qtot is None:
							qtot = qcond
						else:
							qtot = qtot | qcond
				q = q.filter(qtot)
		# perform sorting
		if sort != '':
			q = q.order_by(sort) #TODO: sortsub???
		# paginate		
		qlen = len(q)
		pmax = max(1, int(math.ceil(float(qlen)/self.ipp)))
		if page < 1:
			page = 1
		if page > pmax:
			page = pmax
		q = q[(page - 1) * self.ipp : page * self.ipp]			
		# table headers
		searchable = False
		editable = False
		newable = False
		headers = []
		for f in self.fields:
			edit = getlist(f[1], 'editable', False)
			newt = getlist(f[1], 'newable', edit)
			header = {
				'id': f[0],
				'name': getlist(f[1], 'long_name', f[0]),
				'sortable': getlist(f[1], 'sortable', False),
				'sorted': '',
				'type': getlist(f[1], 'type', 'string'),
				'edit': edit,
				'new': newt,
				'button-image': getlist(f[1], 'icon', ''),
				'delete-button': False,
				'edit-button': False,
				'default': getlist(f[1], 'default', None),
				'help': getlist(f[1], 'help', None),
			}
			if getlist(f[1], 'searchable', False):
				searchable = True		
			if edit:
				editable = True
			if newt:
				newable = True	
			if sort == f[0]:
				header['sorted'] = '+'
			elif sort == '-%s' % f[0]:
				header['sorted'] = '-'
			headers.append(header)
		if editable:
			headers.append({
				'id': 'edit',
				'name': 'Modifica',
				'sortable': False,
				'sorted': '',
				'edit': '',
				'new': '',
				'button-image': '',
				'delete-button': False,
				'edit-button': True,
				'default': None,
				'help': None,
			})
		if self.deletable:
			headers.append({
				'id': 'delete',
				'name': 'Elimina',
				'sortable': False,
				'sorted': '',
				'edit': '',
				'new': '',
				'button-image': '',
				'delete-button': True,
				'edit-button': False,
				'default': None,
				'help': None,
			})
				
		# data
		rows = []
		for r in q:
			rows.append(self._data_item(r))

		out = {
			'page': page,
			'next': page * self.ipp < qlen,
			'prev': page > 1,
			'page_max': pmax,
			'searchable': searchable,
			'newable': newable and self.creator is not None,
			'headers': headers,
			'name': self.name,
			'name-plural': self.name_plural,
			'gender': self.gender,
			'data': rows,
		}
		return out
	
	def list_item(self, pk):
		o = self.queryset.get(pk=pk)
		return {
			'status': 'OK',
			'pk': pk,
			'data': self._data_item(o),
		}
		
			
	def edit(self, pk, values):
		"""
		In case of success, return: {
			'status': 'OK',
			'data': data, as an item of the 'data' list of list,
		}
		
		In case of problems, return: {
			'status': 'ERROR',
			'error': string,
			'error-fields': [field_id's],
		}
		"""
		o = self.queryset.get(pk=pk)
		mandatory = []
		error = ''
		error_fields = []
		for k in values:
			if getlist(self.fields_dict[k], 'edit-mandatory', False) and values[k] == '':
				mandatory.append(k)
			t = getlist(self.fields_dict[k], 'type', 'string')
			try:
				value, multiple = self._get_item_to_set(k, t, values[k])
				if multiple:
					for subk in value:
						setattr(o, subk, value[subk])
				else:
					setattr(o, k, value)
			except ItemException as ie:
				error = unicode(ie)
				error_fields.append(k)
		if len(mandatory) > 0:
			error = 'Riempi i campi obbligatori'
			error_fields.extend(mandatory)
		
		if len(error_fields) > 0:
			if len(error_fields) > 1 and len(error_fields) > len(mandatory):
				error = 'Correggi gli errori'
			return {
				'status': 'ERROR',
				'error': error,
				'error-fields': error_fields,
			}

		if self.validator is not None:
			v = self.validator(o)
			if v['stauts'] == 'ERROR':
				return v
			
		o.save()
		return {
			'status': 'OK',
			'data': self._data_item(o),
		}
		
	def create(self, values):
		"""
		In case of success, return: {
			'status': 'OK',
			'data': data, as an item of the 'data' list of list,
		}
		
		In case of problems, return: {
			'status': 'ERROR',
			'error': string,
			'error-fields': [field_id's],
		}
		"""
		mandatory = []
		error = ''
		error_fields = []
		out_values = {}
		for k in values:
			if getlist(self.fields_dict[k], 'edit-mandatory', False) and values[k] == '':
				mandatory.append(k)
			t = getlist(self.fields_dict[k], 'type', 'string')
			try:
				value, multiple = self._get_item_to_set(k, t, values[k])
				if multiple:
					for subk in value:
						out_values[subk] = value[subk]
				else:
					out_values[k] = value
			except ItemException as ie:
				error = unicode(ie)
				error_fields.append(k)
		if len(mandatory) > 0:
			error = 'Riempi i campi obbligatori'
			error_fields.extend(mandatory)
		
		if len(error_fields) > 0:
			if len(error_fields) > 1 and len(error_fields) > len(mandatory):
				error = 'Correggi gli errori'
			return {
				'status': 'ERROR',
				'error': error,
				'error-fields': error_fields,
			}
		pprint(out_values)
		v = self.creator(out_values)
		if v['status'] == 'ERROR':
			return v
		o = self.queryset.get(pk=v['pk'])
		return {
			'status': 'OK',
			'pk': v['pk'],
			'data': self._data_item(o),
		}

	def delete(self, pk):
		self.queryset.get(pk=pk).delete()
		return 'OK'
	
	def get_choices(self, pk, field_id):
		choices = self.fields_dict[field_id]['choices'](pk)
		if pk != -1:
			o = self.queryset.get(pk=pk)
			return {
				'value': getattr(o, field_id),
				'choices': choices,
			}
		else:
			return {
				'value': choices.iterkeys().next(),
				'choices': choices
			}

	def __call__(self, action, crud_args):
		if action == 'list':
			return self.list(**crud_args)
		elif action == 'delete':
			return self.delete(**crud_args)
		elif action == 'edit':
			return self.edit(**crud_args)
		elif action == 'list_item':
			return self.list_item(**crud_args)		
		elif action == 'create':
			return self.create(**crud_args)			
		elif action == 'get_choices':
			return self.get_choices(**crud_args)
		
def crudSimpleCreator(model, **extra_fields):
	"""
	Return a simple creator.
	
	The creator creates an object of model model with values specified in values and extra_fields
	"""
	def f(values):
		c = copy(values)
		c.update(extra_fields)
		o = model(**c)
		o.save()
		return {
			'status': 'OK',
			'pk': o.pk
		}
	return f

def list2choices(l):
	def f(dummy):
		return dict(l)
	return f
		