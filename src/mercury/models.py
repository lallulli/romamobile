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


from django.db import models, reset_queries
import rpyc
from rpyc.utils.server import ThreadedServer
import os, subprocess, signal
from threading import Thread
from Queue import Queue, Empty
import cPickle as pickle
from django.db.models import Q, F
from time import sleep
from datetime import date, time, datetime, timedelta
from contextlib import contextmanager
import random
import settings
import zlib as compressor

"""
Esempio 1: creazione di un servizio Operazioni
	class OperazioniListener(MercuryListener):
		@autopickle
		def exposed_somma(dict):
			return dict['a'] + dict['b']
	
	operazioni = PeerType.objects.get(name='operazioni') 
	m = Mercury(somma, OperazioniListener)


Esempio 2: creazione di un servizio Operazioni; registrazione demone e watchdog
	class OperazioniListener(MercuryListener):
		@autopickle
		def exposed_somma(dict):
			return dict['a'] + dict['b']
	
	operazioni = PeerType.objects.get(name='operazioni')
	operazioni_daemon = Daemon.get_process_daemon('operazioni_daemon')
	m = Mercury(operazioni, OperazioniListener, watchdog_daemon=operazioni_daemon)
	operazioni_daemon.set_ready()


Esempio 3: uso del proxy

Avvio del server proxy:
	python manage.py run_mercury_proxy MERCURY_PROXY_PORT
	
Uso come client del servizio peer_type:
	c = rpyc.connect(MERCURY_PROXY_HOST, MERCURY_PROXY_PORT)
	m = c.root.get_mercury_client(peer_type)
	# Chiamata sincrona:
	risultato = m.sync_any(metodo, parametri)
	# Chiamata asincrona:
	m.async_all(metodo, parametri)
	
"""

config = {
	'allow_public_attrs': True,
	'allow_pickle': True,
}


# Stores for large messages
class Store(object):
	"""
	A store object stores large data, as a mechanism to asynchronously call a remote method

	This is an abstract base class. A derived class must implement the following methods:
	- store(self, param, peer_type, method, id=None)
	- retrieve(self, peer_type, method, id=None), return retrieved param

	Moreover, mixins can implement the following methods to preprocess (encode) data:
	- encode(self, param): encode, call inherited encoders, and return encoded param
	- decode(self, param): call inherited decoders, decode and return decoded param
	"""
	def __init__(self):
		super(Store, self).__init__()

	def encode(self, param):
		try:
			param = super(Store, self).encode(param)
		except:
			pass
		return param

	def decode(self, param):
		try:
			param = super(Store, self).decode(param)
		except:
			pass
		return param


class PickleMixin(object):
	def __init__(self):
		super(PickleMixin, self).__init__()

	def encode(self, param):
		param = pickle.dumps(param, 2)
		try:
			param = super(PickleMixin, self).encode(param)
		except:
			pass
		return param

	def decode(self, param):
		try:
			param = super(PickleMixin, self).decode(param)
		except:
			pass
		return pickle.loads(param)


class CompressMixin(object):
	def __init__(self):
		super(CompressMixin, self).__init__()

	def encode(self, param):
		param = compressor.compress(param)
		try:
			param = super(CompressMixin, self).encode(param)
		except:
			pass
		return param

	def decode(self, param):
		try:
			param = super(PickleMixin, self).decode(param)
		except:
			pass
		return compressor.decompress(param)


class FileStore(PickleMixin, Store):
	def __init__(self, path='/tmp'):
		super(FileStore, self).__init__()
		self.path = path

	def _filename(self, peer_type, method, id):
		if id is None:
			id = ''
		return os.path.join(self.path, "%s_%s_%s" % (peer_type, method, id))

	def store(self, param, peer_type, method, id=None):
		fn = self._filename(peer_type, method, id)
		with open(fn, 'w') as f:
			param = self.encode(param)
			f.write(param)

	def retrieve(self, peer_type, method, id=None):
		fn = self._filename(peer_type, method, id)
		with open(fn) as f:
			return self.decode(f.read())


class CompressedFileStore(FileStore, CompressMixin):
	pass


