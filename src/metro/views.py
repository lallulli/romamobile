# coding: utf-8

#
#    Copyright 2021 Skeed by Luca Allulli
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

from __future__ import print_function
from paline.models import *
from django.template.response import TemplateResponse

MISSING_DESCRIPTIONS = {
	'RL': 'Roma-Lido',
	'RMG': 'Roma-Centocelle',
	'RMVT': 'Roma-Civita Castellana-Viterbo'
}

def default(request):
	ctx = {}
	ps_metro = list(
		Percorso.objects.by_date().filter(linea__tipo='ME', soppresso=False).select_related('linea')
	)
	ps_fc = list(
		Percorso.objects.by_date().filter(linea__tipo='FC', soppresso=False).select_related('linea')
	)
	enhance_routes_with_stats(ps_metro)
	enhance_routes_with_stats(ps_fc)
	ls_metro = set()
	ls_fc = set()
	for p in ps_metro:
		l = p.linea
		l.descrizione = p.descrizione
		if hasattr(p, 'alerts'):
			l.alerts = p.alerts
		ls_metro.add(l)

	for p in ps_fc:
		l = p.linea
		d = p.descrizione
		if d is None:
			d = MISSING_DESCRIPTIONS.get(l.id_linea, l.id_linea)
		l.descrizione = d
		if hasattr(p, 'alerts'):
			l.alerts = p.alerts
		ls_fc.add(l)
	ctx = {
		'linee_metro': sorted(ls_metro, key=lambda l: l.descrizione),
		'linee_fc': sorted(ls_fc, key=lambda l: l.descrizione),
	}
	return TemplateResponse(request, 'metro.html', ctx)
