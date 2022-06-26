# pip install gtfs-realtime-bindings
from google.transit import gtfs_realtime_pb2
from datetime import datetime
import time
from pprint import pprint
from collections import defaultdict
import requests
import settings
import os

SEVERITY_MAPPING = {
	1: 2, # NO_SERVICE
	2: 1, # REDUCED_SERVICE
	3: 1, # SIGNIFICANT_DELAYS
	4: 0, # DETOUR
	5: 0, # ADDITIONAL_SERVICE
	6: 1, # MODIFIED_SERVICE
	7: 1, # OTHER_EFFECT
	8: 0, # UNKNOWN_EFFECT
	9: 0, # STOP_MOVED
}

def get_text(text):
	"""
	Return alert text in languages

	Return dict mapping languages to messages
	"""
	out = {}
	for t in text.translation:
		out[t.language] = t.text
	return out


def read_alerts(predicate=None):
	"""
	Read service alerts from protocolbuffer, and decode relevant ones

	Return a dictionary where lines are key, and values are:
	- max_severity
	- alerts

	Alerts is a dictionary, whose keys are language codes, values are list of messages.

	Each message is a dictionary with languages as keys, and for values:
	- header
	- description
	- severity

	Severity levels are:
	0. Information
	1. Warning, service severily affected
	2. Service interruption
	"""
	out = {}
	now_ts = time.time()

	if predicate is None:
		predicate = lambda v: True
	pb = requests.get(settings.GTFS_SA_URL, verify=False).content

	fm = gtfs_realtime_pb2.FeedMessage()
	fm.ParseFromString(pb)
	# return fm

	for e in fm.entity:
		if e.is_deleted:
			continue
		if predicate(e):
			involved_routes = []
			a = e.alert
			aps = a.active_period
			if len(aps) > 0:
				found = False
				for ap in aps:
					if ap.start <= now_ts <= ap.end:
						found = True
						break
				if not found:
					continue
			severity = SEVERITY_MAPPING[a.effect]
			message = defaultdict(dict)
			header = get_text(a.header_text)
			for lc, value in header.items():
				message[lc]['header'] =  value
				message[lc]['severity'] = severity
			desc = get_text(a.description_text)
			for lc, value in desc.items():
				message[lc]['description'] = value

			for i in a.informed_entity:
				try:
					r = i.route_id
				except AttributeError:
					r = None
				if r:
					if r in out:
						current_line = out[r]
					else:
						current_line = {
							'max_severity': -1,
							'alerts': defaultdict(list),
						}
						out[r] = current_line
					current_line['max_severity'] = max(current_line['max_severity'], severity)
					alerts = current_line['alerts']
					for lc in message:
						alerts[lc].append(message[lc])

	for line in out:
		for lc in out[line]['alerts']:
			messages = out[line]['alerts'][lc]
			messages.sort(key=lambda m: -m['severity'])

	return out