# default_store = CompressedFileStore(settings.MERCURY_FILE_STORE_PATH)
default_store = FileStore(settings.MERCURY_FILE_STORE_PATH)


# Message broker

class PeerType(models.Model):
	name = models.CharField(max_length=31)
	max_queue_length = models.IntegerField(default=-1)
	min_port = models.IntegerField(blank=True, null=True, default=None)
	max_port = models.IntegerField(blank=True, null=True, default=None)
	
	def __unicode__(self):
		return self.name


class Route(models.Model):
	sender = models.ForeignKey(PeerType, related_name='fstar')
	receiver = models.ForeignKey(PeerType, related_name='bstar')
	active = models.BooleanField(default=True, blank=True)
	
	def __unicode__(self):
		return u"[%s] %s --> %s" % ('ON' if self.active else 'OFF', self.sender, self.receiver)


class Peer(models.Model):
	type = models.ForeignKey(PeerType)
	host = models.CharField(max_length=63)
	port = models.IntegerField()
	active = models.BooleanField(blank=True, default=True)
	blocked_until = models.DateTimeField(blank=True, null=True, db_index=True, default=None)
	daemon = models.ForeignKey('Daemon', blank=True, null=True, default=None)
	queue_length = models.IntegerField(default=0)
	
	def __unicode__(self):
		return "%s" % self.type

	@contextmanager
	def get_queue(self):
		try:
			print "Acquisico coda"
			self.queue_length = F('queue_length') + 1
			self.save()
			yield
		finally:
			print "Rilascio coda"
			self.queue_length = F('queue_length') - 1
			self.save()

	def get_receivers(self):
		out = Peer.objects.filter(
			Q(blocked_until__isnull=True) | Q(blocked_until=datetime.now()),
			type__bstar__sender=self,
			type__bstar__active=True,
			active=True
		).order_by('queue_length')
		return out
	
	@classmethod
	def get_receivers_static(cls, name):
		out = cls.objects.filter(
			Q(blocked_until__isnull=True) | Q(blocked_until=datetime.now()),
			type__bstar__sender__name=name,
			type__bstar__active=True,
			active=True
		).order_by('queue_length')
		return out

	def connect_any(self, by_queue=False):
		ss = list(self.get_receivers())

		if by_queue:
			l = ss[0].queue_length
			max_l = ss[0].type.max_queue_length
			if max_l != -1 and l > max_l:
				raise Exception("Servizio momentaneamente non disponibile")
			n = len(ss)
			i = 1
			while i < n and ss[i].queue_length == l:
				i += 1
			ss = ss[:i]

		random.shuffle(ss)
		for s in ss:
			try:
				c = rpyc.connect(s.host, s.port, config=config)
				c.peer = s
				return c
			except Exception:
				#s.bloccato = datetime.now()
				#s.save()
				pass
		return None

	@classmethod
	def connect_any_static(cls, name, by_queue=False):
		ss = list(cls.get_receivers_static(name))

		if by_queue:
			l = ss[0].queue_length
			max_l = ss[0].type.max_queue_length
			if max_l != -1 and l > max_l:
				raise Exception("Servizio momentaneamente non disponibile")
			n = len(ss)
			i = 1
			while i < n and ss[i].queue_length == l:
				i += 1
			ss = ss[:i]

		random.shuffle(ss)
		for s in ss:
			try:
				c = rpyc.connect(s.host, s.port, config=config)
				c.peer = s
				return c
			except Exception:
				#s.bloccato = datetime.now()
				#s.save()
				pass
		return None

	def connect_all(self):
		ss = self.get_receivers()
		cs = []
		for s in ss:
			try:
				c = rpyc.connect(s.host, s.port, config=config)
				c.peer = s
				cs.append(c)
			except Exception:
				s.bloccato = datetime.now()
				s.save()
		return cs
	
	@classmethod	
	def connect_all_static(cls, name):
		ss = cls.get_receivers_static(name)
		cs = []
		for s in ss:
			try:
				c = rpyc.connect(s.host, s.port, config=config)
				c.peer = s
				cs.append(c)
			except Exception:
				s.bloccato = datetime.now()
				s.save()
		return cs	


