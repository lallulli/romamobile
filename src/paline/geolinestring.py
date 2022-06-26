import pyximport; pyximport.install()
from geocoder import SegmentGeocoder
from servizi.utils import memoized, MinMaxValueData
import geomath

class SplittableLinestring(object):
	"""
	Higher-level "geocoder" that allows to project points and split a linestring
	"""
	def __init__(self, points):
		"""
		Init a SplittableLinestring with its points

		:param points: iterable of points (x, y)
		"""
		self.sg = SegmentGeocoder()
		old = None
		self.dist = 0

		for i, p in enumerate(points):
			if old is not None:
				self.sg.add_segment(old, p, i - 1)
				self.dist += geomath.distance(old, p)
			old = p

		self.sg.freeze()

	def project_point(self, point):
		"""
		Project point and get distances from beginning

		:param point: (x, y)
		:return: Pair (distance_from_start, distance_2d)
		"""
		i, dist_inside, dist_from_start, dist_2d = self.sg.project_and_get_dist(point)
		return dist_from_start, dist_2d

	def project_and_sort(self, points, max_distance=None, callback_max_distance=None, point_extractor=None):
		"""
		Project points and get distances from beginning

		:param points: set of points (x, y), or of generic objects from which a point_extractor callback gets a point
		:param max_distance: if distance exceedes max_distance, call a callback
		:param callback_max_distance: takes two parameters (point, distance_from_linestring)
		:return: List of pairs (distance, point), sorted by distance
		"""
		if point_extractor is None:
			point_extractor = lambda p: p
		out = []
		for p in points:
			dist_from_start, dist_2d = self.project_point(point_extractor(p))
			if max_distance is not None and dist_2d > max_distance:
				callback_max_distance(p, dist_2d)
			out.append((min(max(0, dist_from_start), self.dist), p))
		out.sort(key=lambda x: x[0])
		return out


def distance_split(points, distances):
	"""
	Generator. Split linestring in sublinestrings according to distances

	:param points: linestring, as an iterable of points
	:param distances: iterable of distances, in increasing order
	:yield: list of points
	"""
	op = None
	d = 0
	# print "Distances: ", distances
	dist_iter = distances.__iter__()
	try:
		target_d = dist_iter.next()
	except StopIteration:
		yield list(points)
		points = []
	current = []
	for p in points:
		if op is not None:
			dp = geomath.distance(p, op)
			while dp > 0 and target_d is not None and d + dp >= target_d:
				frac = (target_d - d) / dp
				# print "frac = ", frac
				mp = (op[0] + frac * (p[0] - op[0]), op[1] + frac * (p[1] - op[1]))
				current.append(mp)
				yield current
				dp -= (target_d - d)
				d = target_d
				op = mp
				try:
					target_d = dist_iter.next()
				except StopIteration:
					target_d = None
				current = [mp]
			d += dp
		if p != op:
			current.append(p)
		op = p
	yield current


@memoized
def _get_splittable_linestring(points):
	return SplittableLinestring(points)


def project_and_sort_multi(
		line_points,
		points_with_multiplicity,
		max_distance=None,
		callback_max_distance=None,
		point_extractor=None,
		min_distance=100,
	):
	"""
	Project points and get distances from beginning

	Each point may appear more than once

	:param line_points: point of the line
	:param points_with_multiplicity: set of points ((x, y), n), or of generic objects
	 	from which a point_extractor callback gets a point. n is the multiplicity of each point
	:param max_distance: if distance exceedes max_distance, call a callback
	:param callback_max_distance: takes two parameters (point, distance_from_linestring)
	:return: List of pairs (distance, point), sorted by distance
	"""
	if point_extractor is None:
		point_extractor = lambda p: p
	line_points = tuple(line_points)
	main_ls = (0, line_points)
	out = []
	# print "Multiplicities: ", [x[1] for x in points_with_multiplicity]
	for p, n in points_with_multiplicity:
		# linestrings is the set of (partial) linestrings where we want to find the point.
		# Once a point has been found, if it has multiplicity more than 1, we remove the part of
		# linestring surrounding the found point, thus splitting the linestring in (at most) two parts.
		# In linestrings, we replace the split linestring with the two halves.
		# Subsequent researches of the same point will examine each (sub)linestring, and find the point
		# in the "best" one.
		linestrings = {main_ls}
		while n > 0:
			mm = MinMaxValueData()

			for ls in linestrings:
				ls_distance_from_start, ls_points = ls
				sl = _get_splittable_linestring(ls_points)
				distance_from_start, dist_2d = sl.project_point(point_extractor(p))
				mm.add(dist_2d, distance_from_start=distance_from_start, ls=ls, sl=sl)

			ls = mm.data['ls']
			ls_distance_from_start, ls_points = ls
			dist_from_start_inside_ls = mm.data['distance_from_start']
			dist_from_start = dist_from_start_inside_ls + ls_distance_from_start
			dist_2d = mm.value
			sl = mm.data['sl']
			if max_distance is not None and dist_2d > max_distance:
				callback_max_distance(p, dist_2d)
			out.append((min(max(0, dist_from_start), sl.dist), p))
			n -= 1
			if n > 0:
				linestrings.remove(ls)
				prev = dist_from_start_inside_ls - min_distance
				if prev > 0:
					res = list(distance_split(ls_points, (prev,)))
					# print 1, len(res)
					ls_points_1 = res[0]
					# ls_points_1, ls_points_2 = distance_split(ls_points, (prev,))
					linestrings.add((ls_distance_from_start, tuple(ls_points_1)))
				next = dist_from_start_inside_ls + min_distance
				if next < sl.dist:
					res = list(distance_split(ls_points, (next,)))
					if len(res) == 2:
					# print 2, len(res)
						ls_points_4 = res[1]
						# ls_points_3, ls_points_4 = distance_split(ls_points, (next,))
						linestrings.add((ls_distance_from_start + next, tuple(ls_points_4)))

	out.sort(key=lambda x: x[0])
	return out

