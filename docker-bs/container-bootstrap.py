#!/usr/bin/python
from __future__ import print_function
from github import Github
# noinspection PyUnresolvedReferences
from github.Repository import Repository
# noinspection PyUnresolvedReferences
from github.NamedUser import NamedUser
from github.GithubException import UnknownObjectException
from plumbum import local
import subprocess
from ssl import SSLError
import tarfile
import plumbum
import logging
import base64
import sys
import os

__path__ = os.path.realpath(__file__)
__dir_path__ = os.path.dirname(__path__)
__file_name__ = os.path.basename(__file__)

PRINT_LOG = True
LOG_LEVEL = logging.DEBUG

log = logging.getLogger("cont-bootstrap")
log.setLevel(LOG_LEVEL)
if PRINT_LOG:
	ch = logging.StreamHandler()
	ch.setLevel(LOG_LEVEL)
	log.addHandler(ch)
log_func = log.debug


# clem 13/09/2017
class TermColoring(enumerate):
	HEADER = '\033[95m'
	OK_BLUE = '\033[94m'
	T_BLUE = '\033[34m'
	OK_GREEN = '\033[92m'
	WARNING = '\033[93m'
	FAIL = '\033[91m'
	END_C = '\033[0m'
	BOLD = '\033[1m'
	UNDERLINE = '\033[4m'

	@classmethod
	def ok_blue(cls, text):
		return cls.OK_BLUE + text + cls.END_C

	@classmethod
	def t_blue(cls, text):
		return cls.T_BLUE + text + cls.END_C

	@classmethod
	def ok_green(cls, text):
		return cls.OK_GREEN + text + cls.END_C

	@classmethod
	def fail(cls, text):
		return cls.FAIL + text + cls.END_C

	@classmethod
	def warning(cls, text):
		return cls.WARNING + text + cls.END_C

	@classmethod
	def header(cls, text):
		return cls.HEADER + text + cls.END_C

	@classmethod
	def bold(cls, text):
		return cls.BOLD + text + cls.END_C

	@classmethod
	def underlined(cls, text):
		return cls.UNDERLINE + text + cls.END_C

	@classmethod
	def cmd_print(cls, command, print_func=log_func):
		print_func(cls.ok_green('$ ') + command)

	@classmethod
	def info_print(cls, msg, print_func=log_func, color=None):
		if not color:
			color = cls.t_blue
		print_func(color('%s' % msg))


cmd_print = TermColoring.cmd_print
out_print = TermColoring.info_print


# clem 30/08/2017 form line 203 @ https://goo.gl/Wquh6Z clem 08/04/2016 + 10/10/2016
def this_function_caller_name(delta=0):
	""" Return the name of the calling function's caller

	:param delta: change the depth of the call stack inspection
	:type delta: int

	:rtype: str
	"""
	import sys
	# noinspection PyProtectedMember
	return sys._getframe(2 + delta).f_code.co_name if hasattr(sys, "_getframe") else ''


# TODO throw an error if key is invalid, otherwise azure keeps on returning "resource not found" error
# clem 22/09/2016 duplicated from utilities/__init__
def get_key_bis(name=''):
	if name.endswith('_secret'):
		name = name[:-7]
	if name.startswith('.'):
		name = name[1:]
	try:
		full_path = '%s/.%s_secret' % (CONF_RES_FOLDER.value, name)
		log_func('accessing key at %s from %s' % (full_path, this_function_caller_name()))
		with open(full_path) as f:
			return str(f.read()).replace('\n', '').replace('\r', '')
	except IOError:
		out_print('could not read key %s' % name, log.error, TermColoring.fail)
	return ''


class EnvVar(object):
	name = ''
	_value = ''
	_exported = False

	def __init__(self, name, value, auto_export=True):
		self.name = name.upper()
		self._value = value
		if auto_export:
			self.export()

	def __str__(self):
		return "%s('%s', '%s')" % (self.__class__.name, self.name, self.value)

	@property
	def all(self):
		return self.name, self.value

	def export(self):
		cmd_print("export %s='%s'" % self.all, log.debug)
		os.environ[self.name] = self._value
		self._exported = True

	@property
	def value(self):
		return self._value

	@staticmethod
	def get_var(var_name, *more_vars):
		""" Return the value, or value n-uples of specified env_vars

		:param var_name: a env_var name
		:type var_name: str
		:param more_vars: a n-uples of env_vars names
		:type more_vars: str
		"""
		a_list = list()
		var_value = os.environ.get(var_name, '')
		for each in more_vars:
			a_list.append(os.environ.get(each, ''))
		if a_list:
			a_list = tuple([var_value] + a_list)
		else:
			a_list = var_value
		return a_list


