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

import datetime, re
from logging import getLogger
from os import listdir, remove
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
		begin_time = datetime.datetime.now()
		self.logger.info('**************************')
		self.logger.info('* HOST-BACKUP ({}) *'.format(self._h.get_time_string(begin_time)))
		self.logger.info('**************************')
		success_cnt = 0
		error_cnt = 0
		warning_cnt = 0

		# Get all hosts in pool for backup
		self.logger.info('> Getting all hosts')
		all_hosts = self._get_all_hosts()
		if len(all_hosts) == 0:
			self.logger.error('(!) No hosts returned from pool')
			error_cnt += 1

		for host in all_hosts:
			host_dir = 'HOST_' + host
			path = join(self.config['backup_dir'], host_dir)
			self.logger.info('> Preparing backup directory')
			if self._h.verify_path(path):
				host_start = datetime.datetime.now()
				self.logger.info('*** {} started at {} ***'.format(host, self._h.get_time_string(host_start)))
				backup_file = '{}/host_{}.xbk'.format(path, self._h.get_date_string(host_start))
				self.logger.debug('(i) Backup file: {}'.format(backup_file))

				# Check remaining disk space for backup directory against threshold
				self.logger.info('> Checking backup space')
				backup_space_remaining = self._h.get_remaining_space(self.config['backup_dir'])
				self.logger.debug('(i) -> Backup space remaining: {}%'.format(backup_space_remaining))
				if backup_space_remaining < self.config['space_threshold']:
					self.logger.error('(!) Space remaining is below threshold: {}%'.format(backup_space_remaining))
					error_cnt += 1
					break

				# Backup host
				self.logger.info('> Backing up Host')
				cmd = 'host-backup host="{}" file-name="{}" enabled=true'.format(host, backup_file)
				if not self._run_xe_cmd(cmd):
					self.logger.error('(!) Failed to backup host: {}'.format(host))
					error_cnt += 1
				else:
					# Remove old backups based on retention
					self.logger.info('> Rotating backups')
					if not self._rotate_backups(self.config['max_backups'], path, False):
						self.logger.warning('(!) Failed to cleanup old backups')
						# Non-fatal so only warning as backup completed but cleanup failed
						warning_cnt += 1

					# Gather additional information on backup and report success
					host_end = datetime.datetime.now()
					elapsed = self._h.get_elapsed(host_start, host_end)
					backup_file_size = self._h.get_file_size(backup_file)
					self.logger.info('*** End {} at {} - time:{} size:{} ***'.format(host, self._h.get_time_string(host_end), elapsed, backup_file_size))
					success_cnt += 1
			else:
				self.logger.error('(!) Unable to create backup directory: {}'.format(path))
				error_cnt += 1
			

		# Host Backup Summary
		end_time = datetime.datetime.now()
		elapsed = self._h.get_elapsed(begin_time, end_time)
		self.logger.info('__________________________________________________')
		self.logger.info('HOST-BACKUP completed at {} - time:{}'.format(self._h.get_time_string(end_time), elapsed))

		# Report summary status
		self.logger.info('Summary - S:{} W:{} E:{}'.format(success_cnt, warning_cnt, error_cnt))

	def backup_pool_db(self):
		begin_time = datetime.datetime.now()
		self.logger.info('*****************************')
		self.logger.info('* POOL-DB-BACKUP ({}) *'.format(self._h.get_time_string(begin_time)))
		self.logger.info('*****************************')
		success_cnt = 0
		error_cnt = 0
		warning_cnt = 0

		path = join(self.config['backup_dir'], 'POOL_DB')
		backup_file = '{}/metadata_{}.db'.format(path, self._h.get_date_string())
		self.logger.debug('(i) Backup file: {}'.format(backup_file))

		# Check remaining disk space for backup directory against threshold
		self.logger.info('> Checking backup space')
		backup_space_remaining = self._h.get_remaining_space(self.config['backup_dir'])
		self.logger.debug('(i) -> Backup space remaining: {}%'.format(backup_space_remaining))
		if backup_space_remaining < self.config['space_threshold']:
			self.logger.error('(!) Space remaining is below threshold: {}%'.format(backup_space_remaining))
			error_cnt += 1
		else:
			self.logger.info('> Preparing backup directory')	
			if self._h.verify_path(path):
				# Backing up pool DB
				self.logger.info('> Backing up pool db')
				cmd = 'pool-dump-database file-name="{}"'.format(backup_file)
				if not self._run_xe_cmd(cmd):
					self.logger.error('(!) Failed to backup pool db')
					error_cnt += 1
				else:
					success_cnt += 1

					# Remove old backups based on retention
					self.logger.info('> Rotating backups')
					if not self._rotate_backups(self.config['max_backups'], path, False):
						self.logger.warning('(!) Failed to cleanup old backups')
						# Non-fatal so only warning as backup completed but cleanup failed
						warning_cnt += 1
			else:
				self.logger.error('(!) Unable to create backup directory: {}'.format(path))
				error_cnt += 1

		# Pool DB Backup Summary
		end_time = datetime.datetime.now()
		elapsed = self._h.get_elapsed(begin_time, end_time)
		backup_file_size = self._h.get_file_size(backup_file)
		self.logger.info('_________________________________________________________')
		self.logger.info('POOL-DB-BACKUP completed at {} - time:{} size:{}'.format(self._h.get_time_string(end_time), elapsed, backup_file_size))

		# Report summary status
		self.logger.info('Summary - S:{} W:{} E:{}'.format(success_cnt, warning_cnt, error_cnt))

	def backup_meta(self, vm_record, meta_file):
		# Create dictionary to return all VDI devices and their uuids for vdi-exports
		vdi_data = {}

		self.logger.debug('(i) -> Opening metadata file for writing')
		meta_out = open(meta_file, 'w')

		# Get VM metadata
		self.logger.debug('(i) -> Recording VM metadata: {}'.format(vm_record['name_label']))
		meta_out.write('******* VM *******\n')
		meta_out.write('name_label={}\n'.format(vm_record['name_label']).encode('utf8'))
		meta_out.write('name_description={}\n'.format(vm_record['name_description']).encode('utf8'))
		meta_out.write('memory_dynamic_max={}\n'.format(vm_record['memory_dynamic_max']))
		meta_out.write('VCPUs_max={}\n'.format(vm_record['VCPUs_max']))
		meta_out.write('VCPUs_at_startup={}\n'.format(vm_record['VCPUs_at_startup']))
		if vm_record['other_config']['base_template_name']:
			meta_out.write('base_template_name={}\n'.format(vm_record['other_config']['base_template_name']))
		meta_out.write('os_version={}\n'.format(self._get_os_version(vm_record['uuid'])))
		meta_out.write('orig_uuid={}\n'.format(vm_record['uuid']))
		meta_out.write('\n')
		self.logger.debug('(i) -> VM metadata recorded: {}'.format(vm_record['name_label']))

		# Get VM disk metadata
		for vbd in vm_record['VBDs']:
			vbd_record = self._d.get_vbd_record(vbd)
			if vbd_record['type'].lower() != 'disk':
				self.logger.debug('(i) -> Not a data disk... skipping: {}'.format(vbd_record['type']))
				continue

			vdi_record = self._d.get_vdi_record(vbd_record['VDI'])

			# Store VDI device:uuid pairs for vdi-exports
			self.logger.debug('(i) -> Storing VDI metadata: {}:{}'.format(vbd_record['device'], vdi_record['uuid']))
			vdi_data[vbd_record['device']] = vdi_record['uuid']

			self.logger.debug('(i) -> Recording DISK metadata: {}'.format(vbd_record['device']))
			meta_out.write('******* DISK *******\n')
			meta_out.write('device={}\n'.format(vbd_record['device']))
			meta_out.write('userdevice={}\n'.format(vbd_record['userdevice']))
			meta_out.write('bootable={}\n'.format(vbd_record['bootable']))
			meta_out.write('mode={}\n'.format(vbd_record['mode']))
			meta_out.write('type={}\n'.format(vbd_record['type']))
			meta_out.write('unpluggable={}\n'.format(vbd_record['unpluggable']))
			meta_out.write('empty={}\n'.format(vbd_record['empty']))
			meta_out.write('orig_uuid={}\n'.format(vbd_record['uuid']))
			self.logger.debug('(i) -> Recording vdi metadata: {}'.format(vdi_record['name_label']))
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
			self.logger.debug('(i) -> VDI metadata recorded: {}'.format(vdi_record['name_label']))
			meta_out.write('\n')
			self.logger.debug('(i) -> Disk metadata recorded: {}'.format(vbd_record['device']))

		# Get VM VIF metadata
		for vif in vm_record['VIFs']:
			vif_record = self._d.get_vif_record(vif)
			self.logger.debug('(i) -> Recording VIF metadata: {}'.format(vif_record['device']))
			meta_out.write('******* VIF *******\n')
			meta_out.write('device={}\n'.format(vif_record['device']))
			network_name = self._d.get_network_record(vif_record['network'])['name_label']
			meta_out.write('network_name_label={}\n'.format(network_name))
			meta_out.write('MTU={}\n'.format(vif_record['MTU']))
			meta_out.write('MAC={}\n'.format(vif_record['MAC']))
			meta_out.write('other_config={}\n'.format(vif_record['other_config']))
			meta_out.write('orig_uuid={}\n'.format(vif_record['uuid']))
			meta_out.write('\n')
			self.logger.debug('(i) -> VIF metadata recorded: {}'.format(vif_record['device']))

		self.logger.debug('(i) -> Closing metadata file')
		meta_out.close()

		self.logger.debug('(i) -> Stored VDI data: {}'.format(vdi_data))
		return vdi_data

	def backup_vdi(self):
		begin_time = datetime.datetime.now()
		self.logger.info('**************************')
		self.logger.info('* VDI-EXPORT ({}) *'.format(self._h.get_time_string(begin_time)))
		self.logger.info('**************************')
		success_cnt = 0
		error_cnt = 0
		warning_cnt = 0
		vms = self.config['vdi_exports']

		self.logger.debug('(i) VMs: {}'.format(vms))

		# Warn if empty list given
		if vms == []:
			self.logger.warning('(!) No VMs selected for vdi-export')
			warning_cnt += 1

		for value in vms:
			vm_start = datetime.datetime.now()
			values = value.split(':')
			vm_name = values[0]
			vm_backups = self.config['max_backups']
			vdi_disks = ['xvda']
			if (len(values) > 1) and not (values[1] == '-1'):
				vm_backups = int(values[1])
			if len(values) == 3:
				vdi_disks[:] = []
				vdi_disks += values[2].split(';')

			self.logger.info('*** {} started at {} ***'.format(vm_name, self._h.get_time_string(vm_start)))
			self.logger.debug('(i) Name:{} Max-Backups:{} Disks:{}'.format(vm_name, vm_backups, vdi_disks))
			
			# Check remaining disk space for backup directory against threshold
			self.logger.info('> Checking backup space')
			backup_space_remaining = self._h.get_remaining_space(self.config['backup_dir'])
			self.logger.debug('(i) -> Backup space remaining: {}%'.format(backup_space_remaining))
			if backup_space_remaining < self.config['space_threshold']:
				self.logger.error('(!) Space remaining is below threshold: {}%'.format(backup_space_remaining))
				error_cnt += 1
				break

			# Fail if no disks selected for backup
			if not vdi_disks:
				self.logger.error('(!) No disks selected for backup: {}'.format(vm_name))
				error_cnt += 1
				self.logger.info('-> Skipping VM due to error: {}'.format(vm_name))
				continue

			# Get VM by name for backup
			self.logger.info('> Querying VM')
			vm_object = self._get_vm_by_name(vm_name)
			if not vm_object:
				self.logger.error('(!) No valid VM found: {}'.format(vm_name))
				error_cnt += 1
				self.logger.info('-> Skipping VM due to error: {}'.format(vm_name))
				continue

			vm_backup_dir = join(self.config['backup_dir'], vm_name)

			# Create/Verify backup directory
			self.logger.info('> Preparing VM backup directory')
			if not self._h.verify_path(vm_backup_dir):
				self.logger.error('(!) Unable to create backup directory: {}'.format(vm_backup_dir))
				error_cnt += 1
				self.logger.info('-> Skipping VM due to error: {}'.format(vm_name))
				continue

			# Get VM metadata
			self.logger.info('> Getting VM metadata')
			vm_meta = self._d.get_vm_record(vm_object)
			if not vm_meta:
				self.logger.error('(!) No VM record returned: {}'.format(vm_name))
				error_cnt += 1
				self.logger.info('-> Skipping VM due to error: {}'.format(vm_name))
				continue

			for disk in vdi_disks:
				vdi_start = datetime.datetime.now()
				self.logger.info('>>> Begin {} at {} <<<'.format(disk, self._h.get_time_string(vdi_start)))

				# Set backup files
				base = '{}/backup_{}_{}'.format(vm_backup_dir, disk, self._h.get_date_string())
				meta_backup_file = '{}.meta'.format(base)
				self.logger.debug('(i) meta_backup_file: {}'.format(meta_backup_file))
				backup_file = '{}.{}'.format(base, self.config['vdi_export_format'])
				self.logger.debug('(i) backup_file: {}'.format(backup_file))
				snap_name = 'ONYXBACKUP_{}_{}'.format(vm_name, disk)
				
				# Check remaining disk space for backup directory against threshold
				self.logger.info('> Checking backup space')
				backup_space_remaining = self._h.get_remaining_space(self.config['backup_dir'])
				self.logger.debug('(i) -> Backup space remaining "{}": {}%'.format(self.config['backup_dir'], backup_space_remaining))
				if backup_space_remaining < self.config['space_threshold']:
					self.logger.error('(!) Space remaining is below threshold: {}%'.format(backup_space_remaining))
					error_cnt += 1
					break

				# Backing up VM Metadata
				self.logger.info('> Backing up VM metadata')
				vdi_data = self.backup_meta(vm_meta, meta_backup_file)

				# Cleanup snapshot from previous attempt if exists
				self.logger.info('> Checking for previous snapshot: {}'.format(snap_name))
				cmd = 'vdi-list name-label="{}" params=uuid --minimal'.format(snap_name)
				old_snap = self._get_xe_cmd_result(cmd)
				if old_snap:
					self.logger.warning('(!) Previous backup snapshot found: {}'.format(old_snap))
					self.logger.info('-> Cleaning up snapshot from previous attempt: {}'.format(snap_name))
					cmd = 'vdi-destroy uuid={}'.format(old_snap)
					if not self._run_xe_cmd(cmd):
						self.logger.error('(!) Failed to cleanup snapshot from previous attempt')
						warning_cnt += 1
					else:
						self.logger.info('-> Previous backup snapshot removed')

				# Check for valid disk and get UUID for backup
				self.logger.info('> Verifying disk is valid: {}'.format(disk))
				if disk in vdi_data:
					vdi_uuid = vdi_data[disk]
				else:
					self.logger.error('(!) Invalid device specified: {}'.format(disk))
					error_cnt += 1
					if not self._h.delete_file(meta_backup_file):
						self.logger.error('(!) Failed to remove metadata file: {}'.format(meta_backup_file))
					self.logger.info('-> Skipping VDI due to error: {}'.format(disk))
					continue

				# Take snapshot of VDI
				self.logger.info('> Taking snapshot of disk')
				cmd = 'vdi-snapshot uuid={}'.format(vdi_uuid)
				snap_uuid = self._get_xe_cmd_result(cmd)
				if not snap_uuid:
					self.logger.error('(!) Failed to create snapshot: {}'.format(snap_name))
					error_cnt += 1
					self.logger.debug('(i) -> Removing metadata file: {}'.format(meta_backup_file))
					if not self._h.delete_file(meta_backup_file):
						self.logger.error('(!) Failed to remove metadata file: {}'.format(meta_backup_file))
					self.logger.info('-> Skipping VDI due to error: {}'.format(vm_name))
					continue

				# Set VDI params for easy cleanup
				self.logger.info('> Setting VDI params')
				cmd = 'vdi-param-set uuid={} name-label="{}"'.format(snap_uuid, snap_name)
				if not self._run_xe_cmd(cmd):
					self.logger.error('(!) Failed to prepare snapshot for backup')
					error_cnt += 1
					self.logger.debug('(i) -> Destroying snapshot: {}'.format(snap_name))
					cmd = 'vdi-destroy uuid={}'.format(snap_uuid)
					if not self._run_xe_cmd(cmd):
						self.logger.error('(!) Failed to destroy snapshot: {}'.format(snap_name))
					self.logger.info('-> Skipping VDI due to error: {}'.format(vm_name))
					continue

				# Backup VDI from snapshot
				self.logger.info('> Backing up VDI')
				cmd = 'vdi-export format={} uuid={} filename="{}"'.format(self.config['vdi_export_format'], snap_uuid, backup_file)
				if not self._run_xe_cmd(cmd):
					self.logger.error('(!) Failed to backup VDI: {}'.format(disk))
					error_cnt += 1
					self.logger.debug('(i) -> Destroying snapshot: {}'.format(snap_name))
					cmd = 'vdi-destroy uuid={}'.format(snap_uuid)
					if not self._run_xe_cmd(cmd):
						self.logger.error('(!) Failed to destroy snapshot: {}'.format(snap_name))
					self.logger.info('-> Skipping VDI due to error: {}'.format(vm_name))
					continue

				# Remove snapshot now that backup completed
				self.logger.info('> Cleaning up snapshot: {}'.format(snap_name))
				cmd = 'vdi-destroy uuid={}'.format(snap_uuid)
				if not self._run_xe_cmd(cmd):
					self.logger.warning('(!) Failed to cleanup snapshot: {}'.format(snap_name))
					# Non-fatal so only warning as backup completed but cleanup failed
					warning_cnt += 1

				# Remove old backups based on retention
				self.logger.info('> Rotating backups')
				if not self._rotate_backups(vm_backups, vm_backup_dir):
					self.logger.warning('(!) Failed to cleanup old backups')
					# Non-fatal so only warning as backup completed but cleanup failed
					warning_cnt += 1

				# Gather additional information on backup and report success
				vdi_end = datetime.datetime.now()
				elapsed = self._h.get_elapsed(vdi_start, vdi_end)
				backup_file_size = self._h.get_file_size(backup_file)
				self.logger.info('>>> End {} at {} - time:{} size:{} <<<'.format(disk, self._h.get_time_string(vdi_end), elapsed, backup_file_size))
				success_cnt += 1

			# VM Summary
			vm_end = datetime.datetime.now()
			elapsed = self._h.get_elapsed(vm_start, vm_end)
			self.logger.info('*** {} completed at {} - time:{} ***'.format(vm_name, self._h.get_time_string(vm_end), elapsed))

		# VDI-Export Summary
		end_time = datetime.datetime.now()
		elapsed = self._h.get_elapsed(begin_time, end_time)
		self.logger.info('__________________________________________________')
		self.logger.info('VDI-EXPORT completed at {} - time:{}'.format(self._h.get_time_string(end_time), elapsed))

		# Report summary status
		self.logger.info('Summary - S:{} W:{} E:{}'.format(success_cnt, warning_cnt, error_cnt))

	def backup_vm(self):
		begin_time = datetime.datetime.now()
		self.logger.info('************************')
		self.logger.info('* VM-EXPORT ({}) *'.format(self._h.get_time_string(begin_time)))
		self.logger.info('************************')
		success_cnt = 0
		error_cnt = 0
		warning_cnt = 0
		vms = self.config['vm_exports']

		self.logger.debug('(i) VMs: {}'.format(vms))

		# Warn if empty list given
		if vms == []:
			self.logger.warning('(!) No VMs selected for vm-export')
			warning_cnt += 1

		for value in vms:
			vm_start = datetime.datetime.now()
			values = value.split(':')
			vm_name = values[0]
			vm_backups = self.config['max_backups']
			if (len(values) > 1) and not (values[1] == '-1'):
				vm_backups = int(values[1])

			self.logger.info('*** {} started at {} ***'.format(vm_name, self._h.get_time_string(vm_start)))
			self.logger.debug('(i) Name:{} Max-Backups:{}'.format(vm_name, vm_backups))

			# Set backup files and destinations
			vm_backup_dir = join(self.config['backup_dir'], vm_name)			
			base = '{}/backup_{}'.format(vm_backup_dir, self._h.get_date_string())
			meta_backup_file = '{}.meta'.format(base)
			self.logger.debug('(i) meta_backup_file:{}'.format(meta_backup_file))
			if self.config['compress']:
				backup_file = '{}.xva.gz'.format(base)
			else:
				backup_file = '{}.xva'.format(base)
			self.logger.debug('(i) backup_file:{}'.format(backup_file))
			snap_name = 'ONYXBACKUP_{}'.format(vm_name)

			# Check remaining disk space for backup directory against threshold
			self.logger.info('> Checking backup space')
			backup_space_remaining = self._h.get_remaining_space(self.config['backup_dir'])
			self.logger.debug('(i) -> Backup space remaining: {}%'.format(backup_space_remaining))
			if backup_space_remaining < self.config['space_threshold']:
				self.logger.error('(!) Space remaining is below threshold: {}%'.format(backup_space_remaining))
				error_cnt += 1
				break

			# Get VM by name for backup
			self.logger.info('> Querying VM')
			vm_object = self._get_vm_by_name(vm_name)
			if not vm_object:
				self.logger.error('(!) No valid VM found: {}'.format(vm_name))
				error_cnt += 1
				self.logger.info('-> Skipping VM due to error: {}'.format(vm_name))
				continue

			# Create/Verify backup directory
			self.logger.info('> Preparing VM backup directory')			
			if not self._h.verify_path(vm_backup_dir):
				self.logger.error('(!) Unable to create backup directory: {}'.format(vm_backup_dir))
				error_cnt += 1
				self.logger.info('-> Skipping VM due to error: {}'.format(vm_name))
				continue

			# Get VM metadata
			self.logger.info('> Getting VM metadata')
			vm_meta = self._d.get_vm_record(vm_object)
			if not vm_meta:
				self.logger.error('(!) No VM record returned: {}'.format(vm_name))
				error_cnt += 1
				self.logger.info('-> Skipping VM due to error: {}'.format(vm_name))
				continue

			# Backing up VM Metadata
			self.logger.info('> Backing up VM metadata')
			self.backup_meta(vm_meta, meta_backup_file)
			
			# Cleanup snapshot from previous attempt if exists
			self.logger.info('> Checking for previous snapshot: {}'.format(snap_name))
			cmd = 'snapshot-list name-label="{}" params=uuid --minimal'.format(snap_name)
			old_snap = self._get_xe_cmd_result(cmd)
			if old_snap:
				self.logger.warning('(!) Previous backup snapshot found: {}'.format(old_snap))
				self.logger.info('-> Cleaning up snapshot from previous attempt')
				cmd = 'snapshot-destroy uuid={}'.format(old_snap)
				if not self._run_xe_cmd(cmd):
					self.logger.error('(!) Failed to cleanup snapshot from previous attempt')
					warning_cnt += 1
				else:
					self.logger.info('-> Previous backup snapshot removed')

			vm_uuid = vm_meta['uuid']
			
			# Take snapshot of VM
			self.logger.info('> Taking snapshot of VM')
			cmd = 'vm-snapshot vm={} new-name-label="{}"'.format(vm_uuid, snap_name)
			snap_uuid = self._get_xe_cmd_result(cmd)
			if not snap_uuid:
				self.logger.error('(!) Failed to create snapshot: {}'.format(snap_name))
				error_cnt += 1
				self.logger.debug('(i) -> Removing metadata file: {}'.format(meta_backup_file))
				if not self._h.delete_file(meta_backup_file):
					self.logger.error('(!) Failed to remove metadata file: {}'.format(meta_backup_file))
				self.logger.info('-> Skipping VM due to error: {}'.format(vm_name))
				continue

			# Prepare snapshot for backup
			self.logger.info('> Setting VM params')
			cmd = 'template-param-set is-a-template=false ha-always-run=false uuid={}'.format(snap_uuid)
			if not self._run_xe_cmd(cmd):
				self.logger.error('(!) Failed to prepare snapshot for backup')
				error_cnt += 1
				self.logger.debug('(i) -> Destroying snapshot: {}'.format(snap_name))
				cmd = 'snapshot-destroy uuid={}'.format(snap_uuid)
				if not self._run_xe_cmd(cmd):
					self.logger.error('(!) Failed to destroy snapshot: {}'.format(snap_name))
				self.logger.debug('(i) -> Removing metadata file: {}'.format(meta_backup_file))
				if not self._h.delete_file(meta_backup_file):
					self.logger.error('(!) Failed to remove metadata file: {}'.format(meta_backup_file))
				self.logger.info('-> Skipping VM due to error: {}'.format(vm_name))
				continue

			# Backup VM from snapshot
			self.logger.info('> Backing up VM')
			cmd = 'vm-export uuid={} filename="{}" compress={}'.format(snap_uuid, backup_file, self.config['compress'])
			if not self._run_xe_cmd(cmd):
				self.logger.error('(!) Failed to backup VM: {}'.format(vm_name))
				error_cnt += 1
				self.logger.debug('(i) -> Destroying snapshot: {}'.format(snap_name))
				cmd = 'snapshot-destroy uuid={}'.format(snap_uuid)
				if not self._run_xe_cmd(cmd):
					self.logger.error('(!) Failed to destroy snapshot: {}'.format(snap_name))
				self.logger.debug('(i) -> Removing metadata file: {}'.format(meta_backup_file))
				if not self._h.delete_file(meta_backup_file):
					self.logger.error('(!) Failed to remove metadata file: {}'.format(meta_backup_file))
				self.logger.info('-> Skipping VM due to error: {}'.format(vm_name))
				continue

			# Remove snapshot now that backup completed
			self.logger.info('> Cleaning up snapshot')
			cmd = 'vm-uninstall uuid={} force=true'.format(snap_uuid)
			if not self._run_xe_cmd(cmd):
				self.logger.warning('(!) Failed to cleanup snapshot: {}'.format(snap_name))
				# Non-fatal so only warning as backup completed but cleanup failed
				warning_cnt += 1

			# Remove old backups based on retention
			self.logger.info('> Rotating backups')
			if not self._rotate_backups(vm_backups, vm_backup_dir):
				self.logger.warning('(!) Failed to cleanup old backups')
				# Non-fatal so only warning as backup completed but cleanup failed
				warning_cnt += 1

			# Gather additional information on backup and report success
			vm_end = datetime.datetime.now()
			elapsed = self._h.get_elapsed(vm_start, vm_end)
			backup_file_size = self._h.get_file_size(backup_file)
			self.logger.info('*** {} completed at {} - time:{} size:{} ***'.format(vm_name, self._h.get_time_string(vm_end), elapsed, backup_file_size))
			success_cnt += 1

		# VM-Export Summary
		end_time = datetime.datetime.now()
		elapsed = self._h.get_elapsed(begin_time, end_time)
		self.logger.info('__________________________________________________')
		self.logger.info('VM-EXPORT completed at {} - time:{}'.format(self._h.get_time_string(end_time), elapsed))

		# Report summary status
		self.logger.info('Summary - S:{} W:{} E:{}'.format(success_cnt, warning_cnt, error_cnt))

	def process_vm_lists(self):
		vm_lists = OrderedDict()
		vm_lists['excludes'] = self.config['excludes']
		vm_lists['vdi_exports'] = self.config['vdi_exports']
		vm_lists['vm_exports'] = self.config['vm_exports']
		self._validate_vm_lists(vm_lists)

	def send_email(self):
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

		self.logger.debug('(i) Sending email report to {}'.format(smtp_to))

		with open(smtp_file) as fp:
			msg = MIMEText(fp.read())

		msg['Subject'] = smtp_subject
		msg['From'] = smtp_from
		msg['To'] = smtp_to

		s = smtplib.SMTP(smtp_server,smtp_port,smtp_hostname,smtp_timeout)
		s.ehlo()
		if self.config['smtp_starttls']:
			s.starttls()
			s.ehlo()
		if self.config['smtp_auth']:
			s.login(self.config['smtp_user'], self.config['smtp_pass'])
		s.sendmail(smtp_from, [smtp_to], msg.as_string())
		s.quit()

	# Private Functions

	def _get_all_hosts(self, as_list=True):
		cmd = 'host-list params=hostname --minimal'
		hosts = self._get_xe_cmd_result(cmd)
		if as_list:
			hosts = hosts.split(',')
		self.logger.debug('(i) -> Hosts: {}'.format(hosts))
		return hosts

	def _get_all_vms(self, as_list=True):
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
		cmd = 'vm-list uuid={} params=os-version --minimal'.format(uuid)
		os_version = self._get_xe_cmd_result(cmd)
		if os_version:
			os_version = os_version.split(';')[0][6:]
			self.logger.debug('(i) -> OS version: {}'.format(os_version))
			return os_version
		else:
			self.logger.debug('(i) -> OS version empty')
			return 'None'

	def _get_vm_by_name(self, vm_name):
		vm = self._d.get_vm_by_name(vm_name)
		# Return nothing if more than one VM has same name since backups are done via name-label
		if len(vm) == 0:
			return []
		elif len(vm) > 1:
			self.logger.error('(!) More than one VM exists with same name: {}'.format(vm_name))
			return []
		else:
			return vm[0]

	def _get_xe_cmd_result(self, cmd):
		cmd = '{}/xe {}'.format(self._xe_path, cmd)
		output = ''
		try:
			output = self._h.get_cmd_result(cmd)
			if output == '':
				self.logger.debug('(i) -> Command returned no output')
			else:
				self.logger.debug('(i) -> Command output: {}'.format(output))
		except OSError as e:
			self.logger.error('(!) Unable to run command: {}'.format(e))
		return output

	def _is_vm_name(self, text):
		if re.match('^[\w\s]+$', text) is not None:
			return True
		else:
			return False

	def _is_valid_regex(self, text):
		try:
			re.compile(text)
			return True
		except re.error as e:
			self.logger.debug('(i) -> Regex is not valid: {}'.format(e))
		return False

	def _rotate_backups(self, max, path, vm_type=True):
		self.logger.debug('(i) -> Path to check for backups: {}'.format(path))
		self.logger.debug('(i) -> Maximum backups to keep: {}'.format(max))
		files = [join(path, f) for f in listdir(path)]
		backups = len(files)
		if vm_type:
			if not len(files) % 2 == 0:
				self.logger.error('(!) Orphaned backup/meta files detected. Please remove orphaned files from {}.'.format(path))
				return False
			backups = len(files) / 2
		self.logger.debug('(i) -> Total backups found: {}'.format(backups))
		files = sorted(files, key=getmtime)
		while (backups > max and backups > 1):
			if vm_type:
				meta_file = files.pop(0)
				self.logger.info('-> Removing old metadata backup: {}'.format(meta_file))
				remove(meta_file)
			backup_file = files.pop(0)
			self.logger.info('-> Removing old backup: {}'.format(backup_file))
			remove(backup_file)
			backups -= 1
		return True

	def _run_xe_cmd(self, cmd):
		cmd = '{}/xe {}'.format(self._xe_path, cmd)
		try:
			result = self._h.run_cmd(cmd)
			if result <> 0:
				self.logger.debug('(i) -> Command returned non-zero exit status')
			else:
				self.logger.debug('(i) -> Command successful')
				return True
		except OSError as e:
			self.logger.error('(!) Unable to run command: {}'.format(e))
		return False

	def _validate_vm_lists(self, dict):
		all_vms = self._get_all_vms()
		sanitized_vms = []

		for vm in all_vms:
			reMatch = self._vm_name_invalid_characters(vm)
			if reMatch is not None:
				self.logger.warning('(!) Excluding {} due to invalid characters in name: -> {} <-'.format(vm, reMatch.group()))
			else:
				sanitized_vms.append(vm)

		for type, list in dict.items():
			self.logger.debug('(i) -> {} = {}'.format(type, list))
			validated_list = []
			found_match = False

			# Skip list if empty
			if list == []:
				continue

			# Fail fast if all VMs excluded/matched or no VMs exist in the pool,
			# to prevent python regex from matching all VMs
			if sanitized_vms == []:
				self.config[type] = []
				continue

			# Evaluate values if we get this far
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

				# Warn if name/regex not valid and jump to next item in list
				if not self._is_vm_name(vm_name) and not self._is_valid_regex(vm_name):
					self.logger.warning('(!) Invalid regex: {}'.format(vm_name))
					continue

				# Check for matches against VMs in pool and add to final list for backup
				no_match.append(vm_name)
				for vm in sanitized_vms:
					# Below line for extreme debugging only as pool may have thousands of VMs
					#self.logger.debug('(i) Checking against VM: {}'.format(vm))
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

				# Remove matches from master list to prevent duplicates in other lists
				if found_match:
					for vm in validated_list:
						if vm in sanitized_vms:
							sanitized_vms.remove(vm)

				self.config[type] = sorted(validated_list, key=str.lower)

	def _vm_name_invalid_characters(self, name):
		return re.search('[\:\"/\\\\]', name)
