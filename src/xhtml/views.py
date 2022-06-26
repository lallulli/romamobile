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

"""
Python implementation of ga.php.  
"""
import re
from hashlib import md5
from random import randint
import struct
import urllib2
import time
from urllib import unquote, quote
from Cookie import SimpleCookie, CookieError
#from messaging import stdMsg, dbgMsg, errMsg, setDebugging
import uuid
from django.http import HttpResponse
import datetime
from servizi.utils import datetime2mysql
import middleware
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.shortcuts import render
from django.views.static import serve
import settings
from .models import Ad


VERSION = "4.4sh"
COOKIE_NAME = "__utmmobile"
COOKIE_PATH = "/"
COOKIE_USER_PERSISTENCE = 63072000

GIF_DATA = reduce(lambda x,y: x + struct.pack('B', y), 
				  [0x47,0x49,0x46,0x38,0x39,0x61,
				   0x01,0x00,0x01,0x00,0x80,0x00,
				   0x00,0x00,0x00,0x00,0xff,0xff,
				   0xff,0x21,0xf9,0x04,0x01,0x00,
				   0x00,0x00,0x00,0x2c,0x00,0x00,
				   0x00,0x00,0x01,0x00,0x01,0x00, 
				   0x00,0x02,0x01,0x44,0x00,0x3b], '')

# WHITE GIF:
# 47 49 46 38 39 61 
# 01 00 01 00 80 ff 
# 00 ff ff ff 00 00 
# 00 2c 00 00 00 00 
# 01 00 01 00 00 02 
# 02 44 01 00 3b									   

# TRANSPARENT GIF:
# 47 49 46 38 39 61 
# 01 00 01 00 80 00 
# 00 00 00 00 ff ff 
# ff 21 f9 04 01 00 
# 00 00 00 2c 00 00 
# 00 00 01 00 01 00 
# 00 02 01 44 00 3b				  

def get_ip(remote_address):
	# dbgMsg("remote_address: " + str(remote_address))
	if not remote_address:
		return ""
	matches = re.match('^([^.]+\.[^.]+\.[^.]+\.).*', remote_address)
	if matches:
		return matches.groups()[0] + "0"
	else:
		return ""

def get_visitor_id(guid, account, user_agent, cookie):
	"""
	 // Generate a visitor id for this hit.
	 // If there is a visitor id in the cookie, use that, otherwise
	 // use the guid if we have one, otherwise use a random number.
	"""
	if cookie:
		return cookie
	message = ""
	if guid:
		# Create the visitor id using the guid.
		message = guid + account
	else:
		# otherwise this is a new user, create a new random id.
		message = user_agent + str(uuid.uuid4())
	md5String = md5(message).hexdigest()
	return "0x" + md5String[:16]

def get_random_number():
	"""
	// Get a random number string.
	"""
	return str(randint(0, 0x7fffffff))

def write_gif_data():
	"""
	// Writes the bytes of a 1x1 transparent gif into the response.

	Returns a dictionary with the following values: 
	
	{ 'response_code': '200 OK',
	  'response_headers': [(Header_key, Header_value), ...]
	  'response_body': 'binary data'
	}
	"""
	response = HttpResponse(GIF_DATA) 
	response['Content-Type'] = 'image/gif'									 
	response['Cache-Control'] = 'private, no-cache, no-cache=Set-Cookie, proxy-revalidate'
	response['Pragma'] = 'no-cache'
	response['Expires'] = 'Wed, 17 Sep 1975 21:32:10 GMT'
	return response

def send_request_to_google_analytics(utm_url, request):
	#try:
	rq = urllib2.Request(utm_url, headers={'User-Agent': get(request.META, 'HTTP_USER_AGENT', 'Unknown'),
										  'Accepts-Language': get(request.META, "HTTP_ACCEPT_LANGUAGE",'')}
								 )
	contents = urllib2.urlopen(rq).read()
	# dbgMsg("success")
	"""
	except Exception, e:
		errMsg("fail: %s" % utm_url)
		if environ['GET'].get('utmdebug'):
			raise Exception("Error opening: %s" % utm_url)
		else:
			pass
	"""

def get(dict, key, default=''):
	if key in dict:
		return dict[key]
	else:
		return default
		
