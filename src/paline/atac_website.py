# coding: utf-8
# Written by Luca Allulli

import requests
from BeautifulSoup import BeautifulStoneSoup
from pprint import pprint


def get_atac_buses_viaggiaconatac(id_palina):
	r = requests.get("http://viaggiacon.atac.roma.it/asp/orariFermata.asp?impianto={}".format(id_palina))
	soup = BeautifulStoneSoup(r.text, fromEncoding='iso-8859-1')
	fermate = soup.findAll('fermata')
	out = []
	for f in fermate:
		print "Dentro"
		linea = f.linea.text
		msg = f.mesg.text.lower()
		if "arrivo" in msg:
			d = 0
		elif "capolinea" in msg:
			d = None
		else:
			d = int(msg[:msg.find(' ')])
		out.append((linea, d))
	return out


if __name__ == '__main__':
	o = get_atac_buses_viaggiaconatac("70100")
	pprint(o)
