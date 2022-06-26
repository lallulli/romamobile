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

# xhtml middleware

from django.utils.datastructures import MergeDict

from servizi import models as servizi
from .models import Ad
import datetime
from django.template.defaultfilters import date as datefilter, urlencode
from django.utils.translation import ugettext as _
from random import Random, randint
from servizi.utils import messaggio
from django.http import HttpResponseRedirect
from django.utils import translation
from django.contrib.auth import login, authenticate
from django.utils.safestring import mark_safe
import settings

rnd = Random()


def get_back_url(request, depth):
	#base = 'http://' + request.META['HTTP_HOST']
	base = ''
	session = ''
	if request.does_not_accept_cookies:
		session = '&%s=%s' % (settings.SESSION_COOKIE_NAME, request.session.session_key)	
	try:
		url = request.session['history'][depth].url
		if url.find('?') == -1:
			return base + url + "?nav=%d&back=1%s" % (depth, session)
		else:
			return base + url + "&nav=%d&back=1%s" % (depth, session)
	except Exception:
		return '/'
	

def history_reset(request):
	url = request.path_info
	elem = HistoryElem('/', {})
	request.session['history'] = [elem]
	if 'history_service_depth' in request.session:
		del request.session['history_service_depth']
	request.servizio = None


def set_menu_nav(request):
	elem = HistoryElem('/', {})
	elem.future_params = request.GET
	request.session['history'] = [elem]
	# print request.session['history']
	if 'history_service_depth' in request.session:
		del request.session['history_service_depth']
	request.servizio = None


class HistoryElem(object):
	def __init__(self, url, params):
		self.url = url
		self.params = params
		self.future_params = None
		
	def set_future_params(self, p):
		self.future_params = p
		
	def get_future_params(self):
		try:
			return self.future_params
		except Exception:
			return None
		
	def __str__(self):
		return "(%s, %s, %s)" % (str(self.url), str(self.params), str(self.get_future_params()))
	
	def __repr__(self):
		return str(self)
		

def googleAnalyticsGetImageUrl(request, service):
	GA_ACCOUNT = "MO-6461187-4"
	GA_PIXEL = "/xhtml/ga"
	url = ""
	url += GA_PIXEL + "?"
	url += "utmac=" + GA_ACCOUNT
	url += "&utmn=" + str(randint(0, 0x7fffffff))

	if 'HTTP_REFERRER' in request.META:
		referer = request.META['HTTP_REFERER']
	else:
		referer = '-'
	path = service
	if settings.TEST_LEVEL == 1:
		path = 'beta-' + path
	
	if not('history' in request.session and len(request.session['history']) == 2 and 'back' not in request.REQUEST):
		path += '-internal'
	
	url += "&utmr=" + urlencode(referer)

	if path != '':
		url += "&utmp=" + urlencode(path)

	url += "&guid=ON"

	return url


