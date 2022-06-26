# coding: utf-8
from servizi.models import RicercaErrata

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

from servizi.utils import ricapitalizza, contenttype2model
from servizi.models import *
import re
import urllib, urllib2
from BeautifulSoup import BeautifulStoneSoup
import xml.etree.ElementTree as ET 
import pyproj
from django.utils.translation import ugettext as _
import base64
import settings
from paline.geomath import gbfe_to_wgs84, wgs84_to_gbfe
import json
from pprint import pprint
from paline import models as paline
from risorse import models as risorse
from mercury.models import Mercury
import requests
import traceback

DEFAULT_GEOCODER = 'esri'
ESRI_GEOCODER_MIN_SCORE = 60
ESRI_GEOCODER_FULL_SCORE = 99
ESRI_GEOCODER_MIN_DELTA = 2
ESRI_GEOCODER_MAX_DELTA = 8
ESRI_GEOCODER_URL_PREFIX = r'https://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer'

map_width = 200
map_height = 150
map_size = 230
zoom_min = 1
zoom_max = 15

# Infopoint restituisce le coordinate proiettate in Gauss-Boaga fuso est
gbfe = pyproj.Proj("+proj=tmerc +lat_0=0 +lon_0=15 +k=0.9996 +x_0=2520000 +y_0=0 +ellps=intl +units=m +no_defs")
gbfo = pyproj.Proj("+proj=tmerc +lat_0=0 +lon_0=9 +k=0.9996 +x_0=1500000 +y_0=0 +ellps=intl +units=m +no_defs")

infopoint_url = ""

re_spazi_duplicati = re.compile(r' +')
def cerca_ricerca_errata(ricerca):
	"""
	Cerca la ricerca corrente tra quelle errate.

	Se la trova, restituisce l'eventuale conversione e l'oggetto ricerca errata.
	Input: stringa di ricerca
	Altrimenti restituisce None
	"""
	ricerca = re_spazi_duplicati.sub(' ', ricerca).lower()
	# print ricerca
	res = RicercaErrata.objects.filter(ricerca=ricerca).order_by('-conteggio')
	if len(res) > 0:
		r = res[0]
		if r.conversione is not None:
			r.conteggio += 1
			r.save()
		return (r.conversione, r)
	return None

def aggiorna_ricerca_errata(ricerca, ricerca_errata=None):
	"""
	Aggiorna le statistiche sulle ricerche errate.

	Se ricerca_errata è None, crea una nuova istanza di RicercaErrata
	"""
	if ricerca_errata is None:
		ricerca = re_spazi_duplicati.sub(' ', ricerca).lower()
		RicercaErrata(ricerca=ricerca).save()
	else:
		ricerca_errata.conteggio += 1
		ricerca_errata.save()

def correggi_ricerca_errata(f):
	def g(request, address, *args, **kwargs):
		address.strip()
		ricerca = address
		ricerca_errata = None
		res = cerca_ricerca_errata(ricerca)
		if res is not None:
			conversione, ricerca_errata = res
			if conversione is not None:
				address = conversione
		res = f(request, address, *args, **kwargs)
		if res['stato'] != 'OK':
			aggiorna_ricerca_errata(ricerca, ricerca_errata)
		return res
	return g


def componi_indirizzo_place(address, streetno, place):
	streetno = u" %s" % streetno if streetno != '' else ''
	return ricapitalizza("%s%s, %s" % (address, streetno, place))

def decomponi_indirizzo_place(s):
	i = s.rfind(',')
	if i > 0:
		place = s[i + 1:].strip()
		d = re.compile("[1-9]+")
		if d.search(place) is not None:
			place = "Roma"
		else:
			s = s[:i]
	else:
		place = "Roma"
	r = re.compile(",? *([1-9][0-9]*([ /]*[A-Za-z])?)$")
	m = r.search(s)
	if m is None:
		address = s
		streetno = ""
	else:
		address = s[:m.start()]
		streetno = m.groups(0)[0]
		
	return address, streetno, place


