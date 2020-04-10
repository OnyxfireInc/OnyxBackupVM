#!/usr/bin/env python

# part of OnyxBackupVM
# Copyright (c) 2017-2020 OnyxFire, Inc.
	
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from logging import getLogger
import XenAPI

class DataAPI(object):

	def __init__(self):
		self.logger = getLogger(__name__)
		self._api = '2.7'
		self._program = 'OnyxBackupVM'

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
