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

import datetime, subprocess
from logging import getLogger
from os import devnull, mkdir, remove
from os.path import exists, getsize, join
from shlex import split

class Helper():

	def __init__(self):
		self.logger = getLogger(__name__)

	def delete_file(self, file):
		if exists(file):
			self.logger.debug('(i) -> File exists, deleting...')
			try:
				remove(file)
				return True
			except OSError as e:
				self.logger.critical('(!) Unable to delete file "{}": {}'.format(file, e))
		else:
			self.logger.debug('(i) -> File does not exist: {}'.format(file))
		return False

	def get_elapsed(self, start, end, as_string=True):
		difference = end - start
		elapsed = ''
		symbol = ''
		if difference.seconds < 60:
			elapsed = difference.seconds
			symbol = 's'
		elif difference.seconds < 3600:
			elapsed = difference.seconds / 60
			symbol = 'm'
		elif difference.seconds < 86400:
			elapsed = (difference.seconds / 60) / 60
			symbol = 'h'
		else:
			elapsed = difference.days
			symbol = 'd'
		if as_string:
			elapsed = '{}{}'.format(str(elapsed), symbol)
		return elapsed

	def get_file_size(self, file):
		size = 0
		symbol = 'B'
		if exists(file):
			try:
				size = getsize(file)
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
			self.logger.debug('(i) File does not exist: {}'.format(file))

		sizeString = '{}{}'.format(str(size), symbol)
		return sizeString

	def get_cmd_result(self, cmd_line, strip_newline=True):
		self.logger.debug('(i) -> Running command: {}'.format(cmd_line))
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
			now = datetime.datetime.now()
		else:
			now = date
		str = '%02d%02d%04d-%02d%02d%02d' \
			% (now.month, now.day, now.year, now.hour, now.minute, now.second)
		return str

	def get_remaining_space(self, filesystem):
		cmd = '/bin/df --output=pcent {}'.format(filesystem)
		fs_info = self.get_cmd_result(cmd)
		try:
			output = fs_info.split('\n')[1].lstrip()[:-1]
			self.logger.debug('(i) -> Used space: {}'.format(output))
			percent_used = int(output)
		except ValueError as e:
			self.logger.debug('(i) -> Unexpectedly returned non-integer; defaulting to 100%')
			percent_used = int(100)
		percent_remaining = 100 - percent_used
		return percent_remaining

	def get_time_string(self, date=''):
		if not date:
			now = datetime.datetime.now()
		else:
			now = date
		str = '%02d:%02d:%02d' \
			% (now.hour, now.minute, now.second)
		return str

	def run_cmd(self, cmd_line):
		self.logger.debug('(i) -> Running command: {}'.format(cmd_line))
		cmd = split(cmd_line)
		FNULL = open(devnull, 'w')
		result = subprocess.call(cmd, stdout=FNULL, stderr=subprocess.STDOUT)
		FNULL.close()
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
				self.logger.debug('(i) -> Command returned non-zero exit status: {}'.format(cmd))
				return False
			else:
				cmd = '/bin/rm -f "{}"'.format(touchfile)
				self.run_cmd(cmd)
				return True
		except OSError as e:
			self.logger.error('(!) Unable to write to directory {}: {}'.format(path, e))
		return False