def ga(request):
	"""
	// Track a page view, updates all the cookies and campaign tracker,
	// makes a server side request to Google Analytics and writes the transparent
	// gif byte data to the response.
	"""	
	if settings.TEST_LEVEL >= 2:
		return write_gif_data()
	
	time_tup = time.localtime(time.time() + COOKIE_USER_PERSISTENCE)
	
	# set some useful items in environ: 
	x_utmac = get(request.GET, 'x_utmac')
	
	domain = get(request.META, 'HTTP_HOST')
			
	# Get the referrer from the utmr parameter, this is the referrer to the
	# page that contains the tracking pixel, not the referrer for tracking
	# pixel.	
	document_referer = get(request.GET, 'utmr')
	if not document_referer or document_referer == "0":
		document_referer = "-"
	else:
		document_referer = unquote(document_referer)

	document_path = get(request.GET, 'utmp')
	if document_path:
		document_path = unquote(document_path)

	account = get(request.GET, 'utmac')	  
	user_agent = get(request.META, 'HTTP_USER_AGENT')	

	# // Try and get visitor cookie from the request.
	cookie = get(request.COOKIES, COOKIE_NAME)

	visitor_id = get_visitor_id('', account, user_agent, cookie)
	

	utm_gif_location = "http://www.google-analytics.com/__utm.gif"

	for utmac in [account, x_utmac]:
		if not utmac:
			continue # ignore empty utmacs
		# // Construct the gif hit url.
		utm_url = utm_gif_location + "?" + \
				"utmwv=" + VERSION + \
				"&utmn=" + get_random_number() + \
				"&utmhn=" + quote(domain) + \
				"&utmsr=" + get(request.GET, 'utmsr') + \
				"&utme=" + get(request.GET, 'utme') + \
				"&utmr=" + quote(document_referer) + \
				"&utmp=" + quote(document_path) + \
				"&utmac=" + utmac + \
				"&utmcc=__utma%3D999.999.999.999.999.1%3B" + \
				"&utmvid=" + visitor_id + \
				"&utmip=" + get(request.META, 'REMOTE_ADDR')
		# dbgMsg("utm_url: " + utm_url)	
		send_request_to_google_analytics(utm_url, request)

	# // If the debug parameter is on, add a header to the response that contains
	# // the url that was used to contact Google Analytics.
	#if environ['GET'].get('utmdebug', False):
	#	headers.append(('X-GA-MOBILE-URL', utm_url))
	
	# Finally write the gif data to the response
	response = write_gif_data()
	
	# // Always try and add the cookie to the response.
	expires = time.strftime('%a, %d-%b-%Y %H:%M:%S %Z', time_tup) 
	response.set_cookie(COOKIE_NAME, visitor_id, expires=expires)	
	
	return response


def ping(request):
	return HttpResponse(datetime2mysql(datetime.datetime.now()))


def handler404(request, *args, **kwargs):
	# middleware.history_reset(request)
	return render(request, '404.html', status=404)


def handler500(request):
	middleware.history_reset(request)
	return HttpResponseRedirect('/')


def ad(request, slug, key):
	ad = Ad.objects.get(slug=slug, key=key)
	n = datetime.datetime.now()
	if ad.boost <= 0:
		status = 'Campagna interrotta'
	elif ad.max_views is not None and ad.n_views >= ad.max_views:
		status = 'Campagna non attiva, raggiunto il limite di impressioni'
	elif (ad.from_date is not None and ad.from_date > n):
		status = 'La campagna inizierà il {}'.format(ad.from_date)
	elif (ad.to_date is not None and ad.to_date < n):
		status = 'La campagna è terminata il {}'.format(ad.to_date)
	elif not ad.enabled:
		status = 'Campagna sospesa'
	else:
		status = 'Campagna attiva'
	ctx = {
		'ad': ad,
		'status': status,
	}
	ad.increment_views(-1)
	return TemplateResponse(request, 'ad.html', ctx)


def ad_on(request, slug, key):
	ad = Ad.objects.filter(slug=slug, key=key).update(enabled=True)
	return HttpResponseRedirect('/xhtml/ad/{}/{}'.format(slug, key))


def ad_off(request, slug, key):
	ad = Ad.objects.filter(slug=slug, key=key).update(enabled=False)
	return HttpResponseRedirect('/xhtml/ad/{}/{}'.format(slug, key))