def geocode_place_infotpdati(request, composite_address):
	# print "Geocoding"
	if composite_address.startswith('punto:'):
		try:
			lat, lng = [float(x) for x in composite_address[7:-1].split(',')]
			x, y = wgs84_to_gbfe(lng, lat)
			out = {
				'stato': 'OK',
				'indirizzo': _('Punto su mappa <punto:(%0.4f,%0.4f)>') % (lat, lng),
				'ricerca': composite_address,
				'streetno': '',
				'address': _('Punto su mappa <punto:(%0.4f,%0.4f)>') % (lat, lng),
				'place': '',
				'y': y,
				'x': x,
				'nnp': '',
			}
			return out
		except Exception, e:
			return {'stato': 'Error'}

	address, streetno, place = decomponi_indirizzo_place(ricapitalizza(composite_address))

	serv_session = 'NONE'
	if request is not None:
		serv_session = request.session.session_key

	params = {
		'op': 'getStreetGeocoding',
		'var_street': u"{} {}".format(address, streetno),
		'var_city': place,
		'serv_user': infotpdati_key,
		'serv_session': serv_session,
		'output_type': '1',
	}
	# pprint(params)
	soup = requests.get(infotpdati_url, params=params).json()
	# pprint(soup)

	if soup['status'] == 'ok':
		strade = soup['strade']
		if len(strade) == 1:
			s = strade[0]
			lon, lat = float(s['long'].replace(',', '.')), float(s['lat'].replace(',', '.'))
			x, y = wgs84_to_gbfe(lon, lat)
			cip = componi_indirizzo_place(s['address'], streetno, place)
			return {
				'stato': 'OK',
				'indirizzo': cip,
				'ricerca': cip,
				'streetno': streetno,
				'address': componi_indirizzo(address, streetno),
				'place': place,
				'y': y,
				'x': x,
				'nnp': '',
			}
		else:
			# Ambiguo
			out = {
				'stato': 'Ambiguous',
				'indirizzi': [componi_indirizzo_place(x['address'], streetno, place) for x in strade],
			}
	else:
		return {
			'stato': 'Error',
		}
	if len(out['indirizzi']) > 20:
		return {
			'stato': 'Error',
		}
	return out


def geocode_place_esri(request, composite_address):
	res = requests.get(
		ESRI_GEOCODER_URL_PREFIX + '/findAddressCandidates',
		params={
			'SingleLine': composite_address,
			'forStorage': 'false',
			'f': 'pjson',
			'countryCode': 'IT',
			'searchExtent': '12.1317,42.0959,12.8238,41.6903',
			'location': '12.483559,41.892055'
		}
	)
	# print(res.status_code)
	# print(res.text)
	# pprint(res.json())
	res = res.json()['candidates']
	# cs = [(c['score'], c['address'], c['location']['x'], c['location']['y']) for c in res['candidates'] if c['score'] >= ESRI_GEOCODER_MIN_SCORE]
	res.sort(key=lambda c: c['score'], reverse=True)
	single = True
	if len(res) == 0:
		return {
			'stato': 'Error',
		}
	if len(res) > 1:
		single = False
		s0 = res[0]['score']
		s1 = res[1]['score']
		if s0 >= ESRI_GEOCODER_FULL_SCORE or s0 - s1 > ESRI_GEOCODER_MIN_DELTA:
			single = True
	if single:
		r = res[0]
		loc = r['location']
		lng, lat = loc['x'], loc['y']
		x, y = wgs84_to_gbfe(lng, lat)
		return {
			'stato': 'OK',
			'indirizzo': r['address'],
			'ricerca': r['address'],
			'streetno': '',
			'address': r['address'],
			'place': '',
			'y': y,
			'x': x,
			'lng': lng,
			'lat': lat,
			'nnp': '',
		}
	return {
		'stato': 'Ambiguous',
		'indirizzi': [r['address'] for r in res],
	}


def geocode_place_google(request, composite_address):
	# print "Geocoding con GOOGLE"
	address, streetno, place = decomponi_indirizzo_place(ricapitalizza(composite_address))
	params = {
		'address': componi_indirizzo_place(address, streetno, place).encode('utf8'),
		'sensor': 'false',
		'language': 'it',
		'region': 'it',
	}
	# disable proxy in 3 steps
	# 1: define a proxy handler which does not use a proxy (empty dict)
	h = urllib2.ProxyHandler({})
	# 2: construct an opener
	opener = urllib2.build_opener(h)
	# 3: register the opener globally
	urllib2.install_opener(opener)
	
	f = urllib2.urlopen(u'http://maps.googleapis.com/maps/api/geocode/json?%s' % urllib.urlencode(params))
	geo = json.loads(f.read())
	f.close()
	results = geo['results']

	if len(results) == 1:
		r = results[0]
		loc = r['geometry']['location']
		x, y = wgs84_to_gbfe(loc['lng'], loc['lat'])
		return {
			'stato': 'OK',
			'indirizzo': r['formatted_address'],
			'ricerca': r['formatted_address'],
			'streetno': streetno,
			'address': componi_indirizzo(address, streetno),
			'place': place,
			'y': y,
			'x': x,
			'nnp': '',
		}
	elif len(results) > 1:
		out = {
			'stato': 'Ambiguous',
			'indirizzi': [r['formatted_address'] for r in results],
		}
	else:
		return {
			'stato': 'Error',
		}
	return out



