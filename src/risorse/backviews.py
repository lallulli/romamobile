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

from models import *
from django.db import models, connections, transaction
from servizi.utils import dict_cursor, project, datetime2mysql, group_required, autodump
from servizi.utils import model2contenttype
from servizi import infopoint
from servizi.models import Luogo
from datetime import datetime, timedelta, time, date
from django.template.defaultfilters import date as datefilter, urlencode
from jsonrpc import jsonrpc_method
from pprint import pprint
import logging
import settings

@jsonrpc_method('risorse_lista_tipi', safe=True)
def risorse_lista_tipi(request, tipi_permessi):
	tipi_permessi = [int(t) for t in tipi_permessi]
	ts = TipoRisorsa.objects.all().order_by('nome')
	out = []
	for t in ts:
		try:
			if t.id in tipi_permessi:
				raise TipoRisorsaCustom.DoesNotExist
			t.tiporisorsacustom
		except TipoRisorsaCustom.DoesNotExist:
			out.append({
					'id': t.id,
					'nome': t.nome,
			})
	return out