get_var = EnvVar.get_var

# TODO all these from config/ENV
CONF_RES_FOLDER = EnvVar('RES_FOLDER', '/res')
CONF_IN_FILE = EnvVar('IN_FILE', "in.tar.xz")               # file name to use for the input/job set archive
CONF_OUT_FILE = EnvVar('OUT_FILE', "out.tar.xz")            # file name to use fot the output/result archive
HOME = EnvVar('HOME', get_var('HOME'))
# path to the final archive to be created
CONF_OUT_FILE_PATH = EnvVar('OUT_FILE_PATH', "%s/%s" % (HOME.value, CONF_OUT_FILE.value))
CONF_NEXT_SH = EnvVar('NEXT_SH', "%s/run.sh" % HOME.value)  # path of the next file to

# TODO all these from config/ENV
GIT_HUB_COMMIT = 'heads/new_storage'
GIT_HUB_USERNAME = 'Fclem'
GIT_HUB_REPO = 'isbio2'
GIT_HUB_TOKEN = get_key_bis('git_hub_token') or get_var('GIT_HUB_TOKEN') or ''
GIT_HUB_FOLDER_PATH = 'isbio/storage'
#  run
###
RX_RX_ = 0o550
RW_RW_ = 0o660
RWX_RWX_ = 0o770
storage = ''


# clem 30/08/2017 from line 6 @ https://goo.gl/BLuUFD 03/02/2016
def human_readable_byte_size(num, suffix='B'):
	if type(num) is not int:
		if os.path.isfile(num):
			num = os.path.getsize(num)
		else:
			raise TypeError('num should either be a integer file size, or a valid file path')
	for unit in ['', 'Ki', 'Mi', 'Gi', 'Ti', 'Pi', 'Ei', 'Zi']:
		if abs(num) < 1024.0:
			return "%3.1f%s%s" % (num, unit, suffix)
		num /= 1024.0
	return "%.1f%s%s" % (num, 'Yi', suffix)


