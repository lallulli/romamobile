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


import uuid
import hashlib
from django.db.models import Max, Min, Q
from django.contrib.auth.models import User, Group
from django import forms
from django.utils.safestring import mark_safe
from django.utils.encoding import force_unicode
from django.utils.html import escape, conditional_escape
from itertools import chain
from django.utils.translation import ugettext_lazy as _
from django.template.response import TemplateResponse
from django.template import Template, Context
from django.template.loader import get_template, render_to_string
from django.template.defaultfilters import time as timefilter
from django.template.loaders.app_directories import Loader as TemplateLoader
from django.http import HttpResponseRedirect
from django.forms.widgets import CheckboxInput
from django.core.mail import send_mail, EmailMultiAlternatives
from email.mime.image import MIMEImage
from datetime import datetime, date, time, timedelta
from django.db import transaction as dbtrans
from contextlib import contextmanager
import settings
import os, os.path, shutil
import tempfile
import threading, Queue
import cPickle as pickle
import re
from copy import deepcopy
from base64 import b64encode, b64decode
from zlib import compress, decompress
from django.db import models
from django import db
from django.utils.encoding import force_unicode
from django.contrib.contenttypes import models as contenttypes
import email.utils as eut
import traceback
import string
import random
import zipfile


def service_reply(f):
	def g(*args):
		ret = {}
		ret['id_richiesta'] = hashlib.md5(uuid.uuid1().hex).hexdigest()
		ret['risposta'] = f(*args)
		return ret
	# Make g a well-behaved decorator
	g.__name__ = f.__name__
	g.__doc__ = f.__doc__
	g.__dict__.update(f.__dict__)
	return g


def oggetto_con_max(queryset, field):
	"""Restituisce l'oggetto avente valore massimo per il campo specificato"""
	d = queryset.aggregate(Max(field))
	return queryset.get(**{field: d[field + '__max']})


def oggetto_con_min(queryset, field):
	"""Restituisce l'oggetto avente valore minimo per il campo specificato"""
	d = queryset.aggregate(Min(field))
	return queryset.get(**{field: d[field + '__min']})


def dict_cursor(cursor):
	cols = [x[0] for x in cursor.description]
	n = len(cols)
	for raw in cursor:
		yield dict([(cols[i], raw[i]) for i in range(0, n)])


def project(obj, *attributes):
	"""
	Return a dictionary with the projected attributes
	"""
	d = {}
	for a in attributes:
		attr = getattr(obj, a)
		d[a] = attr if attr is not None else ''
	return d


def sec2min(sec):
	return int(round(sec / 60.0))


def datetime2mysql(dt):
	return dt.strftime("%Y-%m-%d %H:%M:%S")


def datetime2compact(dt):
	return dt.strftime("%Y%m%d%H%M%S")


def date2mysql(dt):
	return dt.strftime("%Y-%m-%d")


def mysql2date(s):
	return datetime2date(datetime.strptime(s, '%Y-%m-%d'))


def mysql2datetime(s):
	return datetime.strptime(s, '%Y-%m-%d %H:%M:%S')


def date2datetime(dt):
	return datetime(year=dt.year, month=dt.month, day=dt.day)


def datetime2date(dt):
	return date(year=dt.year, month=dt.month, day=dt.day)


def datetime2time(dt):
	return time(hour=dt.hour, minute=dt.minute, second=dt.second, microsecond=dt.microsecond)


def dateandtime2datetime(d, t):
	return datetime(year=d.year, month=d.month, day=d.day, hour=t.hour, minute=t.minute, second=t.second)


def xmlrpc2datetime(dt):
	return datetime.strptime(str(dt), "%Y%m%dT%H:%M:%S")


def unmarshal_datetime(dt):
	if dt is None:
		return None
	return mysql2datetime(datetime2mysql(dt))


def datetime2unixtime(dt):
	return (dt - datetime(1970, 1, 1)).total_seconds()


def model2contenttype(model):
	return contenttypes.ContentType.objects.get_for_model(model).pk


def contenttype2model(pk):
	return contenttypes.ContentType.objects.get(pk=pk).model_class()


def parse_http_datetime(text):
	return datetime(*eut.parsedate(text)[:6])


