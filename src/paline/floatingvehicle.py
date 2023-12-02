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


from datetime import date, time, datetime, timedelta
import logging
import math

MAX_TIME = 30 * 60     # 30 minuti
EQUIV_SPEED = 10 / 3.6 # 10  km/h
EXP_CONSTANT = -2.3
TIME_BUFFER = 4 * 60   # Negli ultimi (4) minuti i campioni hanno peso 1, poi il peso decresce
SPACE_BUFFER = 0       # Il bus si deve spostare di almeno (10) m perché sia considerato un nuovo campione
#ALGO = 'exp'
ALGO = 'avg'
SPEED_LIMIT = 80 / 3.6 # 80 km/h

# If a bus goes back by up to MAX_BACKING since last sample, discard new sample
MAX_BACKING = 1000

class FVPath(object):
	def __init__(self):
		object.__init__(self)
		# Map vehicle id's to list of raw vehicle data
		# It is a list of tuples (timestamp, distance)
		self.raw = {}
		# List of speed samples, where each sample has the following form:
		# (time, central_distance, speed, vehicle_id, delta_t)
		# central_distance: distance (from final destination) of middle point of segment where speed is computed
		# speed: in m/s
		# delta_t: temporal width where speed is computed
		self.speed = []
		
	def add(self, id, time, place):
		# print "Aggiungo dati veicolo"
		if not id in self.raw:
			self.raw[id] = []
		op = None
		if len(self.raw[id]) > 0:
			op = self.raw[id][-1][1]
		if op is None or place <= op - SPACE_BUFFER or place > op + MAX_BACKING:
			self.raw[id].append((time, place))
		else:
			pass
			# print "Non si e' mosso"
		
	def process_data(self, time=None):
		if time is None:
			time = datetime.now()
		# print "Pulisco velocita'"
		new_speed = []
		for el in self.speed:
			t = el[0]
			dt = (max(t, time) - min(t, time)).seconds
			if dt <= MAX_TIME:
				new_speed.append(el)
		self.speed = new_speed

		# print "Processo dati percorso"
		for id in self.raw:
			#print self.raw[id]
			vehicle_data = self.raw[id]
			old = None
			for new in vehicle_data:
				if old is not None:
					dt = float((new[0] - old[0]).seconds)
					dd = old[1] - new[1]
					if new[0] >= old[0] and dd >= 0:
						speed = dd / dt
						if speed < SPEED_LIMIT:
							self.speed.append((new[0], (new[1] + old[1]) / 2.0, speed, id, dt))
							# print("Tutto ok!!!", dt, dd, speed)
						else:
							pass
							# print("Speed limit!!!", dt, dd, speed)
					"""
					else:
						if dt <= 0:
							print("Dato duplicato: (%s, %s)" % (str(old), str(new)))
						else:
							print("Spazio negativo (possibile nuovo ciclo): (%s, %s)" % (str(old), str(new)))
					"""
				old = new
			if old is not None:
				self.raw[id] = [old]
		
	def compute_speed(self, time, place_start, place_stop=None):
		#print "Computing speed at %d from:" % place_start
		#print self.speed
		if place_stop is None:
			place_stop = place_start
		p1 = min(place_start, place_stop)
		p2 = max(place_start, place_stop)
		t1 = time - timedelta(seconds=TIME_BUFFER)
		t2 = time + timedelta(seconds=TIME_BUFFER)
		cnt = 0
		weight = 0
		for el in self.speed:
			t, p, s, id, dtw = el
			if t < t1:
				dt = (t1 - t).seconds
			elif t > t2:
				dt = (t - t2).seconds
			else:
				dt = 0
			if p < p1:
				dp = p1 - p
			elif p > p2:
				dp = p - p2
			else:
				dp = 0
			#print "dt = ", dt
			#print "dp equiv = ", dp / EQUIV_SPEED
			wp = dtw * (MAX_TIME - dt - dp / EQUIV_SPEED) / float(MAX_TIME)
			if wp > 0:
				if ALGO == 'exp':
					wd = dp + dt * EQUIV_SPEED
					w = math.exp(EXP_CONSTANT * wd)
				else:
					w = wp
				cnt += w * s
				weight += w
			#print "Internal weight:", w
		if weight > 0:
			if cnt < 0:
				print "ERRORE! VELOCITA' NEGATIVA!"
				print cnt
			#print "Calcolata velocita':", cnt/weight, weight
			return (cnt / weight, weight)
		else:
			pass
			#print "Scartata velocita', il peso vale ", weight
		return (-1, 0)
