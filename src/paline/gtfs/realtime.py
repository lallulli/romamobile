# pip install gtfs-realtime-bindings
from google.transit import gtfs_realtime_pb2
from datetime import datetime
from pprint import pprint
import json
import requests
import settings
import os


MAPPING_FILE = os.path.join(settings.TROVALINEA_PATH_RETE, 'mapping_gtfs.json')


def get_gtfs_rt_last_update():
	return requests.head(settings.GTFS_RT_URL, verify=False).headers['Last-Modified']


def read_vehicles(predicate=None):
	"""
	Read vehicle data from protocolbuffer, and decode to Python dict
	"""
	if predicate is None:
		predicate = lambda v: True
	pb = requests.get(settings.GTFS_RT_URL, verify=False).content

	fm = gtfs_realtime_pb2.FeedMessage()
	fm.ParseFromString(pb)

	for e in fm.entity:
		v = e.vehicle
		if predicate(v):
			# print(v)
			vid = v.vehicle.id
			if vid != '':
				vlab = v.vehicle.label
				if vlab != '':
					vid = vlab
				elif "_" in vid:
					vid = vid[:vid.find('_')]
				else:
					vid += " [Fittizio]"
				yield {
					'route_id': v.trip.route_id,
					'trip_id': v.trip.trip_id,
					'coord': (v.position.longitude, v.position.latitude),
					'vehicle_id': vid,
					'status': v.current_status,
					'start_time': v.trip.start_time,
					'progressiva': v.current_stop_sequence,
					'stop_id': v.stop_id,
					'timestamp': datetime.fromtimestamp(v.timestamp),
					'occupancy_status': int(v.occupancy_status) if v.occupancy_status else None,
				}


def decode_vehicles(trip_to_id_percorso, it):
	"""
	Translate GTFS-encoded vehicle data to mar-encoded data

	:param trip_mapping: dict mapping trip_id's to route id's
	"""
	not_decoded = 0
	total = 0
	for v in it:
		try:
			total += 1
			id_percorso = trip_to_id_percorso[v['trip_id']]
			v['id_percorso'] = id_percorso
			yield v
		except:
			not_decoded += 1
			print("NOT DECODED: ")
			pprint(v)
	print("Not decoded:", not_decoded, total)


def test_raw():
	for v in read_vehicles():
		print(v)


def test_timestamp():
	n = datetime.now()
	for v in read_vehicles():
		print((n - v['timestamp']).seconds)


if __name__ == '__main__':
	# test_raw()
	test_decode()