def group_required(group_names=[], error_response=None):
	"""
	Richiede l'appartenenza a un gruppo.
	
	Se group_names è vuoto, richiede semplicemente il login
	"""
	if type(group_names) not in [list, tuple, set]:
		group_names = [group_names] 
	def wrap(view_func):
		def in_group(request, *args, **kwargs):
			if request.user.is_authenticated():
				if len(group_names) == 0 or len(request.user.groups.filter(name__in=group_names)) > 0:
					return view_func(request, *args, **kwargs)
			if error_response is not None:
				return error_response
			return HttpResponseRedirect('http://login.muoversiaroma.it/GestioneAccount.aspx?IdSito=%d' % settings.ID_SITO)
			#return TemplateResponse(request, 'login_richiesto.html', {'id_sito': settings.ID_SITO})
		return in_group
	return wrap

def group_excluded(group_names, error_response=None):
	if type(group_names) not in [list, tuple, set]:
		group_names = [group_names] 	
	def wrap(view_func):
		def in_group(request, *args, **kwargs):
			if request.user.is_authenticated():
				if len(request.user.groups.filter(name__in=group_names)) > 0:
					if error_response is not None:
						return error_response
					return HttpResponseRedirect('http://login.muoversiaroma.it/GestioneAccount.aspx?IdSito=%d' % settings.ID_SITO)
					#return TemplateResponse(request, 'login_richiesto.html', {'id_sito': settings.ID_SITO})
			return view_func(request, *args, **kwargs)
		return in_group
	return wrap

def populate_form(request, form, **values):
	ks = values.keys()
	for k in ks:
		if k in request.GET:
			return form(request.GET)
	try:
		if k[0] in request.history_future: 
			return form(initial=request.history_future)
	except Exception:
		pass
	return form(initial=values)


class StyledSelect(forms.Select):
	def render_option(self, selected_choices, option_value, option_label, option_style=None):
		option_value = force_unicode(option_value)
		selected_html = (option_value in selected_choices) and u' selected="selected"' or ''
		style = "" if option_style is None else (' class = "%s"' % option_style) 
		return u'<option value="%s"%s%s>%s</option>' % (
			escape(option_value), selected_html, style,
			conditional_escape(force_unicode(option_label)))

	def render_options(self, choices, selected_choices):
		# Normalize to strings.
		selected_choices = set([force_unicode(v) for v in selected_choices])
		output = []
		for k in chain(self.choices, choices):
			option_value, option_label = k[:2]
			option_style = None
			if len(k) > 2:
				option_style = k[2]
			if isinstance(option_label, (list, tuple)):
				output.append(u'<optgroup label="%s">' % escape(force_unicode(option_value)))
				for option in option_label:
					output.append(self.render_option(selected_choices, *option))
				output.append(u'</optgroup>')
			else:
				output.append(self.render_option(selected_choices, option_value, option_label, option_style))
		return u'\n'.join(output)

def aggiungi_banda(valori):
	i = 0
	for a in valori:
		a['banda'] = i
		i += 1
		if i == 3:
			i = 1

# funzione internazionalizzata per trasformare un codice giorno settimana nella corrispondente stringa
def giorni_settimana(breve=False, capital=False):
	if breve and capital:
		return [_(u"Lu"), _(u"Ma"), _(u"Me"), _(u"Gi"), _(u"Ve"), _(u"Sa"), _(u"Do")]
	elif breve and not capital:
		return [_(u"lu"), _(u"ma"), _(u"me"), _(u"gi"), _(u"ve"), _(u"sa"), _(u"do")]
	elif not breve and capital:
		return [_(u"Lunedì"), _(u"Martedì"), _(u"Mercoledì"), _(u"Giovedì"), _(u"Venerdì"), _(u"Sabato"), _(u"Domenica")]
	else:
		return [_(u"lunedì"), _(u"martedì"), _(u"mercoledì"), _(u"giovedì"), _(u"venerdì"), _(u"sabato"), _(u"domenica")]

def dow2string(codice, breve=False):
	giorni = giorni_settimana(breve)
	giorni = [giorni[-1]] + giorni[:-1]
	return giorni[codice - 1]

def weekday2string(codice, breve=False):
	return giorni_settimana(breve)[codice]

def prossima_data(wd):
	"""
	Restituisce la prima data utile dopo oggi con giorno della settimana wd
	"""
	wd = wd % 7
	td = timedelta(days=1)
	d = datetime.now() + td
	while d.weekday() != wd:
		d += td
	return datetime2date(d)
	

def ora_breve(ora):
	return timefilter(ora, _("H:i"))

def str2time(ora):
	# prende l'ora in formato hh:mm e restituisce un oggetto time
	timesplit = re.split(':', ora)
	return time( int(timesplit[0]), int(timesplit[1]))