class MercuryWorker(Thread):
	def __init__(self, owner):
		Thread.__init__(self)
		self.owner = owner
		self.start()
		
	def run(self):
		exit = False
		while not exit:
			try:
				el = self.owner.queue.get()
				if el is not None:
					method = el['method']
					c = el['connection']
					getattr(c.root, method)(el['param'])
				else:
					exit = True
			except Exception:
				pass


class MercuryWatchdog(Thread):
	def __init__(self, owner, daem):
		Thread.__init__(self)
		self.owner = owner
		self.daem = daem
		self.start()
		
	def run(self):
		while True:
			try:
				c = rpyc.connect(self.owner.peer.host, self.owner.peer.port, config=config)
				assert(c.root.ping() == 'OK')
				c.close()
			except Exception:
				self.daem.action = 'R'
				self.daem.save()
			sleep(10)


class Watchdog(Thread):
	def __init__(self, name):
		Thread.__init__(self)
		self.name = name
		
	def run(self):
		while True:
			sleep(10)
			print "Watchdog cycle"
			ss = Peer.get_receivers_static(self.name)
			for s in ss:
				try:
					print "Testing"
					c = rpyc.connect(s.host, s.port, config=config)
					assert(c.root.ping() == 'OK')
					c.close()
					print "Test ok"
				except Exception, e:
					print e
					print "Test KO"
					if s.daemon is not None:
						s.daemon.action = 'R'
						s.daemon.save()
					print "Restart scheduled"


class Mercury(Thread):
	def __init__(self, type, listener=None, nworkers=3, daemon=None, watchdog_daemon=None, persistent_connection=False):
		Thread.__init__(self)
		self.queue = Queue()
		self.workers = [MercuryWorker(self) for i in range(nworkers)]
		if not isinstance(type, PeerType):
			type = PeerType.objects.get(name=type)
		port = 0
		if type.min_port is not None and type.max_port is not None:
			ports = set(range(type.min_port, type.max_port + 1))
			used_ports = set([p.port for p in Peer.objects.filter(type=type)])
			avail_ports = ports - used_ports
			r = random.Random()
			port = r.choice(list(avail_ports))
		self.type = type
		self.listener = listener
		if listener is not None:
			self.server = ThreadedServer(listener, port=port, protocol_config=config)
			self.peer = Peer(
				type=type,
				host=settings.LOCAL_IP,
				port=self.server.port,
				daemon=daemon,
			)
			self.peer.save()
			self.start()
		else:
			self.server = None
			self.peer = None
		self.watchdog = None
		if watchdog_daemon is not None:
			self.watchdog = MercuryWatchdog(self, watchdog_daemon)
		self.persistent_connection = persistent_connection
		if persistent_connection:
			self.connection = self.restore_connection()
		else:
			self.connection = None
		
	# API
	def async_all(self, method, param, replace=False):
		"""
		Call method asyncrouly on all receivers. Return immediately

		method: method name
		param: method parameter (only one parameter is allowed)
		replace: if True, cancel pending invocations of the same method, ad give priority of new invocations to clients
			for which pending invocations have been cancelled
		"""
		if self.peer is not None:
			cs = self.peer.connect_all()
		else:
			cs = Peer.connect_all_static(self.type.name)
		if replace:
			peers = {}
			for c in cs:
				peers[c.peer] = c
			prio = []
			q_new = []
			try:
				while True:
					el = self.queue.get(False)
					peer = el['connection'].peer
					if peer in peers and el['method'] == method:
						prio.append(peer)
					else:
						q_new.append(el)
			except Empty:
				pass
			cs = []
			for p in prio:
				cs.append(peers[p])
				del peers[p]
			for p in peers:
				cs.append(peers[p])
			for el in q_new:
				self.queue.put(el)
		dumped_param = pickle.dumps(param, protocol=2)
		for c in cs:
			self.queue.put({
				'connection': c,
				'method': method,
				'param': dumped_param,
			})

	def async_all_stored(self, method, param, id='', store=None):
		"""
		Call method asyncrouly on all receivers. Return immediately

		method: method name
		param: method parameter (only one parameter is allowed)
		replace: if True, cancel pending invocations of the same method, ad give priority of new invocations to clients
			for which pending invocations have been cancelled
		"""
		if store is None:
			store = default_store
		if self.peer is not None:
			cs = self.peer.connect_all()
			peer_type = self.peer.type.name
		else:
			cs = Peer.connect_all_static(self.type.name)
			peer_type = self.type.name
		sent_param = {
			'peer_type': peer_type,
			'method': method,
			'id': id,
		}
		dumped_param = pickle.dumps(sent_param, protocol=2)
		store.store(param, peer_type, method, id)

		for c in cs:
			self.queue.put({
				'connection': c,
				'method': method,
				'param': dumped_param,
			})

	def restore_connection(self):
		if self.peer is not None:
			self.connection = self.peer.connect_any()
		else:
			self.connection = Peer.connect_any_static(self.type.name)

	def sync_any(self, method, param, by_queue=False):
		if self.persistent_connection:
			try:
				return pickle.loads(getattr(self.connection.root, method)(pickle.dumps(param, 2)))
			except:
				self.restore_connection()
				return pickle.loads(getattr(self.connection.root, method)(pickle.dumps(param, 2)))
		else:
			if self.peer is not None:
				c = self.peer.connect_any(by_queue)
			else:
				c = Peer.connect_any_static(self.type.name, by_queue)
			return pickle.loads(getattr(c.root, method)(pickle.dumps(param, 2)))
	
	@classmethod
	def sync_any_static(cls, name, method, param, by_queue=False):
		c = Peer.connect_any_static(name, by_queue)
		return pickle.loads(getattr(c.root, method)(pickle.dumps(param, 2)))
	
	def rpyc_connect_any(self, by_queue=False):
		if self.peer is not None:
			c = self.peer.connect_any(by_queue)
		else:
			c = Peer.connect_any_static(self.type.name, by_queue)
		return c
	
	def rpyc_connect_all(self):
		if self.peer is not None:
			cs = self.peer.connect_all()
		else:
			cs = Peer.connect_all_static(self.type.name)
		return cs
	
	@classmethod
	def rpyc_connect_any_static(cls, name, by_queue=False):
		return Peer.connect_any_static(name, by_queue)

	@classmethod
	def rpyc_connect_all_static(cls, name):
		return Peer.connect_all_static(name)	
	
	def close(self):
		if self.peer is not None:
			self.peer.delete()
		if self.server is not None:
			self.server.close()
		for w in self.workers:
			self.queue.put(None)
		
	def run(self):
		print "Server listening"
		self.server.start()
		print "Server closed"