class Middleware:
	def set_history(self, request):
		if not 'history' in request.session:
			history_reset(request)
		hist = request.session['history']
		url = request.path_info		
		if 'nav' in request.REQUEST:
			nav = min(int(request.REQUEST['nav']), len(hist))
			if nav < len(hist):
				if 'back' in request.REQUEST:
					url = hist[nav].url
					if 'fpage' in request.REQUEST:
						url = url[:url[1:].find('/') + 2]
					request.path_info = url
					if not 'fpage' in request.REQUEST:
						request.GET = MergeDict(hist[nav].params, request.GET)
					future = hist[nav].get_future_params()
					# print "PARAMETRI FUTURI:", future
					if future is not None:
						request.history_future = future
					hist = hist[:nav + 1] 
				else:
					hist = hist[:nav]
					elem = HistoryElem(url, request.REQUEST)
					hist.append(elem)
			else:
				hist[-1].set_future_params(request.REQUEST)
				elem = HistoryElem(url, request.REQUEST)
				hist.append(elem)
		request.session['history'] = hist
		# print "HIST", hist

	
	def process_request(self, request):
		self.set_history(request)
		
		# Aggiunge un contesto alla richiesta, che poi sarà fuso con il contesto del template
		request.ctx = {}
		
		# Localizzazione: autentica un eventuale utente localizzato, ed imposta un eventuale logo
		if 'restype' in request.GET and 'resid' in request.GET:
			u = authenticate(restype=request.GET['restype'], resid=request.GET['resid'])
			if u is not None:
				if u.is_active:
					login(request, u)
		if request.user.is_authenticated():
			try:
				lp = servizi.LogoPersonalizzato.objects.get(utente=request.user)
				request.ctx['logo_personalizzato'] = lp.path
			except servizi.LogoPersonalizzato.DoesNotExist:
				pass

		# Determina la lingua
		if request.user.is_authenticated():
			try:
				lp = servizi.LinguaPreferita.objects.get(utente=request.user)
				request.session['lingua'] = lp.lingua
				request.lingua = lp.lingua
				translation.activate(request.lingua.codice)
			except servizi.LinguaPreferita.DoesNotExist:
				request.lingua = servizi.Lingua.objects.get(codice=translation.get_language())
		elif 'lingua' in request.session:
			translation.activate(request.session['lingua'].codice)
			request.lingua = request.session['lingua']
		else:
			request.lingua = servizi.Lingua.objects.get(codice=translation.get_language())
			
		# Inizializza la stringa di debug
		request.ctx['am_debug'] = ''
		request.ctx['beta'] = settings.TEST_LEVEL >= 1
		request.ctx['lingua'] = request.lingua
		
		# Determina l'eventuale servizio chiamato
		try:
			nome_servizio = request.session['history'][1].url[1:].split("/")[0]
			if nome_servizio not in ['xhtml', 'ws', 'admin', 'js', 'json', 'back', '', 'servizi']:
				try:
					request.servizio = servizi.ServizioLingua.objects.select_related('servizio__servizio').get(servizio__servizio__nome=nome_servizio, lingua=request.lingua)
					if not 'history_service_depth' in request.session:
						request.session['history_service_name'] = request.servizio.descrizione
						request.session['history_service_depth'] = len(request.session['history']) - 1
				except servizi.ServizioLingua.DoesNotExist:
					history_reset(request)
					return HttpResponseRedirect('/')
			else:
				request.servizio = None
		except Exception:
			request.servizio = None

		# Verifica che il servizio sia abilitato
		if request.servizio is not None and not request.servizio.servizio.servizio.attivo():
			history_reset(request)
			request.session['redirect_message'] = _(u'Il servizio temporaneamente non è attivo')
			return HttpResponseRedirect('/')

		# Verifica la presenza di notifiche
		notifiche = []
		if request.user.is_authenticated():
			rns = servizi.RichiestaNotifica.objects.filter(user=request.user, su_visita=True)
			for rn in rns:
				if rn.attiva():
					try:
						if rn.downcast().calcola():
							# Refresh object in order to get updated attributes (e.g. message)
							r = servizi.RichiestaNotifica.objects.get(pk=rn.pk)
							notifiche.append(r)
					except Exception:
						pass
		request.ctx['notifiche'] = notifiche
			
		# Verifica la presenza di messaggi
		if 'redirect_message' in request.session and request.session['redirect_message'] is not None:
			request.ctx['notifiche'].append({
				'messaggio': request.session['redirect_message'],
				'icona': {
					'width': 16,
					'height': 16,
					'src': '/xhtml/s/img/ok.gif',
				}
			})
			

			request.session['redirect_message'] = None
		
		#print "FINE ELABORAZIONE RICHIESTA", request

	def process_template_response(self, request, response):
		try:
			if response.context_data is None:
				response.context_data = {}
		except:
			response.context_data = {}

		# Merge context
		response.context_data.update(request.ctx)
	
		# Data e ora
		n = datetime.datetime.now()
		dt = datefilter(n, _("d/m/y H:i"))
		response.context_data['DateTime'] = dt[0].upper() + dt[1:]
		response.context_data['now'] = n
		
		# Servizio e tool per la navigazione
		response.context_data['servizio'] = request.servizio
		response.context_data['path'] = request.path
		if 'history_service_depth' in request.session:
			response.context_data['history_service_name'] = request.session['history_service_name']
			response.context_data['history_service_url'] = get_back_url(request, request.session['history_service_depth']) + "&fpage=1"
		response.context_data['history_1'] = get_back_url(request, len(request.session['history']) - 2)
		response.context_data['refresh'] = get_back_url(request, len(request.session['history']) - 1)
		response.context_data['history_main_menu'] = '/?%s=%s' % (settings.SESSION_COOKIE_NAME, request.session.session_key) if request.does_not_accept_cookies else '/'
		# response.context_data['rnd_didyouknow'] = rnd.randint(0, 4)
		ad_geom = response.context_data.get('ad_geom', None)
		if 'ad' in response.context_data:
			response.context_data['rnd_ad'] = response.context_data['ad']
		else:
			response.context_data['rnd_ad'] = Ad.random_choice(request.lingua.codice, False, ad_geom)
		response.context_data['id_sito'] = settings.ID_SITO
		response.context_data['formaction'] = mark_safe('action="%s"' % request.path_info)
		response.context_data['id_sito'] = settings.ID_SITO		
		response.context_data['request'] = request
		platform = 'generic'
		ua = request.META['HTTP_USER_AGENT']
		if ua.find('Android') > -1:
			platform = 'Android'
		elif ua.find('iPhone') > -1:
			platform = 'iOS'
		response.context_data['platform'] = platform

		if request.servizio is not None:
			s = request.servizio.nome()
		else:
			s = 'menu'
		response.context_data['GoogleAnalytics'] = googleAnalyticsGetImageUrl(request, s)
		return response
	
	
class SessionCookieMiddleware(object):
	def process_request(self, request):
		if not request.COOKIES.has_key(settings.SESSION_COOKIE_NAME):
			request.does_not_accept_cookies = True
			if request.GET.has_key(settings.SESSION_COOKIE_NAME):
				request.COOKIES[settings.SESSION_COOKIE_NAME] = request.GET[settings.SESSION_COOKIE_NAME]
		else:
			request.does_not_accept_cookies = False