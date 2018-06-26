#!/usr/bin/env python

# part of OnyxBackupVM
# Copyright (c) 2018 OnyxFire, Inc.
	
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

import datetime, re
from logging import getLogger
from os import listdir
from os.path import getmtime, join
from collections import OrderedDict
import onyxbackup.data as data
import onyxbackup.util as util

class XenApiService(object):

	def __init__(self, config):
		self.logger = getLogger(__name__)
		self.config = config
		self._h = util.Helper()
		self._d = data.XenLocal()
		self._xe_path = '/opt/xensource/bin'

	# API Functions

	def backup_hosts(self):
		"""
			Run backup of pool hosts utilizing host-backup
		"""
		self._start_function('HOST-BACKUP')

		all_hosts = self._get_all_hosts()
		if not all_hosts:
			self.logger.info('-> Skipping hosts backup due to error')
			self._stop_function()
			return

		for host in all_hosts:
			self._start_task(host)
			skip_message = '-> Skipping host backup due to error'
			host_dir = 'HOST_' + host
			host_backup_dir = join(self.config['backup_dir'], host_dir)
			backup_file = '{}/host_{}.xbk'.format(host_backup_dir, self._h.get_date_string())
			self.logger.debug('(i) Backup file: {}'.format(backup_file))

			if not self._check_backup_space():
				self.logger.info(skip_message)
				self._stop_task()
				continue

			if not self._verify_backup_dir(host_backup_dir):
				self.logger.info(skip_message)
				self._stop_task()
				continue

			if not self._export_to_file(host, backup_file, 'host'):
				self.logger.info(skip_message)
				self._stop_task()
				continue

			self._rotate_backups(self.config['max_backups'], host_backup_dir, False)
			self._add_status('success')
			self._stop_task()
		self._stop_function()

	def backup_pool_db(self):
		"""
			Run backup of pool metadata utilizing pool-dump-database
		"""
		self._start_function('POOL-BACKUP')
		skip_message = '-> Skipping pool metadata backup due to error'
		db_backup_dir = join(self.config['backup_dir'], 'POOL_DB')
		backup_file = '{}/metadata_{}.db'.format(db_backup_dir, self._h.get_date_string())
		self.logger.debug('(i) Backup file: {}'.format(backup_file))

		if not self._check_backup_space():
			self.logger.info(skip_message)
			self._stop_function()
			return

		if not self._verify_backup_dir(db_backup_dir):
			self.logger.info(skip_message)
			self._stop_function()
			return

		if not self._export_to_file(None, backup_file, 'pool'):
			self.logger.info(skip_message)
			self._stop_function()
			return

		self._rotate_backups(self.config['max_backups'], db_backup_dir, False)
		self._add_status('success')
		self._stop_function()

	def backup_vdi(self):
		"""
			Run backups of just configured VM disks utilizing vdi-export
		"""
		self._start_function('VDI-EXPORT')
		skip_message = '-> Skipping VM due to error'
		skip_message_disk = '-> Skipping disk due to error'
		vms = self.config['vdi_exports']
		self.logger.debug('(i) VMs: {}'.format(vms))

		if vms == []:
			self._add_status('error', '(!) No VMs selected for vdi-export')
			self._stop_function()
			return

		for value in vms:
			values = value.split(':')
			vm_name = values[0]
			vm_backups = self.config['max_backups']
			vdi_disks = ['xvda']
			if (len(values) > 1) and not (values[1] == '-1'):
				vm_backups = int(values[1])
			if len(values) == 3:
				vdi_disks[:] = []
				vdi_disks += values[2].split(';')

			self._start_task(vm_name)
			self.logger.debug('(i) Name:{} Max-Backups:{} Disks:{}'.format(vm_name, vm_backups, vdi_disks))

			if not vdi_disks:
				self._add_status('error', '(!) No disks selected for backup')
				self.logger.info(skip_message)
				continue
			
			if not self._check_backup_space():
				self.logger.info(skip_message)
				self._stop_task()
				continue

			vm_object = self._get_vm_by_name(vm_name)
			if not vm_object:
				self.logger.info(skip_message)
				self._stop_task()
				continue

			vm_backup_dir = join(self.config['backup_dir'], vm_name)

			if not self._verify_backup_dir(vm_backup_dir):
				self.logger.info(skip_message)
				self._stop_task()
				continue

			vm_meta = self._get_vm_record(vm_object)
			if not vm_meta:
				self.logger.info(skip_message)
				self._stop_task()
				continue

			for disk in vdi_disks:
				self._start_subtask(disk)

				base = '{}/backup_{}_{}'.format(vm_backup_dir, disk, self._h.get_date_string())
				meta_backup_file = '{}.meta'.format(base)
				self.logger.debug('(i) meta_backup_file: {}'.format(meta_backup_file))
				backup_file = '{}.{}'.format(base, self.config['vdi_export_format'])
				self.logger.debug('(i) backup_file: {}'.format(backup_file))
				
				if not self._check_backup_space():
					self.logger.info(skip_message_disk)
					self._stop_subtask()
					continue

				vdi_data = self._backup_meta(vm_meta, meta_backup_file)
				if not vdi_data:
					self.logger.info(skip_message_disk)
					self._stop_subtask()
					continue

				self.logger.info('> Verifying disk is valid')
				if disk in vdi_data:
					vdi_uuid = vdi_data[disk]
				else:
					self._add_status('error', '(!) Invalid device specified')
					self._h.delete_file(meta_backup_file)
					self.logger.info(skip_message_disk)
					self._stop_subtask()
					continue

				if not self._cleanup_snapshot(vdi_uuid, 'vdi'):
					self._h.delete_file(meta_backup_file)
					self.logger.info(skip_message_disk)
					self._stop_subtask()
					continue

				snap_uuid = self._snapshot(vdi_uuid, 'vdi')
				if not snap_uuid:
					self._h.delete_file(meta_backup_file)
					self.logger.info(skip_message_disk)
					self._stop_subtask()
					continue

				if not self._prepare_snapshot(snap_uuid, 'vdi'):
					self._destroy_snapshot(snap_uuid, 'vdi')
					self._h.delete_file(meta_backup_file)
					self.logger.info(skip_message_disk)
					self._stop_subtask()
					continue

				if not self._export_to_file(snap_uuid, backup_file, 'vdi'):
					self._destroy_snapshot(snap_uuid, 'vdi')
					self._h.delete_file(meta_backup_file)
					self.logger.info(skip_message_disk)
					self._stop_subtask()
					continue

				self._destroy_snapshot(snap_uuid, 'vdi')
				self._rotate_backups(vm_backups, vm_backup_dir)
				self._add_status('success')
				self._stop_subtask()
			self._stop_task()
		self._stop_function()

	def backup_vm(self):
		"""
			Run full backups of VMs utilizing vm-export
		"""
		self._start_function('VM-EXPORT')
		skip_message = '-> Skipping VM due to error'
		vms = self.config['vm_exports']
		self.logger.debug('(i) VMs: {}'.format(vms))

		if vms == []:
			self._add_status('error', '(!) No VMs selected for vm-export')
			self._stop_function()
			return

		for value in vms:
			values = value.split(':')
			vm_name = values[0]
			vm_backups = self.config['max_backups']
			if (len(values) > 1) and not (values[1] == '-1'):
				vm_backups = int(values[1])
			snapshot_type = 'vm'

			self._start_task(vm_name)
			self.logger.debug('(i) Name:{} Max-Backups:{}'.format(vm_name, vm_backups))

			vm_backup_dir = join(self.config['backup_dir'], vm_name)			
			base = '{}/backup_{}'.format(vm_backup_dir, self._h.get_date_string())
			meta_backup_file = '{}.meta'.format(base)
			self.logger.debug('(i) meta_backup_file:{}'.format(meta_backup_file))
			if self.config['compress']:
				backup_file = '{}.xva.gz'.format(base)
			else:
				backup_file = '{}.xva'.format(base)
			self.logger.debug('(i) backup_file:{}'.format(backup_file))

			if not self._check_backup_space():
				self.logger.info(skip_message)
				self._stop_task()
				continue

			vm_object = self._get_vm_by_name(vm_name)
			if not vm_object:
				self.logger.info(skip_message)
				self._stop_task()
				continue

			if not self._verify_backup_dir(vm_backup_dir):
				self.logger.info(skip_message)
				self._stop_task()
				continue

			vm_meta = self._get_vm_record(vm_object)
			if not vm_meta:
				self.logger.info(skip_message)
				self._stop_task()
				continue

			if self._is_windows_vm(vm_meta['uuid'])
				if self._is_quiesce_enabled(vm_meta):
					snapshot_type = 'vm-vss'

			if not self._backup_meta(vm_meta, meta_backup_file):
				self.logger.info(skip_message)
				self._stop_task()
				continue

			if not self._cleanup_snapshot(vm_meta['uuid']):
				self.logger.info(skip_message)
				self._stop_task()
				continue

			snap_uuid = self._snapshot(vm_meta['uuid'])
			if not snap_uuid:
				self._h.delete_file(meta_backup_file)
				self.logger.info(skip_message)
				self._stop_task()
				continue

			if not self._prepare_snapshot(snap_uuid):
				self._destroy_snapshot(snap_uuid)
				self._h.delete_file(meta_backup_file)
				self.logger.info(skip_message)
				self._stop_task()
				continue

			if not self._export_to_file(snap_uuid, backup_file, snapshot_type):
				self._uninstall_vm(snap_uuid)
				self._h.delete_file(meta_backup_file)
				self.logger.info(skip_message)
				self._stop_task()
				continue

			self._uninstall_vm(snap_uuid)
			self._rotate_backups(vm_backups, vm_backup_dir)
			self._add_status('success')
			self._stop_task()
		self._stop_function()

	def process_vm_lists(self):
		"""
			Aggregate lists of VMs configured and run specified actions on them
		"""
		vm_lists = OrderedDict()
		vm_lists['excludes'] = self.config['excludes']
		vm_lists['vdi_exports'] = self.config['vdi_exports']
		vm_lists['vm_exports'] = self.config['vm_exports']
		self._validate_vm_lists(vm_lists)

	def send_email(self):
		"""
			Send email to configured recipient containing the report from
			the current backup
		"""
		import smtplib
		from email.mime.text import MIMEText

		smtp_file = self.config['smtp_file']
		smtp_server = self.config['smtp_server']
		smtp_port = self.config['smtp_port']
		smtp_hostname = self.config['smtp_hostname']
		smtp_timeout = self.config['smtp_timeout']
		smtp_subject = self.config['smtp_subject']
		smtp_from = self.config['smtp_from']
		smtp_to = self.config['smtp_to']

		try:
			print('')
			self.logger.debug('(i) Opening email report file: {}'.format(smtp_file))
			with open(smtp_file) as fp:
				self.logger.debug('(i) Building text/plain email message from file')
				msg = MIMEText(fp.read())
				msg['Subject'] = smtp_subject
				msg['From'] = smtp_from
				msg['To'] = smtp_to

			self.logger.debug('(i) Creating SMTP instance')
			s = smtplib.SMTP(smtp_server,smtp_port,smtp_hostname,smtp_timeout)
			self.logger.debug('(i) Sending EHLO')
			s.ehlo()
			if self.config['smtp_starttls']:
				self.logger.debug('(i) Enabling starttls for email')
				s.starttls()
				s.ehlo()
			if self.config['smtp_auth']:
				self.logger.debug('(i) Logging in as {}'.format(self.config['smtp_user']))
				s.login(self.config['smtp_user'], self.config['smtp_pass'])

			self.logger.debug('(i) Sending email report to {}'.format(smtp_to))
			s.sendmail(smtp_from, [smtp_to], msg.as_string())
			s.quit()
		except SMTPException as e:
			self.logger.error('(!) Email report failed to send: {}'.format(str(e)))

	# Private Functions

	def _add_status(self, status_type, message=''):
		"""
			Update status counts of the given type and log given message
			at appropriate level for the given type
		"""
		if status_type == 'error':
			self.logger.error(message)
		elif status_type == 'warning':
			self.logger.warning(message)
		elif status_type == 'critical':
			self.logger.critical(message)
		elif status_type == 'success':
			self.logger.debug('(i) Job completed successfully')
		else:
			self.logger.error('{} is not a valid status, defaulting to error'.format(status_type))
			self._add_status('error', message)
			return
		self.status[status_type] += 1

	def _backup_meta(self, vm, file):
		"""
			Backup VM metadata of the given VM to given file
			
			@return Dictionary of VDIs {device-name:vdi-uuid} or False if failed
		"""
		self.logger.info('> Backing up VM metadata')
		vdi_data = {}

		try:
			self.logger.debug('(i) -> Opening metadata file for writing')
			with open(file, 'w') as meta_out:
				meta_out.write('******* VM *******\n')
				meta_out.write('name_label={}\n'.format(vm['name_label']).encode('utf8'))
				meta_out.write('name_description={}\n'.format(vm['name_description']).encode('utf8'))
				meta_out.write('memory_dynamic_max={}\n'.format(vm['memory_dynamic_max']))
				meta_out.write('VCPUs_max={}\n'.format(vm['VCPUs_max']))
				meta_out.write('VCPUs_at_startup={}\n'.format(vm['VCPUs_at_startup']))
				if vm['other_config']['base_template_name']:
					meta_out.write('base_template_name={}\n'.format(vm['other_config']['base_template_name']))
				meta_out.write('os_version={}\n'.format(self._get_os_version(vm['uuid'])))
				meta_out.write('orig_uuid={}\n'.format(vm['uuid']))
				meta_out.write('\n')

				for vbd in vm['VBDs']:
					vbd_record = self._d.get_vbd_record(vbd)
					if vbd_record['type'].lower() != 'disk':
						self.logger.debug('(i) -> Not a data disk... skipping: {}'.format(vbd_record['type']))
						continue

					vdi_record = self._d.get_vdi_record(vbd_record['VDI'])
					self.logger.debug('(i) Storing VDI metadata: {}:{}'.format(vbd_record['device'], vdi_record['uuid']))
					vdi_data[vbd_record['device']] = vdi_record['uuid']

					meta_out.write('******* DISK *******\n')
					meta_out.write('device={}\n'.format(vbd_record['device']))
					meta_out.write('userdevice={}\n'.format(vbd_record['userdevice']))
					meta_out.write('bootable={}\n'.format(vbd_record['bootable']))
					meta_out.write('mode={}\n'.format(vbd_record['mode']))
					meta_out.write('type={}\n'.format(vbd_record['type']))
					meta_out.write('unpluggable={}\n'.format(vbd_record['unpluggable']))
					meta_out.write('empty={}\n'.format(vbd_record['empty']))
					meta_out.write('orig_uuid={}\n'.format(vbd_record['uuid']))
					meta_out.write('---- VDI ----\n')
					meta_out.write('name_label={}\n'.format(vdi_record['name_label']))
					meta_out.write('name_description={}\n'.format(vdi_record['name_description']))
					meta_out.write('virtual_size={}\n'.format(vdi_record['virtual_size']))
					meta_out.write('type={}\n'.format(vdi_record['type']))
					meta_out.write('sharable={}\n'.format(vdi_record['sharable']))
					meta_out.write('read_only={}\n'.format(vdi_record['read_only']))
					meta_out.write('orig_uuid={}\n'.format(vdi_record['uuid']))
					sr_uuid = self._d.get_sr_record(vdi_record['SR'])['uuid']
					meta_out.write('orig_sr_uuid={}\n'.format(sr_uuid))
					meta_out.write('\n')

				for vif in vm['VIFs']:
					vif_record = self._d.get_vif_record(vif)
					meta_out.write('******* VIF *******\n')
					meta_out.write('device={}\n'.format(vif_record['device']))
					network_name = self._d.get_network_record(vif_record['network'])['name_label']
					meta_out.write('network_name_label={}\n'.format(network_name))
					meta_out.write('MTU={}\n'.format(vif_record['MTU']))
					meta_out.write('MAC={}\n'.format(vif_record['MAC']))
					meta_out.write('other_config={}\n'.format(vif_record['other_config']))
					meta_out.write('orig_uuid={}\n'.format(vif_record['uuid']))
					meta_out.write('\n')
		except IOError as e:
			self._add_status('error', '(!) Unable to open metadata backup file: {}'.format(file))
			return False

		self.logger.debug('(i) Retrieved VDI data: {}'.format(vdi_data))
		return vdi_data

	def _check_backup_space(self):
		"""
			Check remaining disk space percentage for configured backup directory
			against configured threshold
		"""
		self.logger.info('> Checking backup space')
		percent_remaining = self._h.get_remaining_space(self.config['backup_dir'])
		self.logger.debug('(i) -> Backup space remaining: {}%'.format(percent_remaining))
		if percent_remaining < self.config['space_threshold']:
			self._add_status('error', '(!) Space remaining is below threshold: {}%'.format(percent_remaining))
			return False
		return True

	def _cleanup_snapshot(self, uuid, snapshot_type='vm', snap_name='ONYXBACKUP'):
		self.logger.info('> Checking for snapshot from previous backup')
		if snapshot_type == 'vm':
			cmd = 'snapshot-list name-label="{}" snapshot-of={} params=uuid --minimal'.format(snap_name, uuid)
		elif snapshot_type == 'vdi':
			cmd = 'vdi-list name-label="{}" snapshot-of={} params=uuid --minimal'.format(snap_name, uuid)
		else:
			self._add_status('error', '(!) Invalid snapshot type: {}'.format(snapshot_type))
			return False

		snap_uuid = self._get_xe_cmd_result(cmd)
		if snap_uuid:
			self.logger.debug('(i) Snapshot found: {}'.format(uuid))
			self.logger.info('-> Destroying snapshot')

			if snapshot_type == 'vm':
				cmd = 'snapshot-destroy uuid={}'.format(snap_uuid)
			elif snapshot_type == 'vdi':
				cmd = 'vdi-destroy uuid={}'.format(snap_uuid)
			else:
				self._add_status('error', '(!) Invalid snapshot type: {}'.format(snapshot_type))
				return False

			if not self._run_xe_cmd(cmd):
				self._add_status('error', '(!) Failed to destroy snapshot: {}'.format(snap_uuid))
				return False
			self.logger.info('-> Snapshot destroyed successfully')
		return True

	def _create_status(self):
		"""
			Create status object to hold currently running functions and tasks
			as well as their associated metadata
		"""
		self.status = {}
		self.status['error'] = 0
		self.status['warning'] = 0
		self.status['success'] = 0

	def _destroy_snapshot(self, uuid, snapshot_type='vm'):
		"""
			Destroy the snapshot with the given uuid
		"""
		self.logger.info('> Destroying snapshot')

		if snapshot_type == 'vm':
			cmd = 'snapshot-destroy uuid={}'.format(uuid)
		elif snapshot_type == 'vdi':
			cmd = 'vdi-destroy uuid={}'.format(uuid)
		else:
			self._add_status('error', '(!) Invalid snapshot type: {}'.format(snapshot_type))
			return False
		if not self._run_xe_cmd(cmd):
			self._add_status('error', '(!) Failed to destroy snapshot: {}'.format(uuid))
			return False
		return True

	def _export_to_file(self, id, file, export_type='vm'):
		"""
			Perform backup of VM, VDI, Host, or POOL DB with given id to
			specified file
		"""
		self.logger.info('> Exporting {}'.format(export_type.upper()))

		if export_type == 'vm':
			cmd = 'vm-export uuid={} filename="{}" compress={}'.format(id, file, self.config['compress'])
		elif export_type == 'vdi':
			cmd = 'vdi-export uuid={} filename="{}" format={}'.format(id, file, self.config['vdi_export_format'])
		elif export_type == 'pool':
			cmd = 'pool-dump-database file-name="{}"'.format(file)
		elif export_type == 'host':
			cmd = 'host-backup host="{}" file-name="{}" enabled=true'.format(id, file)
		else:
			self._add_status('error', '(!) Invalid export type: {}'.format(export_type))

		if not self._run_xe_cmd(cmd):
			self._add_status('error', '(!) Failed to export {}'.format(export_type.upper()))
			return False
		backup_file_size = self._h.get_file_size(file)
		self.logger.info('(i) -> Backup size: {}'.format(backup_file_size))
		return True

	def _get_all_hosts(self, as_list=True):
		"""
			Get all hosts' hostnames in pool and by default return as a list

			@return List of hosts in pool or False if none
		"""
		self.logger.info('> Getting all hosts')
		cmd = 'host-list params=hostname --minimal'
		hosts = self._get_xe_cmd_result(cmd)
		if as_list:
			hosts = hosts.split(',')
		self.logger.debug('(i) -> Hosts: {}'.format(hosts))
		if len(hosts) == 0:
			self._add_status('error', '(!) No hosts returned from pool')
			return False
		return hosts

	def _get_all_vms(self, as_list=True):
		"""
			Get a list of all VMs in the pool and by default return as list
		"""
		cmd = 'vm-list is-control-domain=false is-a-snapshot=false params=name-label --minimal'
		vms = self._get_xe_cmd_result(cmd)
		if as_list:
			vms = vms.split(',')
		self.logger.debug('(i) -> VMs in pool: {}'.format(vms))
		if vms == ['']:
			raise RuntimeError('(!) No VMs in pool to backup')
		else:
			return vms

	def _get_os_version(self, uuid):
		"""
			Get OS version of VM and trim to just show the 'name' portion
		"""
		cmd = 'vm-list uuid={} params=os-version --minimal'.format(uuid)
		os_version = self._get_xe_cmd_result(cmd)
		if os_version:
			os_version = re.split('[;:|]', os_version)[1][1:]
			self.logger.debug('(i) -> OS version: {}'.format(os_version))
			return os_version
		else:
			self.logger.debug('(i) -> OS version empty')
			return 'EMPTY'

	def _get_vm_by_name(self, name):
		"""
			Retrieve VM record by name-label
		"""
		self.logger.info('> Querying VM by name')
		vm = self._d.get_vm_by_name(name)
		vm_object = None
		# Return nothing if more than one VM has same name since backups are done via name-label
		if len(vm) == 0:
			self._add_status('error', '(!) No VM found matching name')
		elif len(vm) > 1:
			self._add_status('error', '(!) More than one VM exists with queried name')
		else:
			vm_object = vm[0]
		return vm_object

	def _get_vm_record(self, vm):
		"""
			Get VM record given a VM object
		"""
		self.logger.info('> Getting VM metadata')
		vm_meta = self._d.get_vm_record(vm)
		if not vm_meta:
			self._add_status('error', '(!) No VM record returned')
			return False
		return vm_meta

	def _get_xe_cmd_result(self, cmd):
		"""
			Run a given command with xe and return the resulting stdout/stderr
		"""
		cmd = '{}/xe {}'.format(self._xe_path, cmd)
		output = ''
		try:
			output = self._h.get_cmd_result(cmd)
			if output == '':
				self.logger.debug('(i) ---> Command returned no output')
			else:
				self.logger.debug('(i) ---> Command output: {}'.format(output))
		except OSError as e:
			self.logger.error('(!) Unable to run command: {}'.format(e))
		return output

	def _is_quiesce_enabled(self, vm):
		"""
			Checks VM record allowed operations to determine if VSS
			provider is loaded on VM
		"""
		self.logger.info('> Checking if VSS provider enabled')
		allowed_operations = vm['allowed_operations']
		if 'snapshot_with_quiesce' in allowed_operations:
			self.logger.debug('(i) -> VSS is enabled on VM')
			return True
		else:
			return False

	def _is_vm_name(self, text):
		"""
			Check if text is a valid simple VM name containing only letters,
			numbers, spaces, underscores, and hyphens
		"""
		if re.match('^[\w\s]+$', text) is not None:
			return True
		else:
			return False

	def _is_valid_regex(self, text):
		"""
			Check if text is a valid regular expression
		"""
		try:
			re.compile(text)
			return True
		except re.error as e:
			self.logger.debug('(i) -> Regex is not valid: {}'.format(e))
		return False

	def _is_windows_vm(self, uuid):
		"""
			Parses OS version string for "windows" to verify if VM is
			running Windows OS
		"""
		self.logger.info('> Checking OS type')
		os = self._get_os_version(uuid)
		if 'windows' in os.lower():
			self.logger.debug('(i) -> VM is running Windows: {}'.format(os))
			return True
		else:
			return False
		

	def _prepare_snapshot(self, uuid, snapshot_type='vm', snap_name='ONYXBACKUP'):
		"""
			Prepare snapshot with given uuid for backup
		"""
		self.logger.info('> Preparing snapshot for backup')

		if snapshot_type == 'vm':
			cmd = 'template-param-set is-a-template=false ha-always-run=false uuid={}'.format(uuid)
		elif snapshot_type == 'vdi':
			cmd = 'vdi-param-set uuid={} name-label="{}"'.format(uuid, snap_name)
		else:
			self._add_status('error', '(!) Invalid snapshot type: {}'.format(snapshot_type))
			return False

		if not self._run_xe_cmd(cmd):
			self._add_status('error', '(!) Failed to prepare snapshot: {}'.format(uuid))
			return False
		return True

	def _print_function_footer(self, title):
		"""
			Print the footer of a named unction in the logs
		"""
		function_end = datetime.datetime.now()
		elapsed = self._h.get_elapsed(self.status['function_start'], function_end)
		self.logger.info('________________________________________')
		self.logger.info('{} completed at {}'.format(title, self._h.get_time_string(function_end)))
		self.logger.info('time: {}'.format(elapsed))
		self.logger.info('Summary - S:{} W:{} E:{}'.format(self.status['success'], self.status['warning'], self.status['error']))

	def _print_function_header(self, title):
		"""
			Print the header of a named function in the logs
		"""
		print('')
		self.logger.info('************************')
		self.logger.info('    {}'.format(title))
		self.logger.info('************************')
		self.logger.info('Started: {}'.format(self._h.get_time_string(self.status['function_start'])))

	def _print_task_footer(self, title, start):
		"""
			Print the footer of a named task in the logs
		"""
		task_end = datetime.datetime.now()
		elapsed = self._h.get_elapsed(start, task_end)
		self.logger.info('--- {} completed at {} ---'.format(title, self._h.get_time_string(task_end)))
		self.logger.info('time: {}'.format(elapsed))

	def _print_task_header(self, title, start):
		"""
			Print the header of a named task in the logs
		"""
		print('')
		self.logger.info('--- {} started at {} ---'.format(title, self._h.get_time_string(start)))

	def _rotate_backups(self, max, path, vm_type=True):
		"""
			Rotate backups at the given path deleting backups over the given max.
			Defaults to handling VM backups which are handled in pairs with
			metadata backup files
		"""
		self.logger.info('> Rotating backups')
		self.logger.debug('(i) -> Path to check for backups: {}'.format(path))
		self.logger.debug('(i) -> Maximum backups to keep: {}'.format(max))
		files = [join(path, f) for f in listdir(path)]
		backups = len(files)
		if vm_type:
			if not len(files) % 2 == 0:
				self._add_status('error', '(!) Orphaned backup/meta files detected. Please remove orphaned files from {}.'.format(path))
				return False
			backups = len(files) / 2
		self.logger.debug('(i) -> Total backups found: {}'.format(backups))
		files = sorted(files, key=getmtime)
		while (backups > max and backups > 1):
			if vm_type:
				meta_file = files.pop(0)
				self.logger.info('-> Removing old metadata backup: {}'.format(meta_file))
				self._h.delete_file(meta_file)
			backup_file = files.pop(0)
			self.logger.info('-> Removing old backup: {}'.format(backup_file))
			self._h.delete_file(backup_file)
			backups -= 1
		return True

	def _run_xe_cmd(self, cmd):
		"""
			Run the given command with xe and report only success or failure
		"""
		cmd = '{}/xe {}'.format(self._xe_path, cmd)
		try:
			result = self._h.run_cmd(cmd)
			if result <> 0:
				self.logger.debug('(i) ---> Command returned non-zero exit status')
			else:
				self.logger.debug('(i) ---> Command successful')
				return True
		except OSError as e:
			self.logger.error('(!) Unable to run command: {}'.format(e))
		return False

	def _snapshot(self, uuid, snapshot_type='vm', snap_name='ONYXBACKUP'):
		"""
			Take snapshot of VM or VDI identified by given uuid

			@return snapshot uuid or False if failed
		"""
		self.logger.info('> Taking snapshot of {}'.format(snapshot_type))

		if snapshot_type == 'vm':
			cmd = 'vm-snapshot vm={} new-name-label="{}"'.format(uuid, snap_name)
		elif snapshot_type == 'vm-vss':
			cmd = 'vm-snapshot-with-quiesce vm={} new-name-label="{}"'.format(uuid, snap_name)
		elif snapshot_type == 'vdi':
			cmd = 'vdi-snapshot uuid={}'.format(uuid)
		else:
			self._add_status('error', '(!) Invalid snapshot type: {}'.format(snapshot_type))
			return False

		snap_uuid = self._get_xe_cmd_result(cmd)
		if not snap_uuid:
			self._add_status('error', '(!) Failed to create a snapshot')
			return False
		return snap_uuid

	def _start_function(self, title):
		"""
			Perform initial setup for a named function
		"""
		self._create_status()
		self.status['function'] = title
		self.status['function_start'] = datetime.datetime.now()
		self._print_function_header(title)

	def _start_task(self, title):
		"""
			Perform initial setup for a named task
		"""
		self.status['task'] = title
		self.status['task_start'] = datetime.datetime.now()
		self._print_task_header(title, self.status['task_start'])

	def _start_subtask(self, title):
		"""
			Perform initial setup for a named subtask
		"""
		self.status['subtask'] = title
		self.status['subtask_start'] = datetime.datetime.now()
		self._print_task_header(title, self.status['subtask_start'])

	def _stop_function(self):
		"""
			Perform closing actions for a named function
		"""
		self._print_function_footer(self.status['function'])
		self.status['function'] = None
		self.status['function_start'] = None

	def _stop_subtask(self):
		"""
			Perform closing actions for a named subtask
		"""
		self._print_task_footer(self.status['subtask'], self.status['subtask_start'])
		self.status['subtask'] = None
		self.status['subtask_start'] = None

	def _stop_task(self):
		"""
			Perform closing actions for a named task
		"""
		self._print_task_footer(self.status['task'], self.status['task_start'])
		self.status['task'] = None
		self.status['task_start'] = None

	def _uninstall_vm(self, uuid):
		"""
			Uninstall VM with given uuid
		"""
		self.logger.info('> Uninstalling snapshot')
		cmd = 'vm-uninstall uuid={} force=true'.format(uuid)
		if not self._run_xe_cmd(cmd):
			self._add_status('error', '(!) Failed to uninstall snapshot')
			return False
		return True

	def _validate_vm_lists(self, dict):
		"""
			Get all VMs from pool, sanitize so only VMs with valid characters
			are processed, and check the selected VM lists against those valid
			existing VMs
		"""
		all_vms = self._get_all_vms()
		sanitized_vms = []

		for vm in all_vms:
			reMatch = self._vm_name_invalid_characters(vm)
			if reMatch is not None:
				self.logger.warning('(!) Excluding {} due to invalid characters in name: -> {} <-'.format(vm, reMatch.group()))
			else:
				sanitized_vms.append(vm)

		self.logger.debug('(i) -> Sanitized VM list: {}'.format(sanitized_vms))

		for type, list in dict.items():
			self.logger.debug('(i) -> {} = {}'.format(type, list))
			validated_list = []
			found_match = False

			if list == []:
				continue

			if sanitized_vms == []:
				self.config[type] = []
				continue

			for value in list:
				self.logger.debug('(i) -> Checking for matches: {}'.format(value))
				values = value.split(':')
				vm_name = values[0]
				vm_backups = ''
				vdi_disks = ''
				if len(values) > 1:
					try:
						tmp_max = int(values[1])
						if isinstance(tmp_max, (int, long)) and (tmp_max == -1 or tmp_max > 0):
							vm_backups = values[1]
							if len(values) == 3:
								vdi_disks = values[2]
						else:
							self.logger.warning('(!) max_backups out of range for {}: {}'.format(vm_name, values[1]))
					except ValueError as e:
						self.logger.warning('(!) max_backups non-integer for {}: {}'.format(vm_name, values[1]))
				no_match = []

				if not self._is_vm_name(vm_name) and not self._is_valid_regex(vm_name):
					self.logger.warning('(!) Invalid regex: {}'.format(vm_name))
					continue

				no_match.append(vm_name)
				for vm in sanitized_vms:
					if ((self._is_vm_name(vm_name) and vm_name == vm) or
						(not self._is_vm_name(vm_name) and re.match(vm_name, vm))):
						if vm_backups == '':
							new_value = vm
						elif not vm_backups == '' and not vdi_disks == '':
							new_value = '{}:{}:{}'.format(vm, vm_backups, vdi_disks)
						else:
							new_value = '{}:{}'.format(vm, vm_backups)
						self.logger.debug('(i) -> Match found: {}'.format(vm))
						found_match = True
						if vm_name in no_match:
							no_match.remove(vm_name)
						validated_list.append(new_value)

				for vm in no_match:
					self.logger.warning('(!) No matching VMs found: {}'.format(vm))

				if found_match:
					for vm in validated_list:
						if vm in sanitized_vms:
							sanitized_vms.remove(vm)

				self.config[type] = sorted(validated_list, key=str.lower)

	def _verify_backup_dir(self, path):
		"""
			Verify backup directory exists or create it if not
		"""
		self.logger.info('> Verifying backup directory')			
		if not self._h.verify_path(path):
			self._add_status('error', '(!) Unable to create backup directory: {}'.format(path))
			return False
		return True

	def _vm_name_invalid_characters(self, name):
		"""
			Check if provided VM name contains any invalid characters
		"""
		return re.search('[\:\"/\\\\]', name)