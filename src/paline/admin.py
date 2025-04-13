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

from django.contrib import admin
from models import *

admin.site.register(PalinaPreferita)
admin.site.register(GruppoPalinePreferite)
admin.site.register(StatPeriodoAggregazione)
admin.site.register(Disservizio)
admin.site.register(DisservizioPalinaElettronica)
admin.site.register(LineaSospesa)
admin.site.register(FermataSospesa)
admin.site.register(ArcoRimosso)
admin.site.register(LogAvm)
admin.site.register(DescrizioneLinea)
