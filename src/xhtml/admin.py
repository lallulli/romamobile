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

from django.contrib.gis import admin
from models import *

class AdAdmin(admin.OSMGeoAdmin):
	list_display = ['slug', 'from_date', 'to_date', 'boost', 'n_views', 'max_views', 'count']
	search_fields = ['slug', 'content']
	readonly_fields = ['key']
	save_as = True
	openlayers_url = 'https://openlayers.org/api/2.11/OpenLayers.js'
	wms_url = 'https://vmap0.tiles.osgeo.org/wms/vmap0'


admin.site.register(Ad, AdAdmin)


