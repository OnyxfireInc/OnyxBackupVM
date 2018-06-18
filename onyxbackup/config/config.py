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

import ConfigParser
import logging
from json import load
from logging.config import dictConfig
from os import getenv
from os.path import abspath, dirname, exists, expanduser, join
from sys import argv
import onyxbackup.util as util

class Configurator(object):
 
	def __init__(self):
		self._h = util.Helper()
		path = abspath(argv[0])
		self._base_dir = dirname(path)

	def configure(self, args):
		self._setup_logging(args)
		self.logger.debug('(i) Setting defaults for configuration')
		conf_parser = ConfigParser.SafeConfigParser()
		conf_parser.add_section('xenserver')
		conf_parser.set('xenserver', 'share_type', 'nfs')
		conf_parser.set('xenserver', 'backup_dir', join(self._base_dir, 'exports'))
		conf_parser.set('xenserver', 'space_threshold', '20')
		conf_parser.set('xenserver', 'max_backups', '4')
		conf_parser.set('xenserver', 'compress', 'False')
		conf_parser.set('xenserver', 'vdi_export_format', 'raw')
		conf_parser.set('xenserver', 'pool_backup', 'False')
		conf_parser.set('xenserver', 'host_backup', 'False')
		conf_parser.add_section('smtp')
		conf_parser.set('smtp', 'smtp_enabled', 'false')
		conf_parser.set('smtp', 'smtp_auth', 'false')
		conf_parser.set('smtp', 'smtp_user', 'user')
		conf_parser.set('smtp', 'smtp_pass', 'password')
		conf_parser.set('smtp', 'smtp_file', join(self._base_dir, 'logs', 'backup.rpt'))
		conf_parser.set('smtp', 'smtp_server', 'localhost')
		conf_parser.set('smtp', 'smtp_port', '25')
		conf_parser.set('smtp', 'smtp_hostname', 'xenserver')
		conf_parser.set('smtp', 'smtp_timeout', '15')
		conf_parser.set('smtp', 'smtp_subject', 'OnyxBackup - VM Backup Report')
		conf_parser.set('smtp', 'smtp_from', 'xenserver@localhost')
		conf_parser.set('smtp', 'smtp_to', 'you@example.com')
		self.logger.debug('(i) Reading updates to config from configuration files')
		conf_parser.read(['{}/etc/onyxbackup.cfg'.format(self._base_dir), '/etc/onyxbackup.cfg', expanduser('~/onyxbackup.cfg')])
		if args.config:
			self.logger.debug('(i) Reading configuration file provided on command-line')
			conf_parser.read([args.config])
		return self._sanitize_options(conf_parser)

	def validate_config(self, options):
		self.logger.debug('(i) Validating configuration options')

		self.logger.debug('(i) -> Checking if space_threshold within range')
		if options['space_threshold'] < 1:
			raise ValueError('(!) space_threshold out of range -> {}'.format(options['space_threshold']))

		self.logger.debug('(i) -> Checking if max_backups within range')
		if options['max_backups'] < 1:
			raise ValueError('(!) max_backups out of range -> {}'.format(options['max_backups']))

		self.logger.debug('(i) -> Checking if vdi_export_format is valid value')
		if options['vdi_export_format'] != 'raw' and options['vdi_export_format'] != 'vhd':
			raise ValueError('(!) vdi_export_format invalid -> {}'.format(options['vdi_export_format']))

		self.logger.debug('(i) -> Checking if backup_dir exists')
		if not self._h.verify_path(options['backup_dir']):
			raise ValueError('(!) backup_dir does not exist and could not be created -> {}'.format(options['backup_dir']))

		self.logger.debug('(i) -> Checking if backup_dir writeable')
		if not self._h.verify_path_writeable(options['backup_dir']):
			raise ValueError('(!) backup_dir not writeable -> {}'.format(options['backup_dir']))

		self.logger.debug('(i) -> Checking if both vm_exports and vdi_exports are empty')
		if ( not options['vm_exports'] ) and ( not options['vdi_exports'] ):
			self.logger.debug('(i) -> Setting vm_export to default -> .* (all VMs)')
			options['vm_exports'] = ['.*']

	# Private Functions

	def _sanitize_options(self, parser):
		self.logger.debug('(i) Sanitizing configuration options')
		options = {}

		options['share_type'] = parser.get('xenserver', 'share_type')
		if options['share_type'] == 'smb':
			options['backup_dir'] = parser.get('xenserver', 'backup_dir').replace("/", "\\")
		else:
			options['backup_dir'] =  parser.get('xenserver', 'backup_dir')
		options['space_threshold'] = parser.getint('xenserver', 'space_threshold')
		options['max_backups'] = parser.getint('xenserver', 'max_backups')
		options['compress'] = parser.getboolean('xenserver', 'compress')
		options['vdi_export_format'] = parser.get('xenserver', 'vdi_export_format')
		options['pool_backup'] = parser.getboolean('xenserver', 'pool_backup')
		options['host_backup'] = parser.getboolean('xenserver', 'host_backup')
		options['vm_exports'] = parser.get('xenserver', 'vm_exports').split(',') if parser.has_option('xenserver', 'vm_exports') else []
		options['vdi_exports'] = parser.get('xenserver', 'vdi_exports').split(',') if parser.has_option('xenserver', 'vdi_exports') else []
		options['excludes'] = parser.get('xenserver', 'excludes').split(',') if parser.has_option('xenserver', 'excludes') else []
		options['smtp_enabled'] = parser.getboolean('smtp', 'smtp_enabled')
		options['smtp_auth'] = parser.getboolean('smtp', 'smtp_auth')
		options['smtp_user'] = parser.get('smtp', 'smtp_user')
		options['smtp_pass'] = parser.get('smtp', 'smtp_pass')
		options['smtp_file'] = parser.get('smtp', 'smtp_file')
		options['smtp_server'] = parser.get('smtp', 'smtp_server')
		options['smtp_port'] = parser.getint('smtp', 'smtp_port')
		options['smtp_hostname'] = parser.get('smtp', 'smtp_hostname')
		options['smtp_timeout'] = parser.getint('smtp', 'smtp_timeout')
		options['smtp_subject'] = parser.get('smtp', 'smtp_subject')
		options['smtp_from'] = parser.get('smtp', 'smtp_from')
		options['smtp_to'] = parser.get('smtp', 'smtp_to')
		return options

	def _setup_logging(self, args):
		self.logger = logging.getLogger(__name__)
		log_level = 'INFO'
		if args.log_level:
			log_level = args.log_level.upper()

		ch = logging.StreamHandler()
		log_format = "%(message)s"
		formatter = logging.Formatter(fmt=log_format)
		ch.setFormatter(formatter)
		self.logger.addHandler(ch)
		self.logger.setLevel(log_level)
		
		self.logger.debug('(i) Determining logging configuration')
		DEFAULT_LOGGING={
			"version": 1,
			"disable_existing_loggers": False,
			"formatters": {
				"simple": {
					"format": "%(message)s"
				},
				"detailed": {
					"format": "%(asctime)s - %(levelname)s: %(message)s [ %(module)s:%(funcName)s():%(lineno)s ]",
					"datefmt": "%m/%d/%Y %I:%M:%S %p"
				}
			},
			"handlers": {
				"console": {
					"class": "logging.StreamHandler",
					"formatter": "simple",
					"stream": "ext://sys.stdout"
				},
				"report": {
					"class": "logging.FileHandler",
					"formatter": "simple",
					"filename": join(self._base_dir, 'logs', 'backup.rpt'),
					"mode": "w",
					"encoding": "utf8"
				},
				"file": {
					"class": "logging.handlers.RotatingFileHandler",
					"level": "WARNING",
					"formatter": "detailed",
					"filename": join(self._base_dir, 'logs', 'onyxbackup-xs.log'),
					"maxBytes": 10485760,
					"backupCount": 20,
					"encoding": "utf8"
				},
				"debug": {
					"class": "logging.handlers.RotatingFileHandler",
					"level": "DEBUG",
					"formatter": "detailed",
					"filename": join(self._base_dir, 'logs', 'debug.log'),
					"maxBytes": 10485760,
					"backupCount": 20,
					"encoding": "utf8"
				}
			},
			"loggers": {
				"onyxbackup": {
					"level": log_level,
					"handlers": ["console", "report", "file", "debug"],
					"propagate": 0
				}
			},
			"root": {
				"level": 'WARNING',
				"handlers": ["console"]
			}
		}

		cfg_file = join(self._base_dir, 'etc', 'logging.json')
		value = getenv('LOG_CFG', None)
		if value:
			self.logger.debug('(i) -> Logging config environment variable set: {}'.format(value))
			cfg_file = value
		if exists(cfg_file):
			self.logger.debug('(i) -> Logging config file exists. Loading...')
			with open(cfg_file, 'r') as f:
				try:
					log_config = load(f)
					dictConfig(log_config)
					self.logger.debug('(i) -> Configuration successfully loaded -> {}'.format(cfg_file))
				except Exception as e:
					self.logger.warning('(!) Error loading logging configuration from file: {}'.format(e))
					self.logger.debug('(i) -> Falling back to default configuration')
					dictConfig(DEFAULT_LOGGING)
		else:
			self.logger.debug('(i) -> Logging config file doesn\'t exist: loading default configuration')
			dictConfig(DEFAULT_LOGGING)