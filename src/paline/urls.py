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
	url('^linea/(\w+)$', views.linea),
	url('^percorso/(\w+)$', views.percorso),
	url('^mappa/js/(\w+)/$', views.visualizza_mappa),
	# url('^mappa/static$', views.visualizza_mappa_statica),
	# url('^mappa/static/(\w+)$', views.visualizza_mappa_statica),
	# url('^mappa-palina/static/(\w+)$', views.visualizza_mappa_statica_palina),
	# url('^mappa-palina/static/(\w+)/(\d*)/([0-9.]*)/([0-9.]*)$', views.visualizza_mappa_statica_palina),
	url('^palina/(\w+)$', views.palina),
	url('^gruppo/(\d+)$', views.gruppo),
	url('^disservizio/(\d+)$', views.disservizio),
	url('^disservizio/gruppo/(\d+)$', views.disservizio_gruppo),
	url('^preferiti/aggiungi/(\d+)$', views.preferiti_aggiungi),
	url('^preferiti/escludi_linee/(\d+)$', views.preferiti_escludi_linee),
	url('^preferiti/elimina/(\d+)$', views.preferiti_elimina),
	url('^preferiti/elimina_palina/(\d+)/(\d+)$', views.preferiti_elimina_palina),
	url('^img-linea/(\w+)$', views.img_linea),
	url('^carica_rete$', views.carica_rete),
	url('^elenco_linee', views.elenco_linee),
	url('^sospendi_fermata/(\w+)/(\w+)$', views.sospendi_fermata),

)