def messaggio(request, msg):
	return TemplateResponse(request, 'messaggio.html', {'msg': msg})

def modifica_url_con_storia(request, url, offset=1):
	url = url.split('#')
	pre = url[0]
	post = "#" + url[1] if len(url) > 1 else ''
	session = ''
	if request.does_not_accept_cookies:
		session = '&amp;%s=%s' % (settings.SESSION_COOKIE_NAME, request.session.session_key)
	url = pre + '%snav=%d%s' % (
		('&amp;' if '?' in pre else '?'),
		(len(request.session['history']) - 1 + offset),
		session,
	) + post
	return url

def re_sub(rexp, find, func):
	"""
	Cerca la l'espressione regolare e sostituisce tutte le occorrenze valutando una funzione
	
	rexp: espressione regolare con un raggruppamento
	find: stringa di ricerca
	func: funzione ad un parametro, riceve l'occorrenza trovata e restituisce la stringa
	      da sostituire
	"""
	r = re.compile(rexp)
	out = ""
	i = 0
	for m in r.finditer(find):
		out += find[i:m.start()] + func(m.group(1))
		i = m.end()
	out += find[i:]
	return out


def modifica_url_con_storia_link(request, st, offset=1):
	def sostitutore(s):
		return modifica_url_con_storia(request, s, offset)
	return re_sub('\[hist\]([^[]*)\[/hist\]', st, sostitutore)


def hist_redirect(request, url, offset=0, msg=None):
	if msg is not None:
		request.session['redirect_message'] = msg
	return HttpResponseRedirect(modifica_url_con_storia(request, url, offset))


class AtacMobileForm(forms.Form):
	def is_valid(self):
		ret = forms.Form.is_valid(self)
		for f in self.errors:
			self.fields[f].widget.attrs.update({'class': 'hlform'})
		return ret
	
	def set_error(self, fields):
		if type(fields) != list:
			field = [fields]
		for f in fields:
			self.fields[f].widget.attrs.update({'class': 'hlform'})


class BrRadioFieldRenderer(forms.widgets.RadioFieldRenderer):
	def render(self):
		"""Outputs a <ul> for this set of radio fields."""
		return mark_safe(u'\n'.join([u'%s<br />'% force_unicode(w) for w in self]))
	
class BrCheckboxSelectMultiple(forms.CheckboxSelectMultiple):
	def render(self, name, value, attrs=None, choices=()):
		if value is None: value = []
		has_id = attrs and 'id' in attrs
		final_attrs = self.build_attrs(attrs, name=name)
		output = []
		# Normalize to strings
		str_values = set([force_unicode(v) for v in value])
		for i, (option_value, option_label) in enumerate(chain(self.choices, choices)):
			# If an ID attribute was given, add a numeric index as a suffix,
			# so that the checkboxes don't all have the same ID attribute.
			if has_id:
				final_attrs = dict(final_attrs, id='%s_%s' % (attrs['id'], i))
				label_for = u' for="%s"' % final_attrs['id']
			else:
				label_for = ''

			cb = CheckboxInput(final_attrs, check_test=lambda value: value in str_values)
			option_value = force_unicode(option_value)
			rendered_cb = cb.render(name, option_value)
			option_label = conditional_escape(force_unicode(option_label))
			output.append(u'<label%s>%s %s</label>' % (label_for, rendered_cb, option_label))
		return mark_safe(u'<br />\n'.join(output))
	
class BrRadioFieldRenderer(forms.widgets.RadioFieldRenderer):
	def render(self):
		"""Outputs a <ul> for this set of radio fields."""
		return mark_safe(u'\n'.join([u'%s<br />'% force_unicode(w) for w in self]))
	
class BrRadioSelect(forms.widgets.RadioSelect):
	renderer = BrRadioFieldRenderer


def permission_links(user, menu):
	"""
	Prepare context for a custom menu according to user permissions
	
	menu is a list of dict with the following keys:
		'url': url to be inserted in <a> tag
		'caption': menu item caption
		'groups': set of authorized user groups
		
	return a pair (redirect_url, filtered_menu).
	If redirect_url is not None, user should be redirected to that URL.
	Otherwise, filtered_menu contains menu items that user is allowed to view.
	"""
	user_groups = set([x.name for x in user.groups.all()])
	filtered_menu = [x for x in menu if len(user_groups.intersection(x['groups'])) > 0]
	return (filtered_menu[0]['url'], filtered_menu) if len(filtered_menu) == 1 else (None, filtered_menu)

