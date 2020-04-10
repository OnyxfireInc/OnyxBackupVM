#!/usr/bin/env python

# OnyxBackupVM
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

import argparse
from datetime import datetime
from logging import getLogger
from os import uname
from sys import exit
import onyxbackup.config as config
import onyxbackup.service as service
import onyxbackup.util as util

class Cli(object):

	def __init__(self):
		self.logger = getLogger('onyxbackup')
		self.program_name = 'OnyxBackupVM'
		self.program_version = 'v1.3.1'
		self.config = self._setup()
		self._h = util.Helper()

	# API Functions

	def run(self):
		try:
			xenService = service.XenApiService(self.config)
			server_name = self._get_server_name()
			self.logger.info('-----------------------------------------------------')
			self.logger.info('{} running on {}'.format(self.program_name, server_name))
			self.logger.info('Started: {}'.format(self._h.get_date_string_print()))
			self.logger.info('-----------------------------------------------------')
			self.logger.debug('(i) Processing VM lists')
			xenService.process_vm_lists()

			if self.config['preview']:
				self._print_config()
				self._end_run()
				exit(0)

			if self.config['host_backup']:
				xenService.backup_hosts()

			if self.config['pool_backup']:
				xenService.backup_pool_db()

			if self.config['vdi_exports']:
				xenService.backup_vdi()

			if self.config['vm_exports']:
				xenService.backup_vm()

			self._end_run()

			if self.config['smtp_enabled']:
				xenService.send_email()
			exit(0)
		except Exception as e:
			self.logger.exception(e)
			self._end_run()
			exit(1)

	# Private Functions

	def _end_run(self):
		print('')
		self.logger.info('--------------------------------------------------------')
		self.logger.info('Ended: {}'.format(self._h.get_date_string_print()))

	def _get_server_name(self):
		return uname()[1]

	def _print_config(self):
		print('')
		self.logger.info('Running with these settings:')
		self.logger.info('  backup_dir        = {}'.format(self.config['backup_dir']))
		self.logger.info('  space_threshold   = {}'.format(self.config['space_threshold']))
		self.logger.info('  share_type        = {}'.format(self.config['share_type']))
		self.logger.info('  compress          = {}'.format(self.config['compress']))
		self.logger.info('  max_backups       = {}'.format(self.config['max_backups']))
		self.logger.info('  vdi_export_format = {}'.format(self.config['vdi_export_format']))
		self.logger.info('  pool_backup       = {}'.format(self.config['pool_backup']))
		self.logger.info('  host_backup       = {}'.format(self.config['host_backup']))
		self._print_vm_list('excludes', self.config['excludes'])
		self._print_vm_list('vdi-exports', self.config['vdi_exports'])
		self._print_vm_list('vm-exports', self.config['vm_exports'])
		if self.config['smtp_enabled']:
			print('')
			self.logger.info('  ****** SMTP ******')
			if self.config['smtp_auth']:
				self.logger.info('  smtp_auth         = {}'.format(self.config['smtp_auth']))
				self.logger.info('  smtp_user         = {}'.format(self.config['smtp_user']))
			self.logger.info('  smtp_starttls     = {}'.format(self.config['smtp_starttls']))
			self.logger.info('  smtp_server       = {}'.format(self.config['smtp_server']))
			self.logger.info('  smtp_port         = {}'.format(self.config['smtp_port']))
			self.logger.info('  smtp_hostname     = {}'.format(self.config['smtp_hostname']))
			self.logger.info('  smtp_timeout      = {}'.format(self.config['smtp_timeout']))
			self.logger.info('  smtp_subject      = {}'.format(self.config['smtp_subject']))
			self.logger.info('  smtp_from         = {}'.format(self.config['smtp_from']))
			self.logger.info('  smtp_to           = {}'.format(self.config['smtp_to']))

	def _print_vm_list(self, list_type, vms):
		self.logger.info('  {} (count) = {}'.format(list_type, len(vms)))
		str = ''
		for vm in vms:
			str += '{}, '.format(vm)
		if len(str) > 1:
			str = str[:-2]
		self.logger.info('  {}: {}'.format(list_type, str))

	def _setup(self):
		copyright = 'Copyright (C) 2017-2020  OnyxFire, Inc. <https://onyxfireinc.com>'
		program_title = '{} {}'.format(self.program_name, self.program_version)
		written_by = 'Written by: Lance Fogle (@lancefogle)'

		parent_parser = argparse.ArgumentParser(add_help=False)
		parent_parser.add_argument('-l', '--log-level', choices=['debug', 'info', 'warning', 'error', 'critical'],
			help='Log Level (Default: info)', metavar='LEVEL')
		parent_parser.add_argument('-c', '--config', help='Config file for runtime overrides', metavar='FILE')
		args, remaining_argv = parent_parser.parse_known_args()

		c = config.Configurator()
		options = c.configure(args)

		child_parser = argparse.ArgumentParser(
		  description=program_title + '\n' + copyright + '\n' + written_by,
		  parents=[parent_parser],
		  version=program_title + '\n' + copyright + '\n' + written_by,
		  formatter_class=argparse.RawDescriptionHelpFormatter
		)
		child_parser.set_defaults(**options)
		child_parser.add_argument('-d', '--backup-dir', metavar='PATH',
			help='Backups directory (Default: <' + self.program_name + ' Path>/exports)')
		child_parser.add_argument('-p', '--pool-backup', action='store_true', help='Backup Pool DB')
		child_parser.add_argument('-H', '--host-backup', action='store_true', help='Backup Hosts in Pool (dom0)')
		child_parser.add_argument('-C', '--compress', action='store_true',
			help='Compress on export (vm-exports only)')
		child_parser.add_argument('-F', '--format', choices=[ 'raw', 'vhd' ], metavar='FORMAT',
			help='VDI export format (vdi-exports only, Default: raw)')
		child_parser.add_argument('--preview', action='store_true', help='Preview resulting config and exit')
		child_parser.add_argument('-e', '--vm-export', action='append', dest='vm_exports', metavar='STRING',
			help='VM name or Regex for vm-export (Default: ".*") NOTE: Specify multiple times for multiple values')
		child_parser.add_argument('-E', '--vdi-export', action='append', dest='vdi_exports', metavar='STRING',
			help='VM name or Regex for vdi-export (Default: None) NOTE: Specify multiple times for multiple values')
		child_parser.add_argument('-x', '--exclude', action='append', dest='excludes', metavar='STRING',
			help='VM name or Regex to exclude (Default: None) NOTE: Specify multiple times for multiple values')

		final_args = vars(child_parser.parse_args(remaining_argv))
		options.update(final_args)
		c.validate_config(options)
		return options

# CLI execution

def main():
	program = Cli()
	program.run()

if __name__ == '__main__':
	main()
