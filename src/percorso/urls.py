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

import django
from django.conf.urls.defaults import patterns, include, url
import views
import os, os.path

urlpatterns = patterns('',
	url('^$', views.default),
	url(r'^js/$', views.percorso_js),
	url(r'^js/(?P<path>.*)$', django.views.static.serve,
		{'document_root': os.path.join(os.path.dirname(__file__), 'js/output').replace('\\','/')}),
	url(r'^jsd/$', django.views.static.serve,
		{'document_root': os.path.join(os.path.dirname(__file__), 'js/output-pred').replace('\\','/'), 'path': 'index.html'}),
	url(r'^jsd/(?P<path>.*)$', django.views.static.serve,
		{'document_root': os.path.join(os.path.dirname(__file__), 'js/output-pred').replace('\\','/')}),
	url(r'^dettaglio$', views.dettaglio),
	url(r'^mappa-din/static$', views.mappa_statica_dinamico),
	url('^mappa-din/static/(\d*)/([0-9.]*)/([0-9.]*)$', views.mappa_statica_dinamico),
	url(r'^mappa-din/js', views.mappa_dinamico),
	url(r'^mappa/(\w+)$', views.mappa),
	url(r'^mappaimg$', views.mappaimg),
	url(r'^preferiti/aggiungi/(\w+)$', views.preferiti_aggiungi),
	url(r'^espandi$', views.calcola_percorso_espandi),
	url(r'^espandi/([^/]*)$', views.calcola_percorso_espandi),
	url(r'^aggiorna_posizione/(\w+)$', views.aggiorna_posizione),
	url(r'^avanzate$', views.avanzate),
	url(r'^da_palina/(\w+)$', views.da_palina),
	url(r'^bici/(\d+)$', views.bici),
	url(r'^modo/(\d+)$', views.modo),
	url(r'^escludi/([^/]+)$', views.escludi),
	url(r'^includi/([^/]+)$', views.includi),
	url(r'^offri-passaggio$', views.offri_passaggio),
	url(r'^trovaci/([^/]*)$', views.trovaci),
	url(r'^cerca_luogo_custom/([^/]*)$', views.cerca_luogo_custom),
	url(r'^aggiungi_widget$', views.aggiungi_widget),
	url(r'^crea_widget$', views.aggiungi_widget),
)