class GitHubDownloader(object):
	_git_hub_client = None
	_repo = None
	_user = None
	_git_user_name = ''
	_git_repo_name = ''

	def __init__(self, username, token, repo):
		""" initialize the github client

		:param username: the github user name
		:type username: str
		:param token: the github auth token for that user as found at https://github.com/settings/tokens
		:type token: str
		:param repo: the repository name
		:type repo: str
		"""
		self._git_hub_client = Github(username, token)
		self._git_user_name = username
		self._git_repo_name = repo

	def _git_safe_query(self, func, *args):
		""" wrapper to execute any github query with ssl_timeout handling and auto-retry

		:param func: The function to call to run the query
		:type func: callable
		:param args: any
		:type args:
		"""
		try:
			return func(*args)
		except SSLError:
			out_print('trying again %s' % func.func_name)
			# try again
			return self._git_safe_query(func, *args)

	@property
	def user(self):
		""" retrieved and cache GitHub user as defined as username in init

		:return: the named user
		:rtype: :class:`github.NamedUser.NamedUser`
		"""
		if not self._user:
			def user_getter():
				""" getter for GitHub user

				:return: the named user
				:rtype: :class:`github.NamedUser.NamedUser`
				"""
				out_print('getting GitHub user %s' % self._git_user_name)
				return self._git_hub_client.get_user(self._git_user_name)
			self._user = self._git_safe_query(user_getter)
		return self._user

	@property
	def repo(self):
		""" retrieved and cache GitHub repository as defined in self._git_repo_name

		:return:
		:rtype: :class:`github.Repository.Repository`
		"""
		if not self._repo:
			def repo_getter():
				""" getter for GitHub repository

				:return:
				:rtype: :class:`github.Repository.Repository`
				"""
				out_print('getting GitHub repository %s/%s' % (self._git_user_name, self._git_repo_name))
				return self.user.get_repo(self._git_repo_name)
			self._repo = self._git_safe_query(repo_getter)
		return self._repo

	# clem 13/09/2017
	def exists(self, file_path, ref):
		""" check if a specific file exists and is non empty

		:param file_path: file path
		:type file_path: str
		:param ref: commit
		:type ref: str
		:return: is_success
		:rtype: bool
		:raise: FileNotFoundError
		"""
		try:
			a_file = self.repo.get_file_contents(file_path, ref)
			assert int(a_file.raw_headers.get('content-length', 0)) > 0, 'file %s exists but is empty' % file_path
			return True
		except UnknownObjectException:
			raise FileNotFoundError('There is no such storage module as "%s" available' % os.path.basename(file_path))

	def download(self, content_file, save_to=None, do_fail=False):
		""" Download and saves the specified content file

		:param content_file: the GithubObject to be downloaded as from self.repo.get_dir_contents or
		self.repo.get_contents
		:type content_file: github.ContentFile.ContentFile
		:param save_to: an optional path to save the file to. If None use the name from github and stores it in the
		local folder
		:type save_to: str
		:param do_fail: should the function raise if for some reason the download raises IOError (will retry once
		after fixing existing target file permission and raise if unsuccessful)
		:type do_fail: bool
		:return: success
		:rtype: bool
		"""
		if not save_to:
			save_to = content_file.name

		try:
			with open(save_to, 'w') as f:
				content = base64.b64decode(content_file.raw_data.get('content', ''))
				first_line = content.split('\n')[0]
				is_executable = first_line[0:2] == '#!'
				f.write(content)
		except IOError as e:
			log_to = log.warning
			if do_fail: # prevents infinite recursion if chmod has no effect
				log_to = log.exception
			out_print('%s on %s %s' % (e.strerror, content_file.path, save_to), log_to)
			if e.errno == 13: # Permission denied
				os.chmod(save_to, RW_RW_)
			return self.download(content_file, save_to, True)
		log_func('%s % 8s\t%s' % (content_file.sha, human_readable_byte_size(content_file.size), content_file.name))
		if is_executable:
			os.chmod(save_to, RWX_RWX_)
		return True

	# clem 13/09/2017
	def download_folder(self, folder_path, ref, save_to=None, do_fail=False):
		"""Download and saves the specified folder content

		:param folder_path: the folder path to be downloaded
		:type folder_path: str
		:param ref: commit
		:type ref: str
		:param save_to: path to save downloaded files to
		:type save_to: str
		:param do_fail: should the function raise if for some reason the download raises IOError (will retry once
		after fixing existing target file permission and raise if unsuccessful)
		:type do_fail: bool
		:return: number of downloaded files
		:rtype: int
		"""
		storage_dir = self.repo.get_dir_contents(folder_path, ref)
		for each in storage_dir:
			self.download(each, save_to, do_fail)
		return len(storage_dir)


def input_pre_handling():
	""" Parse arguments from command line

	:return: (job_id, storage)
	:rtype: tuple[basestring, basestring]
	"""
	assert len(sys.argv) >= 2

	job_id = str(sys.argv[1])
	storage_mod = '' if len(sys.argv) <= 2 else str(sys.argv[2])

	return job_id, storage_mod


def download_storage(storage_module=None):
	""" if the python storage file is not present, it download the whole storage folder from github

	:param storage_module: name of the python storage module
	:type storage_module: str
	"""
	os.chdir(get_var('RES_FOLDER'))
	if not storage_module or not os.path.exists(storage_module):
		git_hub = GitHubDownloader(GIT_HUB_USERNAME, GIT_HUB_TOKEN, GIT_HUB_REPO)

		# check if the specified storage module is in the GitHub folder
		if not storage_module or git_hub.exists('%s/%s' % (GIT_HUB_FOLDER_PATH, storage_module), GIT_HUB_COMMIT):
			out_print('Downloading storage modules from GitHub...', log.info)
			total_dl = git_hub.download_folder(GIT_HUB_FOLDER_PATH, GIT_HUB_COMMIT)
			out_print('done, %s files downloaded' % total_dl)
	else:
		out_print('storage module %s already exists, skipping download' % storage_module, log.info)
	return 0


