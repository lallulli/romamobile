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

admin.site.register(Servizio)
admin.site.register(FasciaServizio)
admin.site.register(Versione)
admin.site.register(ServizioFrontEnd)
admin.site.register(Lingua)
admin.site.register(ServizioLingua)
admin.site.register(GruppoServizio)
admin.site.register(GiornoSettimana)
admin.site.register(LinguaPreferita)
admin.site.register(LogoPersonalizzato)
admin.site.register(Festivita)
admin.site.register(StatoProcessamento)

class RicercaErrataAdmin(admin.ModelAdmin):
    list_display = ('ricerca', 'conteggio', 'conversione')
    search_fields = ('ricerca', 'conversione')

admin.site.register(RicercaErrata, RicercaErrataAdmin)