@contextmanager
def transaction(actual=True, debug=False):
	if actual:
		dbtrans.enter_transaction_management()
		dbtrans.managed(True)
	try:
		yield
	except:
		if debug:
			traceback.print_exc()
		if actual:
			dbtrans.rollback()
	else:
		if actual:
			dbtrans.commit()

def _create_decorator_transaction_commit_manually(using=None):
	def deco(f):
		def g(*args, **kwargs):
			try:
				out = f(*args, **kwargs)
			except Exception as e:
				if using is not None:
					dbtrans.rollback(using=using)
				else:
					dbtrans.rollback()
				raise e
			return out
		if using is not None:
			return dbtrans.commit_manually(using=using)(g)
		return dbtrans.commit_manually(g)
	return deco

def transaction_commit_manually(*args, **kwargs):
	"""
	Improved transaction.commit_manually, that does not hide exceptions.

	If an exception occurs, rollback work and raise exception again
	"""
	# If 'using' keyword is provided, return a decorator
	if 'using' in kwargs:
		return _create_decorator_transaction_commit_manually(using=kwargs['using'])
	# If 'using' keyword is not provided, act as a decorator:
	# first argument is function to be decorated; return modified function
	f = args[0]
	deco = _create_decorator_transaction_commit_manually()
	return deco(f)


def _multisplit_ric(ss, elems):
	if len(elems) == 0:
		return ss
	ret = []
	for s in ss:
		ret.extend(s.split(elems[0]))
	return _multisplit_ric(ret, elems[1:])


def multisplit(s, elems):
	return _multisplit_ric([s], elems)


def is_int(s):
	try:
		i = int(s)
		return True
	except Exception:
		return False


def richiedi_conferma(richiesta, conferma=None, annulla=None):
	def decoratore(f):
		def g(request, *args, **kwargs):
			if 'confermato' in request.GET:
				return f(request, *args, **kwargs)
			ctx = {
				'richiesta': richiesta,
				'conferma': conferma if conferma is not None else _("Conferma"),
				'annulla': annulla if annulla is not None else _("Annulla"),
			}
			return TemplateResponse(request, 'richiedi-conferma.html', ctx)
		return g
	return decoratore


def autodiscover(name):
	"""
	Importa automaticamente i file del tipo name.py presenti nelle applicazioni
	"""
	current_path = os.path.dirname(__file__)
	path = os.path.join(current_path, '..')
	for a in settings.LOCAL_APPS:
		bw = os.path.join(path, '%s/%s.py' % (a, name))
		if os.path.isfile(bw):
			__import__("%s.%s" % (a, name))
	

# RPyC
class RPyCAllowRead(object):
	def _rpyc_getattr(self, name):
		return getattr(self, name)
	
class RPyCAllowWrite(object):
	def _rpyc_setattr(self, name, value):
		setattr(self, name, value)
		
# Multithread
class FunctionInThreadWorker(threading.Thread):
	def __init__(self, tasks, tokens):
		threading.Thread.__init__(self)
		self.tasks = tasks
		self.tokens = tokens
		
	def run(self):
		while True:
			f, args = self.tasks.get()
			f(*args[0], **args[1])
			self.tasks.task_done()
			self.tokens.put("Token")		

class FunctionInThread(object):
	def __init__(self, nmax):
		object.__init__(self)
		self.tasks = Queue.Queue()
		self.tokens = Queue.Queue()
		self.workers = []
		for i in range(nmax):
			self.tokens.put("Token")
			w = FunctionInThreadWorker(self.tasks, self.tokens)
			w.start()
			self.workers.append(w)
	
	def invoke_function(self, f, *args, **kwargs):
		self.tokens.get()
		self.tasks.put((f, (args, kwargs)))
		
# Modificatore ricorsivo per strutture
def apply_ric(struct, func):
	"""
	Applica la funzione func a tutti gli elementi atomici della struttura
	
	La struttura è un array di strutture e atomi, o un dizionario
	i cui valori sono strutture o atomi
	"""
	if hasattr(struct, 'itervalues'):
		for k in struct:
			struct[k] = apply_ric(struct[k], func)
		return struct
	if hasattr(struct, '__iter__'):
		for i in range(len(struct)):
			struct[i] = apply_ric(struct[i], func)
		return struct
	return func(struct)


def _numero_romano(p):
	s = set(['I', 'V', 'X'])
	for x in p:
		if not x in s:
			return False
	return True

