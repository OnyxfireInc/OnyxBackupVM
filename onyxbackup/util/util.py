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

import subprocess
from datetime import datetime
from logging import getLogger
from os import devnull, mkdir, remove
from os.path import exists, getsize, join
from shlex import split
from decimal import Decimal

class Helper():

	def __init__(self):
		self.logger = getLogger(__name__)

	def delete_file(self, file):
		if exists(file):
			self.logger.debug('(i) ---> File exists, deleting...')
			try:
				remove(file)
				return True
			except OSError as e:
				self.logger.error('(!) Unable to delete file "{}": {}'.format(file, e))
		else:
			self.logger.debug('(i) ---> File does not exist: {}'.format(file))
			return True
		return False

	def get_cmd_result(self, cmd_line, strip_newline=True):
		self.logger.debug('(i) ---> Running command: {}'.format(cmd_line))
		result = ''
		cmd = split(cmd_line)
		try:
			result = subprocess.check_output(cmd)
			if strip_newline:
				result = result.rstrip("\n")
		except subprocess.CalledProcessError:
			self.logger.debug('(!) Command returned with non-zero exit status')
		return result

	def get_date_string(self, date=''):
		if date == '':
			now = datetime.now()
		else:
			now = date
		str = '%02d%02d%04d-%02d%02d%02d' \
			% (now.month, now.day, now.year, now.hour, now.minute, now.second)
		return str

	def get_elapsed(self, timedelta, granularity=2):
		intervals = (
			('weeks', 604800),
			('days', 86400),
			('hours', 3600),
			('minutes', 60),
			('seconds', 1),
		)
		result = []
		seconds = timedelta.total_seconds()

		for name, count in intervals:
			value = seconds // count
			if value:
				seconds -= value * count
				if value == 1:
					name = name.rstrip('s')
				result.append("{}{}".format(value, name))
		return ' '.join(result[:granularity])

	def get_file_size(self, file):
		size = 0
		symbol = 'B'
		if exists(file):
			try:
				size = Decimal(float(getsize(file)))
				if size < 1024:
					symbol = 'B'
				elif (size / 1024) < 1024:
					size = size / 1024
					symbol = 'KB'
				elif (size / (1024 * 1024)) < 1024:
					size = size / (1024 * 1024)
					symbol = 'MB'
				else:
					size = size / (1024 * 1024 * 1024)
					symbol = 'GB'
			except OSError as e:
				self.logger.error('(!) Unable to get file size: {}'.format(e))
		else:
			self.logger.debug('(i) --> File does not exist: {}'.format(file))

		sizeString = '{}{}'.format(str(size.quantize(Decimal('0.00'))), symbol)
		return sizeString

	def get_remaining_space(self, filesystem):
		cmd = '/bin/df --output=pcent {}'.format(filesystem)
		fs_info = self.get_cmd_result(cmd)
		try:
			output = fs_info.split('\n')[1].lstrip()[:-1]
			self.logger.debug('(i) ---> Used space: {}%'.format(output))
			percent_used = int(output)
		except ValueError as e:
			self.logger.debug('(i) ---> Unexpectedly returned non-integer; defaulting to 100%')
			percent_used = int(100)
		percent_remaining = 100 - percent_used
		return percent_remaining

	def get_time_string(self, date=''):
		if not date:
			now = datetime.now()
		else:
			now = date
		str = '%02d:%02d:%02d' \
			% (now.hour, now.minute, now.second)
		return str

	def run_cmd(self, cmd_line):
		self.logger.debug('(i) ---> Running command: {}'.format(cmd_line))
		cmd = split(cmd_line)
		with open(devnull, 'w') as FNULL:
			result = subprocess.call(cmd, stdout=FNULL, stderr=subprocess.STDOUT)
		return result

	def verify_path(self, path):
		if not exists(path):
			try:
				mkdir(path)
				return True
			except OSError as e:
				self.logger.error('(!) Unable to create directory {} : {}'.format(path, e))
				return False
		return True

	def verify_path_writeable(self, path):
		touchfile = join(path, "write.test")
		cmd = '/bin/touch "{}"'.format(touchfile)
		try:
			result = self.run_cmd(cmd)
			if result <> 0:
				self.logger.debug('(i) ---> Command returned non-zero exit status: {}'.format(cmd))
				return False
			else:
				cmd = '/bin/rm -f "{}"'.format(touchfile)
				self.run_cmd(cmd)
				return True
		except OSError as e:
			self.logger.error('(!) Unable to write to directory {}: {}'.format(path, e))
		return False
