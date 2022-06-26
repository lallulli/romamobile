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

class PassaggioOffertoAdmin(admin.ModelAdmin):
	list_display = ('user', 'orario', '__unicode__')
	ordering = ('user', 'orario')
	
class PassaggioRichiestoAdmin(admin.ModelAdmin):
	list_display = ('user', 'da_orario', '__unicode__')
	ordering = ('user', 'da_orario')

class DominioOrganizzazioneInline(admin.TabularInline):
    model = DominioOrganizzazione
    extra = 3

class OrganizzazioneCarpoolingAdmin(admin.ModelAdmin):
    inlines = [DominioOrganizzazioneInline]
    list_display = ('nome',)
    search_fields = ('nome', )
	
admin.site.register(OrganizzazioneCarPooling, OrganizzazioneCarpoolingAdmin)
admin.site.register(UtenteCarPooling)
admin.site.register(PassaggioOfferto, PassaggioOffertoAdmin)
admin.site.register(PassaggioRichiesto, PassaggioRichiestoAdmin)
