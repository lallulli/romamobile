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

from django.db import models, connections, transaction
from datetime import date, time, datetime, timedelta
from servizi.utils import datetime2date, date2datetime, dateandtime2datetime, dictfetchall


def generic_batched_dbrotate(
		conn_s,
		conn_t,
		table_s,
		table_t,
		cutoff_date,
		sql_create_fields,
		ts_field,
		map_callback=None,
		job=None,
		dont_filter_timestamp=False,
	):
	"""
	Rotate a db table in a batched way

	conn_s: connection to source db
	conn_t: connection to target db
	table_s: source table name
	table_t: target table name
	cutoff_date: date up to which data is rotated
	sql_create_fields: create table command for target table (NOT INCLUDING "create table table_name")
	ts_field: name of the field containing timestamp
	job: job
	dont_filter_timestamp: don't restrict query by timestamp (e.g. if timestamps are not indexed), use a heuristic to filter

	map_callback: optional callback that map source row into target row

	map_callback receives a dict representing a source row as an input, and must return a dict representing a target row
	"""
	cursor = conn_s.cursor()
	esci = False
	batch_size = 50000

	while not esci:
		if dont_filter_timestamp:
			sql = "select * from " + table_s + " order by id limit " + str(batch_size)
			print sql
			cursor.execute(sql)
		else:
			sql = "select * from " + table_s + " where " + ts_field + " <= %s order by id limit " + str(batch_size)
			print sql
			cursor.execute(sql, cutoff_date)
		els = dictfetchall(cursor)

		if len(els) == 0:
			esci = True
			break

		tss = set()
		max_id = None

		for d in els:
			date = datetime2date(d[ts_field])
			if not date in tss:
				tss.add(date)

			if max_id is None or d['id'] > max_id:
				max_id = d['id']

			if dont_filter_timestamp and date > cutoff_date:
				esci = True

		print "Moving elements up to id %d" % max_id

		for ts in tss:
			table = "%(table)s_%(year)d_%(month)d" % {
				'table': table_t,
				'year': ts.year,
				'month': ts.month,
			}
			cursor_t = conn_t.cursor()

			sql = "	CREATE TABLE IF NOT EXISTS %(table)s %(sql_create_fields)s" % {
				'table': table,
				'sql_create_fields': sql_create_fields,
			}
			try:
				cursor_t.execute(sql)
			except Warning as w:
				print w

		for d in els:
			if map_callback is not None:
				d = map_callback(d)

			sql = "replace into %(table)s (%(fields)s) values (%(value_placeholders)s)" % {
				'table': table,
				'fields': ",".join(d.keys()),
				'value_placeholders': ','.join(["%s"] * len(d)),
			}

			# print sql
			cursor_t.execute(sql, d.values())

		print "Deleting old elements"
		sql = "delete from " + table_s + " where id <= %s"
		# print sql
		cursor.execute(sql, max_id)
		print "Committing storico"
		transaction.commit(using="storico")
		print "Committing live"
		transaction.commit()

		if job is not None:
			job.last_element_pk = max_id
			job.keep_alive()

		if len(els) < batch_size:
			esci = True



def generic_dbrotate(conn_s, conn_t, table_s, table_t, cutoff_date, sql_create_fields, ts_field, map_callback=None):
	"""
	Rotate a db table

	conn_s: connection to source db
	conn_t: connection to target db
	table_s: source table name
	table_t: target table name
	cutoff_date: date of to which data is rotated
	sql_create_fields: create table command for target table (NOT INCLUDING "create table table_name")
	ts_field: name of the field containing timestamp
	map_callback: optional callback that map source row into target row

	map_callback receives a dict representing a source row as an input, and must return a dict representing a target row
	"""
	cursor = conn_s.cursor()

	data_limite = date2datetime(datetime2date(cutoff_date))

	sql = "select * from " + table_s + " where date(" + ts_field + ") = %s"

	# print sql

	cursor.execute(sql, data_limite)

	table = "%(table)s_%(year)d_%(month)d" % {
		'table': table_t,
		'year': data_limite.year,
		'month': data_limite.month,
	}
	cursor_t = conn_t.cursor()

	sql = "	CREATE TABLE IF NOT EXISTS %(table)s %(sql_create_fields)s" % {
		'table': table,
		'sql_create_fields': sql_create_fields,
	}
	try:
		cursor_t.execute(sql)
	except Warning as w:
		print w

	for d in dictfetchall(cursor):

		if map_callback is not None:
			d = map_callback(d)

		sql = "replace into %(table)s (%(fields)s) values (%(value_placeholders)s)" % {
			'table': table,
			'fields': ",".join(d.keys()),
			'value_placeholders': ','.join(["%s"] * len(d)),
		}

		# print sql
		cursor_t.execute(sql, d.values())

	sql = "delete from " + table_s + " where date(" + ts_field + ") = %s"
	# print sql
	cursor.execute(sql, data_limite)


def get_data_limite(days):
	return date.today() - timedelta(days=days)