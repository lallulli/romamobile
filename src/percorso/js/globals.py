from __pyjamas__ import JS

flavors = ['app', 'web']
flavor_id = JS("""$wnd.flavor_id""")
flavor = flavors[flavor_id]

version = '2.8'

web_prefix = 'https://romamobile.it'
base_url = [web_prefix, ''][flavor_id]


def make_absolute(url):
	if not url.startswith('https://'):
		return base_url + url
	return url


users = [None]
controls = [None]


def set_user(u):
	users[0] = u


def get_user():
	return users[0]


def set_control(c):
	controls[0] = c


def get_control():
	return controls[0]


def android():
	if flavor == 'web':
		return False
	return True
	# platform = JS("""$wnd.window.device.platform""")
	# return platform == 'Android'


def old_android():
	return False
	# if flavor == 'web':
	# 	return False
	# platform = JS("""$wnd.window.device.platform""")
	# if platform != "Android":
	# 	return False
	# version = JS("""$wnd.window.device.version""")
	# v = version.split(".")[0]
	# if not v.isdigit():
	# 	return False
	# return int(v) < 4


def ios():
	return False
	# if flavor == 'web':
	# 	return False
	# platform = JS("""$wnd.window.device.platform""")
	# return platform == "iOS"


def get_os():
	if flavor == 'web':
		return 'web'
	elif old_android():
		return 'android-old'
	elif android():
		return 'android'
	else:
		return 'ios'
