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

import marisa_trie as trie
from collections import defaultdict
from pprint import pprint
import requests
from infopoint import ESRI_GEOCODER_URL_PREFIX
import json
import re

class AutocompleteInternal(object):
	def __init__(self, resources, min_len=3, delimiter=" |/|'"):
		"""
		resources: list of pairs (item_data, resource)
		"""
		self.min_len = min_len
		self.splitter = re.compile(delimiter)
		# List of resources
		self.resources = resources
		# Mapping of words to set of resource indexes where they appear
		self.words = defaultdict(list)
		for i in range(len(self.resources)):
			res = self.resources[i][1]
			ws = self.splitter.split(res.lower())
			for w in ws:
				if len(w) >= min_len:
					w = unicode(w)
					self.words[w].append(i)
		self.t = trie.Trie(self.words.keys())


	def find(self, lookup):
		"""
		Find all resources containing a prefix of each word in lookup

		Return a list of pairs (item_data, resource)
		"""
		lookup = unicode(lookup)
		ws = self.splitter.split(lookup.lower())
		res = None
		for w in ws:
			if len(w) >= self.min_len:
				prefixed_words = set([i[0] for i in self.t.items(w)])
				resource_indexes = set()
				for p in prefixed_words:
					resource_indexes.update(self.words[p])
				if res is None:
					res = resource_indexes
				else:
					res.intersection_update(resource_indexes)
		return [self.resources[i] for i in res]


class AutocompleteEsri(object):
	def __init__(self, resources, min_len=3, delimiter=" |/|'"):
		pass

	def find(self, lookup):
		"""
		Find all resources containing a prefix of each word in lookup

		Return a list of pairs (item_data, resource)
		"""
		url = ESRI_GEOCODER_URL_PREFIX + '/suggest'
		res = requests.get(url, params={
			"text": lookup,
			'countryCode': 'IT',
			'searchExtent': '12.37602,42.00589,12.6163,41.7650',
			'location': '12.483559,41.892055',
			"f": "pjson",
		})
		out = []
		print res.status_code
		print res.text
		for elem in res.json()['suggestions']:
			t = elem['text']
			out.append((-1, t))
		return out


Autocomplete = AutocompleteEsri


def find_in_list(lookup, resources, min_length=3, delimiter=" |/|'"):
	"""
	Trivial O(n) lookup in resources, with the same semantic as in Autocomplete find method

	lookup: lookup string
	resources: list of pairs (item_data, resource)
	"""
	res = []
	splitter = re.compile(delimiter)
	ws = sorted(splitter.split(lookup.lower()))
	ws = [w for w in ws if len(w) >= min_length]
	n = len(ws)
	if n == 0:
		return []
	for i in range(len(resources)):
		ws2 = sorted(splitter.split(resources[i][1].lower()))
		ws2 = [w for w in ws2 if len(w) >= min_length]
		m = len(ws2)
		if m == 0:
			continue
		j = 0
		k = 0
		w2 = ws2[0]
		while j < n:
			w = ws[j]
			if w2.startswith(w):
				j += 1
			else:
				if w2 > w:
					break
				k += 1
				if k == m:
					break
				w2 = ws2[k]
		if j == n:
			res.append(resources[i])
	return res