def ricapitalizza(nome):
	if nome is None:
		return None
	out = []
	for p in nome.split(' '):
		o2 = []
		for q in p.split('/'):
			if len(q) > 0 and q[0] != '(' and not _numero_romano(q):
				q = q.capitalize()
			o2.append(q)
		p = '/'.join(o2)
		out.append(p)
	return ' '.join(out)


def autodump(obj):
	return pickle.loads(pickle.dumps(obj))

		
def template_to_mail(dest, template_name, ctx, process_template=False):
	"""
	Invia una mail dopo aver effettuato il rendering del template
	
	La prima riga del template contiene il mittente.
	La seconda riga contiene l'oggetto.
	Le restanti righe contengono il corpo del messaggio.
	"""
	if type(dest) != list:
		dest = [dest]
	if process_template:
		righe = render_text_template(template_name, ctx).splitlines()
	else:
		t = get_template(template_name)
		righe = t.render(Context(ctx)).splitlines()
	fr = righe[0]
	subj = righe[1]
	msg = "\n".join(righe[2:])
	send_mail(subj, msg, fr, dest, fail_silently=True)


def template_to_mail_html(dest, template_name, template_html_name, ctx, process_template=False, images=[]):
	"""
	Invia una mail multipart (testo + HTML) effettuando il rendering del template

	La prima riga del template contiene il mittente.
	La seconda riga contiene l'oggetto.
	Le restanti righe contengono il corpo del messaggio.

	Allega anche un messaggio HTML, con eventuali immagini.
	Il template HTML contiene solamente il testo dell'email
	Ogni immagine è una coppia (nome, contenuto):
	- nome è il nome dell'immagine. Nel file HTML ci si può riferire ad esso così: <img src="cid:nome_immagine.png" />
	- contenuto è il contenuto "secco" dell'immagine, ad esempio la stringa ottenuta leggendo il file immagine con read()
	"""
	if type(dest) != list:
		dest = [dest]
	if process_template:
		righe = render_text_template(template_name, ctx).splitlines()
	else:
		t = get_template(template_name)
		righe = t.render(Context(ctx)).splitlines()
	fr = righe[0]
	subj = righe[1]
	msg = "\n".join(righe[2:])
	msg_html = render_to_string(template_html_name, ctx)
	m = EmailMultiAlternatives(subj, msg, fr, dest)
	m.attach_alternative(msg_html, 'text/html')
	for i in images:
		img = MIMEImage(i[1])
		img.add_header('Content-ID', '<{}>'.format(i[0]))
		m.attach(img)
	m.send(fail_silently=True)


class PickledObject(str):
    """
    A subclass of string so it can be told whether a string is a pickled
    object or not (if the object is an instance of this class then it must
    [well, should] be a pickled one).
    
    Only really useful for passing pre-encoded values to ``default``
    with ``dbsafe_encode``, not that doing so is necessary. If you
    remove PickledObject and its references, you won't be able to pass
    in pre-encoded values anymore, but you can always just pass in the
    python objects themselves.
    
    """
    pass

def dbsafe_encode(value, compress_object=False):
    """
    We use deepcopy() here to avoid a problem with cPickle, where dumps
    can generate different character streams for same lookup value if
    they are referenced differently. 
    
    The reason this is important is because we do all of our lookups as
    simple string matches, thus the character streams must be the same
    for the lookups to work properly. See tests.py for more information.
    """
    if not compress_object:
        value = b64encode(pickle.dumps(deepcopy(value)))
    else:
        value = b64encode(compress(pickle.dumps(deepcopy(value))))
    return PickledObject(value)

def dbsafe_decode(value, compress_object=False):
    if not compress_object:
        value = pickle.loads(b64decode(value))
    else:
        value = pickle.loads(decompress(b64decode(value)))
    return value