class ShellReturn(plumbum.commands.processes.ProcessExecutionError):
	def __init__(self, e):
		# if isinstance(e, plumbum.commands.processes.ProcessExecutionError):
		super(ShellReturn, self).__init__(e.argv, e.retcode, e.stdout, e.stderr)

	def __nonzero__(self): # PY2
		return False

	def __bool__(self): # PY3
		return self.__nonzero__

	def __repr__(self):
		return plumbum.commands.processes.ProcessExecutionError(argv=self.argv, retcode=self.retcode,
			stdout=self.stdout, stderr=self.stderr)


def shell_run(func, *args, **kwargs):
	""" Wrapper for plumbum

	:param func:
	:type func: LocalMachine
	:param args:
	:type args:
	:param kwargs:
	:type kwargs:
	:return:
	:rtype: unicode or ShellReturn
	"""
	retcode = kwargs.get('retcode', 0)
	no_fail = kwargs.get('no_fail', True)
	verbose = kwargs.get('verbose', True)
	try:
		if verbose:
			cmd_print('%s %s' % (str(func), ''.join(args)))
		result = func(*args, retcode=retcode)
		if verbose:
			out_print(result)
		return result
	except plumbum.commands.processes.ProcessExecutionError as e:
		if not no_fail:
			raise e
		if verbose:
			log_func(str(e))
		return ShellReturn(e)


# clem 19/09/2017
def shell_run_bis(command_and_args, retcode=0, verbose=True):
	if isinstance(command_and_args, list):
		command_and_args = ' '.join(command_and_args)
	if verbose:
		cmd_print(command_and_args)
	process = subprocess.Popen(command_and_args, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	process.wait()
	log.info('stdout:')
	for line in process.stdout:
		log.info(line)
	if process.stderr:
		log.warning('stderr:')
		for line in process.stderr:
			log.warning(line)
	result = process.returncode
	if verbose:
		out_print(result)
	return result == retcode


# clem 13/09/2017
class FileNotFoundError(OSError):
	pass


# clem 15/09/2017
def save_env(splitter=' '):
	to_save = str(get_var('SAVE_LIST'))
	if to_save:
		for each in to_save.split(splitter):
			a_var = str(get_var(each))
			if a_var:
				file_name = '%s/.%s_secret' % (CONF_RES_FOLDER.value, each.lower())
				with open(file_name, 'w') as f:
					f.write(a_var)
					out_print('saved %s to %s' % (each, file_name))
			os.environ[each] = ''
			del os.environ[each]


def main():
	global storage
	job_id, storage = input_pre_handling()

	save_env()

	if not storage:
		out_print('no storage module specified, running run.sh for backward compatibility.')
		base_path = os.path.dirname(__file__)
		cmd_print('%s/run.sh' % base_path)
		out_print(local['%s/run.sh' % base_path](job_id))
		exit(0)

	# TODO get the var_names from settings/config
	storage_var = EnvVar('STORAGE_FN', '%s.py' % storage) # name of the storage module python file

	download_storage(storage_var.value)

	# TODO store keys

	storage_module_shell = '%s/%s' % (CONF_RES_FOLDER.value, storage_var.value)

	out_print(shell_run_bis([storage_module_shell, 'upgrade']))

	result = shell_run_bis([storage_module_shell, 'load', job_id])
	if result:
		source_file = '%s/%s' % get_var('HOME', 'IN_FILE')
		extract_to = '%s/' % get_var('HOME')
		out_print('extracting %s to %s' % (source_file, extract_to), log.info)
		with tarfile.open(source_file, "r") as in_file:
			in_file.extractall(path=extract_to)
		out_print('done', log.info)
		os.chmod(CONF_NEXT_SH.value, RX_RX_)

		result = shell_run_bis([CONF_NEXT_SH.value])
		# TODO hooking too
		result2 = shell_run_bis([storage_module_shell, 'save', job_id])
		return finished(result2 and result)
	exit(77)


def finished(success):
	global storage
	if success:
		out_print('All Done !', log.info)
		exit(0)
	else:
		out_print('%s failure !' % storage, log.critical)
		exit(88)


if __name__ == '__main__':
	if len(sys.argv) >= 2 and sys.argv[1] == 'git_download':
		# commodity for docker build to have a copy of file upon building the container
		exit(download_storage())

	main()
	exit(99)
