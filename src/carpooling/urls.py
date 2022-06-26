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

from django.conf.urls.defaults import patterns, include, url
import views

urlpatterns = patterns('',
	url('^$', views.default),
	url('^cerca_passaggio$', views.cerca_passaggio),
	url('^offri_passaggio$', views.offri_passaggio),
	url('^aggiungi_punto$', views.aggiungi_punto),
	url('^dettaglio_offerta/(\d+)$', views.dettaglio_offerta),
	url('^dettaglio_richiesta/(\d+)$', views.dettaglio_richiesta),
	url('^ripeti/(\d+)$', views.ripeti),
	url('^annulla/(\d+)$', views.annulla),
	url('^accetta/(\d+)$', views.accetta),
	url('^rifiuta/(\d+)$', views.rifiuta),
	url('^annulla_richiesta/(\d+)$', views.annulla_richiesta),
	url('^offri_passaggio_tempo$', views.offri_passaggio_tempo),
	url('^richiedi/([^/]+)$', views.richiedi),
	url('^escludi/([^/]+)$', views.escludi),
	url('^telefono$', views.telefono),
	url('^abilita/(\d+)$', views.abilita),
	url('^disabilita/(\d+)$', views.disabilita),
	url('^abilitamanager$', views.abilitamanager),
	url('^feedback_richiedente/(\d+)/(\d+)$', views.feedback_richiedente),
	url('^feedback_offerente/(\d+)/(\d+)$', views.feedback_offerente),
	url('^gestione_utenti$', views.gestione_utenti),
)