class PickledObjectField(models.Field):
    """
    A field that will accept *any* python object and store it in the
    database. PickledObjectField will optionally compress it's values if
    declared with the keyword argument ``compress=True``.
    
    Does not actually encode and compress ``None`` objects (although you
    can still do lookups using None). This way, it is still possible to
    use the ``isnull`` lookup type correctly. Because of this, the field
    defaults to ``null=True``, as otherwise it wouldn't be able to store
    None values since they aren't pickled and encoded.
    
    """
    __metaclass__ = models.SubfieldBase
    
    def __init__(self, *args, **kwargs):
        self.compress = kwargs.pop('compress', False)
        self.protocol = kwargs.pop('protocol', 2)
        kwargs.setdefault('null', True)
        kwargs.setdefault('editable', False)
        super(PickledObjectField, self).__init__(*args, **kwargs)
    
    def get_default(self):
        """
        Returns the default value for this field.
        
        The default implementation on models.Field calls force_unicode
        on the default, which means you can't set arbitrary Python
        objects as the default. To fix this, we just return the value
        without calling force_unicode on it. Note that if you set a
        callable as a default, the field will still call it. It will
        *not* try to pickle and encode it.
        
        """
        if self.has_default():
            if callable(self.default):
                return self.default()
            return self.default
        # If the field doesn't have a default, then we punt to models.Field.
        return super(PickledObjectField, self).get_default()

    def to_python(self, value):
        """
        B64decode and unpickle the object, optionally decompressing it.
        
        If an error is raised in de-pickling and we're sure the value is
        a definite pickle, the error is allowed to propogate. If we
        aren't sure if the value is a pickle or not, then we catch the
        error and return the original value instead.
        
        """
        if value is not None:
            try:
                value = dbsafe_decode(value, self.compress)
            except:
                # If the value is a definite pickle; and an error is raised in
                # de-pickling it should be allowed to propogate.
                if isinstance(value, PickledObject):
                    raise
        return value

    def get_prep_value(self, value):
        """
        Pickle and b64encode the object, optionally compressing it.
        
        The pickling protocol is specified explicitly (by default 2),
        rather than as -1 or HIGHEST_PROTOCOL, because we don't want the
        protocol to change over time. If it did, ``exact`` and ``in``
        lookups would likely fail, since pickle would now be generating
        a different string. 
        
        """
        if value is not None and not isinstance(value, PickledObject):
            # We call force_unicode here explicitly, so that the encoded string
            # isn't rejected by the postgresql_psycopg2 backend. Alternatively,
            # we could have just registered PickledObject with the psycopg
            # marshaller (telling it to store it like it would a string), but
            # since both of these methods result in the same value being stored,
            # doing things this way is much easier.
            value = force_unicode(dbsafe_encode(value, self.compress))
        return value

    def value_to_string(self, obj):
        value = self._get_val_from_obj(obj)
        return self.get_prep_value(value)

    def get_internal_type(self): 
        return 'TextField'
    
    def get_prep_lookup(self, lookup_type, value):
        if lookup_type not in ['exact', 'isnull']:
            raise TypeError('Lookup type %s is not supported.' % lookup_type)
        return self.get_prep_value(value)


def dictfetchall(cursor):
	"Returns all rows from a cursor as a dict"
	desc = cursor.description
	return [
	  dict(zip([col[0] for col in desc], row))
	  for row in cursor.fetchall()
	]

def group_by(l, key=None, func=None):
	"""
	A partire da una lista ordinata per una chiave, estrae una lista di liste raggruppata per quella chiave 
	"""
	if len(l) == 0:
		return []
	if key is not None:
		func = lambda x: x[key]
	out = []
	old = None
	for x in l:
		new = func(x)
		if old != new:
			if old is not None:
				out.append(current)
			old = new
			current = []
		current.append(x)
	out.append(current)
	return out
		
def getdef(dict, key, default=None):
	"""
	Return dict[key], if key in dict: default, otherwise
	"""
	return dict[key] if key in dict else default

def setdef(dict, key, default):
	"""
	If key is not in dict: set dict[key] = default
	"""
	if not key in dict:
		dict[key] = default

def extend_to_child_model(parent_instance, child_model):
	"""
	Given an instance a of a model A, and a model B that extends A, create and return an instance of B extending a (since a "is a" B)
	"""
	child_instance = child_model(**{'%s_ptr_id' % type(parent_instance).__name__.lower(): parent_instance.pk})
	child_instance.__dict__.update(parent_instance.__dict__)
	child_instance.save()
	return child_instance

def dedent(s):
	"""
	Removes n levels of indentation from every line, where n is the indentation level of first non-empty line
	"""
	lines = s.splitlines()
	n = len(lines)
	j = 0
	while j < n and lines[j].strip() == '':
		j += 1
	l = lines[j]
	i = 0
	while i < len(l) and l[i] in [' ', '\t']:
		i += 1
	return '\n'.join([l[i:] for l in lines[j:]])

def save_login_params(request):
	request.session['saved_params_during_login'] = request.get_full_path()

def restore_login_params(request):
	if 'saved_params_during_login' in request.session:
		a = request.session['saved_params_during_login']
		del request.session['saved_params_during_login']
		return a
	return None

def enforce_login(f):
	def g(request, *args, **kwargs):
		u = request.user
		if not u.is_authenticated():
			save_login_params(request)
			return HttpResponseRedirect('/servizi/login')
		return f(request, *args, **kwargs)
	return g

