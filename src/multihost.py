##
# A simple middleware component that lets you use a single Django
# instance to server multiple distinct hosts.
##

from django.conf import settings
from django.utils.cache import patch_vary_headers

class MultiHostMiddleware:

	def process_request(self, request):
		try:
			host = request.META["HTTP_HOST"]
			i = host.find(':')
			if i > -1:
				host = host[:i] # ignore port number, if present
			request.urlconf = settings.HOST_MIDDLEWARE_URLCONF_MAP[host]
		except KeyError:
			pass # use default urlconf (settings.ROOT_URLCONF)

	def process_response(self, request, response):
		if getattr(request, "urlconf", None):
			patch_vary_headers(response, ('Host',))
		return response