def autopickle(f):
	def g(self, param):
		return pickle.dumps(f(self, pickle.loads(param)), 2)
	return g


def autostored(store=None):
	if store is None:
		store = default_store
	def deco(f):
		def g(self, sent_param):
			sent_param = pickle.loads(sent_param)
			param = store.retrieve(sent_param['peer_type'], sent_param['method'], sent_param['id'])
			return pickle.dumps(f(self, param), 2)
		return g
	return deco


def queued(daemon):
	def deco(f):
		def g(*args, **kwargs):
			peer = Peer.objects.filter(daemon=daemon)[0]
			with peer.get_queue():
				return f(*args, **kwargs)
		return g
	return deco

class MercuryListener(rpyc.Service):
	def exposed_ping(self):
		return 'OK'
	
class MercuryProxy(MercuryListener):
	def exposed_delete_mercury_clients(self, type):
		Peer.objects.filter(type__name=type).delete()
	
	def exposed_get_mercury_client(self, type):
		return Mercury(PeerType.objects.get(name=type), None)
	
	
# Daemon management

control_action_choices = [
	('N', 'Normal mode'),
	('F', 'Freeze current state'),
	('S', 'Stop all (do not restart)'),
	('R', 'Restart all'),
]


class DaemonControl(models.Model):
	name = models.CharField(max_length=31, db_index=True, unique=True)
	instances = models.IntegerField()
	restart_from = models.TimeField()
	restart_to = models.TimeField()
	restart_timeout = models.IntegerField()
	max_restart_time = models.IntegerField(default=3)
	command = models.CharField(max_length=1023)
	action = models.CharField(max_length=1, default='F', choices=control_action_choices)

	@contextmanager
	def suspend_all_daemons(self):
		print "Closing existing daemons"
		old_action = self.action
		self.action = 'F'
		self.save()
		ss_istanziati = self.daemon_set.all()
		for s in ss_istanziati:
			print "Chiudo il processo ", self.name, s.pid
			try:
				os.kill(s.pid, signal.SIGTERM)
			except Exception:
				pass
			s.delete()
		print "All existing daemons closed"
		yield
		print "Restoring old daemon status"
		self.action = old_action
		self.save()

	def restart_all_daemons(self, force=False):
		"""
		Restart all daemons

		:param force: if True, restart even if nor running in normal mode
		"""
		if force or self.action == 'N':
			self.action = 'R'
			self.save()

	def __unicode__(self):
		return self.name


