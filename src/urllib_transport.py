import urllib2
import xmlrpclib

class UrllibTransport(xmlrpclib.Transport):

	def request(self, host, handler, request_body, verbose=0):
		
		self.verbose=verbose
		url='http://'+host+handler
		if self.verbose: "ProxyTransport URL: [%s]"%url

		request = urllib2.Request(url)
		request.add_data(request_body)
		# Note: 'Host' and 'Content-Length' are added automatically
		request.add_header("User-Agent", self.user_agent)
		request.add_header("Content-Type", "text/xml") # Important

		proxy_handler=urllib2.ProxyHandler()
		opener=urllib2.build_opener(proxy_handler)
		f=opener.open(request)
		return(self.parse_response(f))