def geocode_place_infotp(request, composite_address):
	# print "Geocoding"
	if composite_address.startswith('punto:'):
		try:
			lat, lng = [float(x) for x in composite_address[7:-1].split(',')]
			x, y = wgs84_to_gbfe(lng, lat)
			out = {
				'stato': 'OK',
				'indirizzo': _('Punto su mappa <punto:(%0.4f,%0.4f)>') % (lat, lng),
				'ricerca': composite_address,
				'streetno': '',
				'address': _('Punto su mappa <punto:(%0.4f,%0.4f)>') % (lat, lng),
				'place': '',
				'y': y,
				'x': x,
				'nnp': '',
			}
			return out
		except Exception, e:
			return {'stato': 'Error'}
	
	address, streetno, place = decomponi_indirizzo_place(ricapitalizza(composite_address))
	root = ET.Element('request_norm')
	xplace = ET.SubElement(root, "place")
	xplace.text = place
	xaddress = ET.SubElement(root, "address")
	xaddress.text = address
	xnumber = ET.SubElement(root, "number")
	xnumber.text = streetno
	response = urllib2.urlopen(infopoint_url + "norm_xml.asp", ET.tostring(root), timeout=settings.INFOPOINT_TIMEOUT)
	soup = BeautifulStoneSoup(response.read())
	if soup.status.text == 'OK':
		#lon, lat = gbfe(float(soup.coord_x.text), float(soup.coord_y.text), inverse=True)
		#x, y = gbfo(lon, lat)
		x, y = float(soup.coord_x.text), float(soup.coord_y.text)
		cip = componi_indirizzo_place(soup.candidate.text, streetno, place)
		return {
			'stato': 'OK',
			'indirizzo': cip,
			'ricerca': cip,
			'streetno': streetno,
			'address': componi_indirizzo(address, streetno),
			'place': place,
			'y': y,
			'x': x,
			'nnp': soup.nnp.text,
		}
	elif soup.status.text == 'Warning' and soup.warning_code.text == '2':
		out = {
			'stato': 'Ambiguous',
			'indirizzi': [componi_indirizzo_place(x.text, streetno, place) for x in soup.findAll('candidate')],
		}
	elif soup.status.text == 'Warning' and soup.warning_code.text == '1':
		out = {
			'stato': 'Ambiguous',
			'indirizzi': [componi_indirizzo_place(address, streetno, x.text) for x in soup.findAll('candidate')],
		}
	else:
		return {
			'stato': 'Error',
		}
	if len(out['indirizzi']) > 10:
		return {
			'stato': 'Error',
		}
	return out


def geocode_place_gbfe_only(request, address, geocoder=DEFAULT_GEOCODER):
	if len(paline.Linea.objects.by_date().filter(id_linea=address.strip())) > 0:
		return {'stato': 'Error'}
	if geocoder == 'esri':
		gc = geocode_place_esri
	elif geocoder == 'infotpdati':
		gc = geocode_place_infotpdati
	elif geocoder == 'google':
		gc = geocode_place_google
	else:
		gc = geocode_place_infotp
	return gc(request, address)

re_address = re.compile(r'.*<(.*)>')