def find_common_sublists(l1, l2):
	"""
	Find common subsequences of lists l1 and l1
	
	l1, l2: lists
	output: list of tuples, with the form (0|1|2, element), where
		0: common element
		1: element of l1
		2: element of l2
	"""
	s1 = set(l1)
	s2 = set(l2)
	s0 = s1.intersection(s2)
	i1 = 0
	i2 = 0
	n1 = len(l1)
	n2 = len(l2)
	out = []
	while i1 < n1 and i2 < n2:
		e1 = l1[i1]
		e2 = l2[i2]
		if e1 in s0 and e1 == e2:
			out.append((0, e1))
			i1 += 1
			i2 += 1
		elif not e1 in s0:
			out.append((1, e1))
			i1 += 1
		else:
			out.append((2, e2))
			i2 += 1
	out.extend([(1, i) for i in l1[i1:]])	
	out.extend([(2, i) for i in l2[i2:]])
	return out
				

def batch_qs(qs, batch_size=50000):
	"""
	Yields tuples, one by one, from the queryset. The query is performed in batches.

	Usage:
			# Make sure to order your queryset
			article_qs = Article.objects.order_by('id')
			for start, end, total, qs in batch_qs(article_qs):
					print "Now processing %s - %s of %s" % (start + 1, end, total)
					for article in qs:
							print article.body
	"""
	total = qs.count()
	for start in range(0, total, batch_size):
		end = min(start + batch_size, total)
		for p in qs[start:end]:
			yield p

def render_text_template(name, ctx):
	tl = TemplateLoader()
	s, d = tl.load_template_source(name)
	out = []
	for l in s.splitlines():
		l = l.strip()
		if len(l) > 1 and l[0] == '^' and l[-1] == '$':
			l = l[1:-1]
		if l == '':
			out.append('\n')
		else:
			out.append(l)
	return Template("".join(out)).render(Context(ctx))

def add_user_to_group(user_name, group_name):
	u = User.objects.get(username=user_name)
	u.groups.add(Group.objects.get(name=group_name))
	u.save()

def instance2dict(instance, key_format=None):
	"""
	Returns a dictionary containing field names and values for the given
	instance
	"""
	from django.db.models.fields import DateField
	from django.db.models.fields.related import ForeignKey
	if key_format:
		assert '%s' in key_format, 'key_format must contain a %s'
	key = lambda key: key_format and key_format % key or key

	pk = instance._get_pk_val()
	d = {}
	for field in instance._meta.fields:
		attr = field.name
		value = getattr(instance, attr)
		if value is not None:
			if isinstance(field, ForeignKey):
				value = value._get_pk_val()
			elif isinstance(field, DateField):
				value = value.strftime('%Y-%m-%d')
		d[key(attr)] = value
	for field in instance._meta.many_to_many:
		if pk:
			d[key(field.name)] = [
				obj._get_pk_val()
				for obj in getattr(instance, field.attname).all()]
		else:
			d[key(field.name)] = []
	return d

def generate_key(length):
	chars = string.ascii_letters + string.digits + '_'
	return ''.join(random.choice(chars) for i in range(length))


def weighted_random_choice(lst):
	"""
	Choice a random element from a list of weights

	Probability to be chosen is proportional to element weight
	Return: element index
	"""
	cumul = []
	tot = 0
	for el in lst:
		tot += el
		cumul.append(tot)
	r = random.random() * tot
	for i, el in enumerate(cumul):
		if r <= el:
			return i


def cache_method(timeout_sec):
	def decorator(f):
		def g(*args, **kwargs):
			return f(*args, **kwargs)
		return g
	return decorator


def dictfetchall(cursor):
	"Returns all rows from a cursor as a dict"
	desc = cursor.description
	return [
		dict(zip([col[0] for col in desc], row))
		for row in cursor.fetchall()
	]


@contextmanager
def make_temp_directory():
	temp_dir = tempfile.mkdtemp()
	yield temp_dir
	shutil.rmtree(temp_dir)

@contextmanager
def mostra_avanzamento(totale):
	"""
	Mostra la percentuale di avanzamento di un processo

	Esempio di utilizzo:
	with mostra_avanzamento(instances.count()) as conta:
		for i in instances:
			conta()
			# processa l'istanza i
	"""
	def _now():
		return "[{}] ".format(datetime2mysql(datetime.now()))
	attuale = [0.0]
	percentuale = [0]
	print _now() + "0% ({} elementi)".format(totale)
	def _mostra_avanzamento():
		attuale[0] += 1
		p = int(100 * attuale[0] / totale)
		if p != percentuale[0]:
			percentuale[0] = p
			print _now() + str(p) + "%"
	yield _mostra_avanzamento
	if percentuale[0] != 100:
		print _now() + "100%"


