#!/usr/bin/env python

# part of OnyxBackup-XS
# Copyright (c) 2018 OnyxFire, Inc.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from logging import getLogger
import XenAPI

class DataAPI(object):

	def __init__(self):
		self.logger = getLogger(__name__)
		self._api = '2.7'
		self._program = 'OnyxBackup'

	def get_api_version(self):
		self.login()
		try:
			pool = self._session.xenapi.pool.get_all()[0]
			host = self._session.xenapi.pool.get_master(pool)
			major_version = self._session.xenapi.host.get_API_version_major(host)
			minor_version = self._session.xenapi.host.get_API_version_minor(host)
			api_version = '{}.{}'.format(major_version, minor_version)
			self.logger.debug('(i) -> API version: {}'.format(api_version))
		finally:
			self.logout()
		return api_version

	def get_master(self):
		self.login()
		try:
			pool = self._session.xenapi.pool.get_all()[0]
			host = self._session.xenapi.pool.get_master(pool)
			host_record = self._session.xenapi.host.get_record(host)
			master = host_record['address']
			self.logger.debug('(i) -> Master address: {}'.format(master))
		finally:
			self.logout()
		return master

	def get_network_record(self, network):
		self.login()
		try:
			self.logger.debug('(i) -> Getting record for Network: {}'.format(network))
			network_record = self._session.xenapi.network.get_record(network)
		finally:
			self.logout()
		return network_record

	def get_sr_record(self, sr):
		self.login()
		try:
			self.logger.debug('(i) -> Getting record for SR: {}'.format(sr))
			sr_record = self._session.xenapi.SR.get_record(sr)
		finally:
			self.logout()
		return sr_record

	def get_vbd_record(self, vbd):
		self.login()
		try:
			self.logger.debug('(i) -> Getting record for VBD: {}'.format(vbd))
			vbd_record = self._session.xenapi.VBD.get_record(vbd)
		finally:
			self.logout()
		return vbd_record

	def get_vdi_record(self, vdi):
		self.login()
		try:
			self.logger.debug('(i) -> Getting record for VDI: {}'.format(vdi))
			vdi_record = self._session.xenapi.VDI.get_record(vdi)
		finally:
			self.logout()
		return vdi_record

	def get_vif_record(self, vif):
		self.login()
		try:
			self.logger.debug('(i) -> Getting record for VIF: {}'.format(vif))
			vif_record = self._session.xenapi.VIF.get_record(vif)
		finally:
			self.logout()
		return vif_record

	def get_vm_by_name(self, vm_name):
		self.login()
		try:
			self.logger.debug('(i) -> Getting VM object: {}'.format(vm_name))
			vm = self._session.xenapi.VM.get_by_name_label(vm_name)
			return vm
		finally:
			self.logout()
		return vm

	def get_vm_record(self, vm):
		self.login()
		try:
			self.logger.debug('(i) -> Getting record for VM: {}'.format(vm))
			vm_record = self._session.xenapi.VM.get_record(vm)
		finally:
			self.logout()
		return vm_record

	def login(self):
		raise NotImplementedError('(!) Must be implemented in subclass')

	def logout(self):
		self.logger.debug('(i) -> Logging out of session')
		self._session.xenapi.session.logout()

	def vm_exists(self, vm_name):
		self.login()
		try:
			self.logger.debug('(i) -> Checking if vm exists: {}'.format(vm_name))
			vm = self._session.xenapi.VM.get_by_name_label(vm_name)
			if ( len(vm) == 0 ):
				return False
			else:
				return True
		finally:
			self.logout()

class XenLocal(DataAPI):

	def __init__(self):
		super(self.__class__, self).__init__()
		self._username = 'root'
		self._password = ''
		self._session = XenAPI.xapi_local()

	def login(self):
		self.logger.debug('(i) -> Logging in to get local session')
		self._session.xenapi.login_with_password(self._username, self._password, self._api, self._program)

class XenRemote(DataAPI):

	def __init__(self, username, password, url):
		super(self.__class__, self).__init__()
		self._username = username
		self._password = password
		self._url = url
		self._session = XenAPI.Session('https://' + self._url)

	def login(self):
		self.logger.debug('(i) -> Logging in to get remote session')
		try:
			self._session.xenapi.login_with_password(self._username, self._password, self._api, self._program)
		except XenAPI.Failure as e:
			if e.details[0] == 'HOST_IS_SLAVE':
				self.logger.warning('(!) Host is slave: {}'.format(self._url))
				self._url = 'https://' + e.details[1]
				self.logger.info('-> Trying master from response: {}'.format(e.details[1]))
				self._session = XenAPI.Session(self._url)
				self._session.xenapi.login_with_password(self._username, self._password, self._api, self._program)
			else:
				raise