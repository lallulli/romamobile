# coding: utf-8

#
#    Copyright 2015-2016 Roma servizi per la mobilità srl
#    Developed by Luca Allulli
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

from gtfs_pb2 import TripUpdate, FeedHeader, FeedMessage
from datetime import date, time, datetime, timedelta
from servizi.utils import datetime2unixtime

def generate_feed(ultimo_aggiornamento):
	f = FeedMessage()
	fh = f.header
	fh.gtfs_realtime_version = "1"
	fh.timestamp = int(datetime2unixtime(ultimo_aggiornamento))
	return f

def generate_gtfs_rt(rete, arrivi):
	f = generate_feed(arrivi['ultimo_aggiornamento'])
	entity_count = 0
	for perc in arrivi['percorsi']:
		id_percorso = perc['id_percorso']
		percorso = rete.percorsi[id_percorso]
		last_update = perc['ultimo_aggiornamento']
		for v in perc['arrivi']:
			# Entità
			entity = f.entity.add()
			entity.id = str(entity_count)
			entity_count += 1

			# TripUpdate
			tu = entity.trip_update

			# TripDescriptor
			td = tu.trip
			td.route_id = percorso.id_linea
			td.schedule_relationship = 1 # ADDED

			# VehicleDescriptor
			id_veicolo = v['id_veicolo']
			vd = tu.vehicle
			vd.id = id_veicolo
			vd.label = id_veicolo

			# Arrivals
			arrivi = v['arrivi']
			for id_fermata in arrivi:
				stu = tu.stop_time_update.add()
				stu.stop_id = id_fermata
				ste = stu.arrival
				# StopTimeEvent
				ste.time = int(datetime2unixtime(arrivi[id_fermata]))

			# Vehicle entity
			entity_vehicle = f.entity.add()
			entity_vehicle.id = str(entity_count)
			entity_count += 1

			# VehiclePosition and VehicleDescriptor
			vp = entity_vehicle.vehicle
			vd = vp.vehicle
			vd.id = id_veicolo
			vd.label = id_veicolo
			vp.stop_id = v['id_prossima_palina']
			vp.timestamp = int(datetime2unixtime(last_update))

	return f
