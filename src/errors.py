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

from xmlrpclib import Fault

XMLRPC = {
	'XRE_EXC':					Fault(801, 'Eccezione generica'),
	'XRE_DB':					Fault(802, 'Errore database'),
	'XRE_NO_ID_PALINA':			Fault(803, 'Palina inesistente'),
	'XRE_NO_LINEA':				Fault(804, 'Linea inesistente'),
	'XRE_PALINA_NOTIN_LINEA':	Fault(805, 'La linea non contiene la palina richiesta'),
	'XRE_NO_CARTEGGIO':			Fault(806, 'Carteggio inesistente'),
	'XRE_NO_PERCORSO':			Fault(807, 'Percorso inesistente'),
	'XRE_PALINA_NON_RAGGIUNTA':	Fault(808, 'Palina non raggiunta dal servizio'),
	'XRE_LINEA_NON_ABILITATA':	Fault(809, 'Linea non abilitata al servizio'),
	'XRE_TYPE_MISMATCH':		Fault(810, 'Tipo non corrispondente'),
	'XRE_MSG_TOO_LONG':			Fault(811, 'Messaggio troppo lungo'),
	'XRE_NO_KIOSK':				Fault(812, 'Chiosco inesistente'),
	'XRE_EMPTY_XML':			Fault(813, 'XML nel database vuoto'),
	'XRE_NO_ZONE':				Fault(814, 'Zona inesistente'),
	'XRE_XML':					Fault(815, 'Errore XML'),
	'XRE_NO_CAMERA':			Fault(816, 'Telecamera inesistente'),
	'XRE_CAMERA_NOT_PUBLIC':	Fault(817, 'Telecamera non pubblica'),
	'XRE_NO_ROUTE':				Fault(818, 'Tratta inesistente'),
	'XRE_NO_NEWS':				Fault(819, 'Notizia inesistente'),
	'XRE_SOAP':					Fault(820, 'Errore client SOAP'),
	'XRE_AUTH':					Fault(821, 'Errore di autenticazione'),
	'XRE_NO_VEHICLE':			Fault(822, 'Veicolo non trovato'),
	'XRE_AMBIGUOUS':			Fault(823, 'Richiesta ambigua'),
	'XRE_NOT_LOGGED':			Fault(824, 'Accesso non effettuato'),
	'XRE_DAILY_LIMIT':		Fault(825, 'Raggiunto limite giornaliero accessi'),
}