@contextmanager
def chdir(new_dir):
	"""
	Context manager. Chdir to a temporary dir, and return to previous working dir on exit.
	"""
	c = os.getcwd()
	os.chdir(new_dir)
	yield
	os.chdir(c)


@contextmanager
def temp_dir():
	"""
	Context manager. Create and yield a temporary dir, and destroys it on exit
	"""
	t = tempfile.mkdtemp()
	yield t
	shutil.rmtree(t)


@contextmanager
def chdir_temp():
	"""
	Context manager. Chdir to a temporary dir, and destroys it on exit (returning to old dir).
	"""
	with temp_dir() as t:
		with chdir(t):
			yield t


def create_dir_if_not_existing(path, recurse=False):
	path = os.path.abspath(path)
	if not os.path.exists(path):
		parent, sub = os.path.split(path)
		if recurse and not os.path.exists(parent):
			create_dir_if_not_existing(parent, True)
		os.mkdir(path)


def get_singleton_subdir(path, recursive=False):
	"""
	Return the path of the subdir, if there is only a subdir
	"""
	sub = os.listdir(path)
	if len(sub) != 1:
		return path
	sub_path = os.path.join(path, sub)
	if not os.path.isdir(sub_path):
		return path
	if recursive:
		return get_singleton_subdir(sub_path)
	else:
		return sub_path


@contextmanager
def uncompress_zip(filename, enter_singleton_subdir=True, enter_singleton_recursive=False):
	with temp_dir() as path:
		with zipfile.ZipFile(filename, 'r') as zip:
			zip.extractall(path)
			if enter_singleton_subdir:
				yield get_singleton_subdir(path, enter_singleton_recursive)
			else:
				yield path


def delete_if_exists(path):
	if os.path.exists(path):
		shutil.rmtree(path)


def limiter(iter, limit=None):
	if limit is not None:
		limit -= 1
	for i, el in enumerate(iter):
		yield el
		if limit is not None and limit == i:
			break


def close_idle_db_connections():
	"""
	Close idle PostgreSQL transactions whose state has not changed during last 5 minutes

	See https://stackoverflow.com/a/30769511/170159
	"""
	sql = """
		WITH inactive_connections AS (
			SELECT
				pid,
				rank() over (partition by client_addr order by backend_start ASC) as rank
			FROM 
				pg_stat_activity
			WHERE
				-- Exclude the thread owned connection (ie no auto-kill)
				pid <> pg_backend_pid( )
			AND
				-- Exclude known applications connections
				application_name !~ '(?:psql)|(?:pgAdmin.+)'
			AND
				-- Include connections to the same database the thread is connected to
				datname = current_database() 
			AND
				-- Include connections using the same thread username connection
				usename = current_user 
			AND
				-- Include inactive connections only
				state in ('idle', 'idle in transaction', 'idle in transaction (aborted)', 'disabled') 
			AND
				-- Include old connections (found with the state_change field)
				current_timestamp - state_change > interval '5 minutes' 
		)
		SELECT
			pg_terminate_backend(pid)
		FROM
			inactive_connections 
		WHERE
			rank > 1 -- Leave one connection for each application connected to the database	
	"""
	conn = db.connections['default']
	cur = conn.cursor()
	cur.execute(sql)


class MinMaxValueData:
	"""
	Keep track of the minimum value, and its associated data

	How to use:
	```python
	mmvd = MinMaxValueData()
	for value, data1, data2 in a_list:
		mmvd.add(value, data1=data1, data2=data2)

	print(mmvd.value, mmvd.data)
	```

	Here, mmvd.data is a dictionary
	"""
	def __init__(self, find_max=False):
		"""
		Init class

		:param find_max: find max instead of min
		"""
		self.find_max = find_max
		self.value = None
		self.data = {}

	def add(self, value, **kwargs):
		if (
			self.value is None
			or (self.find_max and value > self.value)
			or (not self.find_max and value < self.value)
		):
			self.value = value
			self.data.update(kwargs)


def memoized(f):
	cache = {}
	def g(*args):
		if args in cache:
			return cache[args]
		res = f(*args)
		cache[args] = res
		return res
	return g

