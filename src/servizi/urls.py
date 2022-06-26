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
	url('^login_ws$', views.login_ws),
	url('^logout$', views.logout),
	url('^login$', views.login_page),
	url('^app_login_by_token/(.+)$', views.app_login_by_token),
	url('^login_app_landing', views.login_app_landing),
	url('^logout_return$', views.logout_return),
	url('^notifiche/(\d+)$', views.notifiche),
	url('^notifiche/fasce/(\d+)$', views.notifiche_fasce),
	url('^notifiche/fasce/elimina/(\d+)$', views.notifiche_fasce_elimina),
	url('^tema$', views.tema),
	url('^$', views.servizi_new)
)