@correggi_ricerca_errata
def geocode_place(request, address, geocoder=DEFAULT_GEOCODER):
	address = address.strip()
	address_sym = re_address.findall(address)
	if len(address_sym) == 1:
		r = geocode_place(request, address_sym[0], geocoder)
		r['ricerca'] = address
		return r
	if len(address) == 5 and address.isdigit():
		address = 'fermata:%s' % address
	if address.startswith('punto:'):
		try:
			lat, lng = address[7:-1].split(',')
			x, y = wgs84_to_gbfe(lng, lat)
			out = {
				'stato': 'OK',
				'indirizzo': _('Punto su mappa <punto:(%s,%s)>') % (lat, lng),
				'ricerca': address,
				'streetno': '',
				'address': _('Punto su mappa <punto:(%s,%s)>') % (lat, lng),
				'place': '',
				'y': y,
				'x': x,
				'lng': lng,
				'lat': lat,
			}
			return out
		except Exception, e:
			return {'stato': 'Error'}
	elif address.startswith('fermata:'):
		id_palina = address[8:]
		p = paline.Palina.objects.by_date().filter(id_palina=id_palina)
		if len(p) == 0:
			return {
				'stato': 'Error',
			}
		else:
			p = p[0]
			coord = Mercury.sync_any_static(settings.MERCURY_WEB, 'coordinate_palina', {'id_palina': id_palina})
			lat, lng = coord['lat'], coord['lng']
			x, y = wgs84_to_gbfe(lng, lat)
			return {
				'stato': 'OK',
				'address': address,
				'place': 'Roma',
				'palina': id_palina,
				'indirizzo': "%s (%s)" % (p.nome_ricapitalizzato(), p.id_palina),
				'ricerca': address,
				'x': x,
				'y': y,
				'lng': lng,
				'lat': lat,
			}
	elif address.startswith('risorsa:'):
		id = [int(x) for x in address[8:].split('-')]
		model = contenttype2model(id[0])
		r = model.objects.get(pk=id[1])
		try:
			indirizzo = r.indirizzo
		except:
			indirizzo = ''
		geom = r.geom
		x, y = r.geom.x, r.geom.y
		# lng, lat = gbfe_to_wgs84(x, y)
		return {
			'stato': 'OK',
			'address': address,
			'place': 'Roma',
			'risorsa': id,
			'indirizzo': indirizzo,
			'ricerca': address,
			'x': x,
			'y': y,
		}	
	res = geocode_place_gbfe_only(request, address, geocoder)
	if res['stato'] == 'OK':
		res['lng'], res['lat'] = gbfe_to_wgs84(res['x'], res['y'])
	return res
		


def componi_indirizzo(address, streetno):
	streetno = " %s" % streetno if streetno != '' else ''
	return "%s%s" % (address, streetno)

def decomponi_indirizzo(s):
	r = re.compile(",? *([1-9][0-9]*([ /]*[A-Za-z])?)$")
	m = r.search(s)
	if m is None:
		address = s
		streetno = ""
	else:
		address = s[:m.start()]
		streetno = m.groups(0)[0]
		
	return address, streetno

def _contiene(luogo, richiesti):
	for w in richiesti:
		if luogo.lower().find(w) != -1:
			return True
	return False

def _decodifica_luoghi_ambigui(luoghi, richiesto):
	out = []
	richiesti = richiesto.lower().split()
	for l in luoghi:
		localita, comune, provincia, cap = l.text.split(' -- ')
		if _contiene(localita, richiesti):
			out.append((localita, comune))
	out.sort()
	# rimozione duplicati
	"""
	out2 = []
	prev = None
	for o in out2:
		if prev is None or prev != o[0]:
			prev = o[0]
			out2.append(o)
	print out2
	"""
	return out
			

def find_resources(request, point, resource_type):
	root = ET.Element('request_resource')
	xplace = ET.SubElement(root, "place")
	xplace.text = "Roma"
	command = ET.SubElement(root, "command")
	command.text = "showresource"
	command.attrib['mode'] = "3"
	command.attrib['maxcounts'] = "5"
	command.attrib['mintoshow'] = "2"
	child_id = ET.SubElement(root, "child_id")
	child_id.text = str(resource_type)
	nnp_start = ET.SubElement(root, "nnp_start")
	nnp_start.text = point['nnp']
	coord_x = ET.SubElement(root, "coord_x")
	coord_x.text = str(point['coord_x'])
	coord_y = ET.SubElement(root, "coord_y")
	coord_y.text = str(point['coord_y'])	
	mapsize = ET.SubElement(root, "mapsize")
	mapsize.text = str(map_size)
	image_width = ET.SubElement(root, "image_width")
	image_width.text = str(map_width)
	image_height = ET.SubElement(root, "image_height")
	image_height.text = str(map_height)
	
	response = urllib2.urlopen(infopoint_url + "resource_xml.asp", ET.tostring(root), timeout=settings.INFOPOINT_TIMEOUT)
	soup = BeautifulStoneSoup(response.read())
	request.session['infopoint'] = {
		'point': point,
		'soup': soup,
		'context': 	soup.contextname.text,
		'zoom_min': zoom_min,
		'zoom_max': zoom_max,
		'map': base64.b64decode(soup.server_response.image.text),
		'zoomlevel': zoom_max - 2
	}
	return soup