daemon_action_choices = [
	('N', 'Normal mode'),
	('F', 'Freeze (suspend restart)'),
	('R', 'Restart'),
]


class Daemon(models.Model):
	control = models.ForeignKey(DaemonControl)
	active_since = models.DateTimeField(db_index=True, auto_now_add=True)
	ready = models.BooleanField(blank=True, default=False)
	pid = models.IntegerField(default=-1)
	action = models.CharField(max_length=1, default='N', choices=daemon_action_choices)
	number = models.IntegerField(blank=True, null=True, default=None)

	@classmethod
	def get_process_daemon(cls, name, in_docker):
		if in_docker:
			try:
				return cls.objects.get(control__name=name)
			except cls.DoesNotExist:
				dc = DaemonControl.objects.get(name=name)
				d = cls(control=dc)
				d.save()
				return d
		return cls.objects.get(control__name=name, pid=os.getpid()) 
	
	def set_ready(self):
		self.ready = True
		self.save()
	
	def __unicode__(self):
		return u"[%s] %s (%s)" % (self.active_since, self.control, self.pid)

	def save(self, *args, **kwargs):
		if self.number is None:
			ds = Daemon.objects.filter(control=self.control)
			s = set([d.number for d in ds if d.number is not None])
			i = 1
			while i in s:
				i += 1
			self.number = i
		super(Daemon, self).save(*args, **kwargs)


class Node(models.Model):
	"""
	An execution node for jobs, i.e., a physical or virtual machine
	"""
	name = models.CharField(max_length=31)

	def __unicode__(self):
		return self.name


job_action_choices = [
	('N', 'Normal mode (auto execution)'),
	('F', 'Force execution, then go to normal'),
	('O', 'Force execution once, then stop'),
	('S', 'Stopped'),
]


class Job(models.Model):
	node = models.ForeignKey(Node)
	function = models.CharField(max_length=63, help_text="""
		Function to be called, with format: "app.function".
		Function function must be defined in file app/jobs.py, and take a Job instance as a parameter.
	""")
	start_ts = models.DateTimeField(blank=True, null=True, default=None)
	stop_ts = models.DateTimeField(blank=True, null=True, default=None)
	completed_ts = models.DateTimeField(blank=True, null=True, default=None)
	keepalive_ts = models.DateTimeField(blank=True, null=True, default=None)
	timeout_minutes = models.IntegerField(default=10)
	last_status = models.IntegerField(default=0) # UNIX-like: 0 is ok, > 0 is error
	last_message = models.CharField(max_length=2047, blank=True, default='')
	completion = models.FloatField(blank=True, null=True, default=None)
	last_element_ts = models.DateTimeField(blank=True, null=True, default=None)
	last_element_pk = models.IntegerField(blank=True, null=True, default=None)
	action = models.CharField(max_length=1, default='S', choices=job_action_choices)
	sched_hour = models.CharField(max_length=63, default='*')
	sched_minute = models.CharField(max_length=63, default='*')
	sched_dow = models.CharField(max_length=31, default='*')
	sched_dom = models.CharField(max_length=63, default='*')
	sched_moy = models.CharField(max_length=63, default='*')

	def __unicode__(self):
		return self.function

	def keep_alive(self, completion=None):
		self.completion = completion
		self.keepalive_ts = datetime.now()
		self.save()
		reset_queries()
