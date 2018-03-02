#!/usr/bin/env python

# OnyxBackup for XenServer
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

import argparse, datetime
from logging import getLogger
from os import uname
from sys import exit
import onyxbackup.config as config
import onyxbackup.service as service

class Cli(object):

	def __init__(self):
		self.logger = getLogger('onyxbackup')
		self.config = self._setup()

	# API Functions

	def run(self):
		try:
			xenService = service.XenApiService(self.config)
			server_name = self._get_server_name()
			self.logger.info('---------------------------------------------------------')
			self.logger.info('OnyxBackup for XenServer running on {}'.format(server_name))
			self.logger.info('Started: {}'.format(self._get_date_string()))
			self.logger.info('---------------------------------------------------------')
			print('')
			self.logger.debug('(i) Processing VM lists')
			xenService.process_vm_lists()
			print('')

			if self.config['preview']:
				self._print_config()
				print('')
				self._end_run()

			if self.config['host_backup']:
				xenService.backup_hosts()
				print('')

			if self.config['pool_backup']:
				xenService.backup_pool_db()
				print('')

			if self.config['vdi_exports']:
				xenService.backup_vdi()
				print('')

			if self.config['vm_exports']:
				xenService.backup_vm()
				print('')

			self._end_run()
		except Exception as e:
			self.logger.critical('Fatal Exception: {}'.format(str(e)))
			self._end_run(1)

	# Private Functions

	def _end_run(self, exitCode=0):
		self.logger.info('---------------------------------------------------------')
		self.logger.info('Ended: {}'.format(self._get_date_string()))
		exit(exitCode)

	def _get_date_string(self, date=''):
		if date == '':
			now = datetime.datetime.now()
		else:
			now = date
		str = '%02d/%02d/%04d %02d:%02d:%02d' \
			% (now.month, now.day, now.year, now.hour, now.minute, now.second)
		return str

	def _get_server_name(self):
		return uname()[1]

	def _print_config(self):
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

	def _print_vm_list(self, type, vms):
		self.logger.info('  {} (count) = {}'.format(type, len(vms)))
		str = ''
		for vm in vms:
			str += '{}, '.format(vm)
		if len(str) > 1:
			str = str[:-2]
		self.logger.info('  {}: {}'.format(type, str))

	def _setup(self):
		version = '1.0.0'
		current_year = datetime.datetime.now().year
		copyright = 'Copyright (C) {}  OnyxFire, Inc. <https://onyxfireinc.com>'.format(current_year)
		program_title = 'OnyxBackup for XenServer {}'.format(version)
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
			help='Backups directory (Default: <OnyxBackup-XS Path>/exports)')
		child_parser.add_argument('-p', '--pool-backup', action='store_true', help='Backup Pool DB')
		child_parser.add_argument('-H', '--host-backup', action='store_true', help='Backup Hosts in Pool (dom0)')
		child_parser.add_argument('-C', '--compress', action='store_true',
			help='Compress on export (vm-exports only)')
		child_parser.add_argument('-F', '--format', choices=[ 'raw', 'vhd' ], metavar='FORMAT',
			help='VDI export format (vdi-exports only, Default: raw)')
		child_parser.add_argument('--preview', action='store_true', help='Preview resulting config and exit')
		child_parser.add_argument('-e', '--vm-export', action='append', dest='vm_exports', metavar='STRING',
			help='VM name or Regex for vm-export (Default: ".*") NOTE: Specify multiple times for multiple values)')
		child_parser.add_argument('-E', '--vdi-export', action='append', dest='vdi_exports', metavar='STRING',
			help='VM name or Regex for vdi-export (Default: None) NOTE: Specify multiple times for multiple values)')
		child_parser.add_argument('-x', '--exclude', action='append', dest='excludes', metavar='STRING',
			help='VM name or Regex to exclude (Default: None) NOTE: Specify multiple times for multiple values)')

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