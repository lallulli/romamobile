import socket
import rpyc
import traceback
from time import sleep
from datetime import date, time, datetime, timedelta
from django.core.management.base import BaseCommand, CommandError
import settings
from mercury.models import Mercury

RESTART_TIMEOUT = timedelta(minutes=2)
peer_type = 'romatpl'

# A UDP server
# Set up a UDP server
UDPSock = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)

# Listen on port
# (to all IP addresses on this system)
listen_addr = ("", PORT)
UDPSock.bind(listen_addr)

class Command(BaseCommand):
	args = """Nessun argomento"""
	help = 'Decoder flusso dati AVM RomaTPL'

	def handle(self, *args, **options):
		while True:
			try:
				# Setup mercury client
				now = datetime.now()

				# Report on all data packets received and
				# where they came from in each case (as this is
				# UDP, each may be from a different source and it's
				# up to the server to sort this out!)
				while True:
					data,addr = UDPSock.recvfrom(1024)
					ds = data.strip()
					msg = {
						'id_vettura': ds[0:5].strip(),
						'num_tel': ds[5:19],
						'tipo_mess': ds[19:22],
						'tipo_evento': ds[22:24],
						'dataora': datetime.strptime(ds[24:38], "%Y%m%d%H%M%S"),
						'tipo_fix': ds[41:42],
						'lat': float(ds[42:51].replace(",", ".")),
						'lon': float(ds[52:61].replace(",", ".")),
						'progressivo_msg': ds[61:68],
						'msg_da_ultimo_zn': ds[67:70],
						'reason': ds[70:72],
						'dataorazn': ds[72:86],
						'latzn': ds[86:95],
						'lonzn': ds[95:105],
						'id_percorso': ds[105:111].strip(),
						'prog_nodo_percorso': int(ds[111:114]),
						'id_fermata': ds[114:120],
						'nsecdazn_1': ds[120:126],
						'metri_da_zn_1': ds[126:132],
						'velocita_servizio': ds[132:135],
						'velocita_trasferimento': ds[135:138],
						'velocita_linea': ds[138:141],
						'numero_fermate_vl': ds[141:144],
						'numero_passeggeri': ds[144:147],
						'carico_passeggeri': ds[147:150],
						'cartellino': ds[150:156],
						'corsa': ds[156:162],
						'id_linea_zn': ds[162:168],
						'id_linea_attuale': ds[168:174],
						'modalita': ds[174:177],
						'metri_da_zn': ds[177:183],
						'targa_percorso': ds[183:189],
						'metri_da_reset': ds[189:195],
					}
					# print msg['id_vettura'], msg['tipo_evento'], msg['dataora'], msg['id_fermata'], msg['metri_da_zn'], msg['metri_da_zn_1'], msg['lat'], msg['lon'], msg['id_linea_attuale']
					# Chiamata asincrona:
					if msg['tipo_evento'] in ['ZN', 'KA', 'KN']:
						Mercury.sync_all_static(peer_type, 'dati_da_avm_romatpl', {
							'timestamp': msg['dataora'],
							'progressiva': msg['prog_nodo_percorso'],
							'id_percorso': msg['id_percorso'],
							'id_veicolo': msg['id_vettura'],
							'lon': msg['lon'],
							'lat': msg['lat'],
							'numero_passeggeri': msg['numero_passeggeri'],
							'carico_passeggeri': msg['carico_passeggeri'],
						})
						try:
							Mercury.sync_all_static(peer_type, 'log_dati_avm_romatpl', msg)
						except:
							pass

			except Exception, e:
				print traceback.format_exc()
				sleep(5)