def calculate_route(request, mean, mode, start, stop, date=None):
	root = ET.Element('request_navigate')
	xplace = ET.SubElement(root, "place")
	xplace.text = "Roma"
	command = ET.SubElement(root, "command")
	command.text = "bestway"
	nnp_start = ET.SubElement(root, "nnp_start")
	nnp_start.text = start['nnp']
	civic_start = ET.SubElement(root, "civic_start")
	civic_start.text = start['streetno']
	nnp_end = ET.SubElement(root, "nnp_end")
	nnp_end.text = stop['nnp']
	civic_end = ET.SubElement(root, "civic_end")
	civic_end.text = stop['streetno']
	mapsize = ET.SubElement(root, "mapsize")
	mapsize.text = str(map_size)
	image_width = ET.SubElement(root, "image_width")
	image_width.text = str(map_width)
	image_height = ET.SubElement(root, "image_height")
	image_height.text = str(map_height)
	bw_option = ET.SubElement(root, "bw_option")
	tp_mean = ET.SubElement(bw_option, "tp_mean")
	tp_mean.text = str(mean)
	bw_optimization = ET.SubElement(bw_option, "bw_optimization")
	bw_optimization.text = str(mode)
	if date is not None:
		bw_date = ET.SubElement(root, 'bw_date')
		day = ET.SubElement(bw_date, 'day')
		day.text = str(date.day)
		month = ET.SubElement(bw_date, 'month')
		month.text = str(date.month)
		year = ET.SubElement(bw_date, 'year')
		year.text = str(date.year)
		hour = ET.SubElement(bw_date, 'hour')
		hour.text = str(date.hour)
	tongue = ET.SubElement(root, "tongue")
	tongue.text = _("ita")		
		
	response = urllib2.urlopen(infopoint_url + "navigate_xml.asp", ET.tostring(root), timeout=settings.INFOPOINT_TIMEOUT)
	soup = BeautifulStoneSoup(response.read())
	request.session['infopoint'] = {
		'mean': mean,
		'mode': mode,
		'start': start,
		'stop': stop,
		'date': date,
		'soup': soup,
		'context': 	soup.contextname.text,
		'zoom_min': zoom_min,
		'zoom_max': zoom_max,
		'dyn': False
	}
	return soup
	
	
def prepare_map(request, number=None):
	ip = request.session['infopoint']
	oldsoup = ip['soup']
	root = ET.Element('request_navigate')
	xplace = ET.SubElement(root, "place")
	xplace.text = "Roma"
	mapsize = ET.SubElement(root, "mapsize")
	mapsize.text = str(map_size)
	image_width = ET.SubElement(root, "image_width")
	image_width.text = str(map_width)
	image_height = ET.SubElement(root, "image_height")
	image_height.text = str(map_height)
	context = ET.SubElement(root, "contextname")
	context.text = ip['context']
	command = ET.SubElement(root, 'command')
	zoom_init = False
	try:
		number = int(number)
		elem = oldsoup.findAll(hot_x=True)[number]
		command.text = 'zoomat'
		coord_x = ET.SubElement(root, 'coord_x')
		coord_x.text = elem['hot_x']
		coord_y = ET.SubElement(root, 'coord_y')
		coord_y.text = elem['hot_y']
		# zoomlevel will be immediately decreased to 2
		ip['zoomlevel'] = zoom_max + 1
		zoom_init = True
	except ValueError:
		if number in ['i', 'o']:
			zl = ip['zoomlevel']
			command.text = 'zoom'
			if number == 'o' and zl > zoom_min:
				zl -= 1
				zt = '2'
			elif number == 'i' and zl < zoom_max:
				zl += 1
				zt = '1'
			command.attrib['zoomtype'] = zt
			ip['zoomlevel'] = zl
		elif number in ['n', 's', 'w', 'e']:
			command.text = 'pan'
			command.attrib['pantype'] = {
				'w': '1',
				'n': '2',
				'e': '3',
				's': '4'
			}[number]
	response = urllib2.urlopen(infopoint_url + "navigate_xml.asp", ET.tostring(root), timeout=settings.INFOPOINT_TIMEOUT)
	soup = BeautifulStoneSoup(response.read())
	#print soup
	ip['map'] = base64.b64decode(soup.server_response.image.text)
	ip['context'] = soup.contextname.text
	if zoom_init:
		prepare_map(request, 'o')
	
def get_map(request):
	return request.session['infopoint']['map']
