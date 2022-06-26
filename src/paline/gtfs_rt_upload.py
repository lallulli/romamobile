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

import paramiko
import settings


def createSSHClient(server, user, password, port=22):
	client = paramiko.SSHClient()
	client.load_system_host_keys()
	client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
	client.connect(server, port, user, password)
	return client



def gtfs_realtime_uploader(g):
	with open("gtfs_rt.txt", "w") as f:
		f.write(str(g))
	with open("gtfs_rt.bin", "w") as f:
		f.write(g.SerializeToString())

	ssh = createSSHClient(settings.WEBSERVER_HOST, settings.WEBSERVER_USER, settings.WEBSERVER_PASSWORD)
	sftp = paramiko.SFTPClient.from_transport(ssh.get_transport())
	sftp.put('./gtfs_rt.txt', '/gtfs_rt.txt')
	sftp.put('./gtfs_rt.bin', '/gtfs_rt.bin')
	sftp.close()
	ssh.close()


