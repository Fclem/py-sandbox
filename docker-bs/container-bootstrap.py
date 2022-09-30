#!/usr/bin/python
from __future__ import print_function
from github import Github
# noinspection PyUnresolvedReferences
from github.Repository import Repository
# noinspection PyUnresolvedReferences
from github.NamedUser import NamedUser
from github.GithubException import UnknownObjectException
from res import StorageModulePrototype
import subprocess
import importlib
from ssl import SSLError
import tarfile
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
	ch = logging.StreamHandler(sys.stdout)
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
CONF_RES_FOLDER = EnvVar('RES_FOLDER', '/res')              # the resource folder contains keys and storage modules
CONF_IN_FILE = EnvVar('IN_FILE', "in.tar.xz")               # file name to use for the input/job set archive
CONF_OUT_FILE = EnvVar('OUT_FILE', "out.tar.xz")            # file name to use fot the output/result archive
CONF_HOME = EnvVar('HOME', get_var('HOME'))                 # home folder is where job archive will be extracted
# path to the final archive to be created
CONF_OUT_FILE_PATH = EnvVar('OUT_FILE_PATH', "%s/%s" % (CONF_HOME.value, CONF_OUT_FILE.value))
# path to the local file to download the job archive to
CONF_IN_FILE_PATH = EnvVar('IN_FILE_PATH', "%s/%s" % (CONF_HOME.value, CONF_IN_FILE.value))
CONF_NEXT_SH = EnvVar('NEXT_SH', "%s/run.sh" % CONF_HOME.value)  # path of the next script to trigger the job

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
		""" wrapper to execute any github query with ssl_timeout handling and auto-retry (Has exception management)

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
		""" check if a specific file exists and is non empty (Has exception management)

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
	assert len(sys.argv) >= 2, 'Not enough arguments'

	job_id = str(sys.argv[1])
	storage_mod = '' if len(sys.argv) <= 2 else str(sys.argv[2])

	return job_id, storage_mod


def nop():
	""" does nothing """
	pass


def download_storage(storage_module=None, verbose=True):
	""" if the python storage file is not present, it download the whole storage folder from github

	Has exception management

	:param storage_module: name of the python storage module
	:type storage_module: str
	:param verbose: Should extra info be directed to log output (default to True)
	:type verbose: bool | None
	:return: is success (will return True even if nothing was downloaded, provided there was no errors)
	:rtype: bool
	"""
	try:
		os.chdir(get_var('RES_FOLDER'))
		if not storage_module or not os.path.exists(storage_module):
			git_hub = GitHubDownloader(GIT_HUB_USERNAME, GIT_HUB_TOKEN, GIT_HUB_REPO)

			# check if the specified storage module is in the GitHub folder
			if not storage_module or git_hub.exists('%s/%s' % (GIT_HUB_FOLDER_PATH, storage_module), GIT_HUB_COMMIT):
				out_print('Downloading storage modules from GitHub...', log.info) if verbose else nop()
				total_dl = git_hub.download_folder(GIT_HUB_FOLDER_PATH, GIT_HUB_COMMIT)
				out_print('done, %s files downloaded' % total_dl) if verbose else nop()
		else:
			out_print('storage module %s already exists, skipping download' % storage_module, log.info)
		return True
	except Exception as e:
		log.error('Error while downloading storage modules: %s' % str(e))
	return False


# deleted class ShellReturn on 22/09/2017 as it was deprecated (see commit f3f3e10154210b2cbd2855fef169fd623141387c)
# deleted shell_run on 22/09/2017 as it was deprecated (see commit f3f3e10154210b2cbd2855fef169fd623141387c)
# deleted shell_run_bis on 22/09/2017 as it was deprecated (see commit f3f3e10154210b2cbd2855fef169fd623141387c)


# clem 22/09/2017
def shell_run_raw(command, args=list(), verbose=True):
	""" run a BLOCKING shell command using subprocess.call with Exception management

	:param command: the command to run. must be a valid shell command, or valid path with no arguments
	:type command: basestring
	:param args: a list of arguments to pass to the command
	:type args: list
	:param verbose: Should extra info be directed to log output (default to True)
	:type verbose: bool | None
	:return: the retcode of the shell process
	:rtype: int
	"""
	assert isinstance(args, list)
	retcode = 127
	print_line = command + ' ' + ' '.join(args) if args else command
	try:
		cmd_print(print_line) if verbose else nop()
		retcode = subprocess.call([command] + args)
	except Exception as e:
		log.error('Error while running "%s": %s' % (print_line, str(e)))
	return retcode


# clem 22/09/2017
def shell_run(command, args=list(), retcode=0, verbose=True):
	""" run a BLOCKING shell command using subprocess.call with Exception management

	:param command: the command to run. must be a valid shell command, or valid path with no arguments
	:type command: basestring
	:param args: a list of arguments to pass to the command
	:type args: list
	:param retcode: the expected return code for the function to return True
	:type retcode: int
	:param verbose: Should extra info be directed to log output (default to True)
	:type verbose: bool | None
	:return: is command return code equals retcode
	:rtype: bool
	"""
	return shell_run_raw(command, args, verbose) == retcode


# clem 13/09/2017
class FileNotFoundError(OSError):
	pass


# clem 15/09/2017
def save_env(splitter=' ', verbose=True):
	""" Saves any env var that is listed in the env var SAVE_LIST (space separated) and then deletes it from env

	Useful for passing on keys to the container
	Has exception management

	:param splitter: the separation char used in SAVE_LIST (default to space)
	:type splitter: str
	:param verbose: do print a debug line for each saved env var
	:type verbose: bool | None
	:return: is success, something was saved, return False otherwise
	:rtype: bool
	"""
	try:
		to_save = str(get_var('SAVE_LIST'))
		if to_save:
			for each in to_save.split(splitter):
				a_var = str(get_var(each))
				if a_var:
					file_name = '%s/.%s_secret' % (CONF_RES_FOLDER.value, each.lower())
					with open(file_name, 'w') as f:
						f.write(a_var)
						out_print('saved %s to %s' % (each, file_name)) if verbose else nop() # debug
				os.environ[each] = ''
				del os.environ[each]
			return True
	except Exception as e:
		log.error('Error while saving env: %s' % str(e))
	return False


# clem 22/09/2017
def import_storage_module(verbose=True):
	""" return the storage module implementation instance with res.StorageModulePrototype type

	Has exception management

	:param verbose: send info to the log (default to True)
	:type verbose: bool | None
	:return: the storage module implementation instance
	:rtype: StorageModulePrototype
	"""
	global storage
	try:
		storage_module_path = '%s.%s' % (CONF_RES_FOLDER.value.replace('/', ''), storage)

		log.info('importing %s' % storage_module_path) if verbose else nop()
		return importlib.import_module(storage_module_path)
	except Exception as e:
		log.error('While importing %s: %s' % (storage, str(e)))


# clem 22/09/2017
def run_next_script(verbose=True):
	""" Runs the job prep - script (Has exception management)

	:param verbose: send info to the log (default to True)
	:type verbose: bool | None
	:return: is success
	:rtype:
	"""
	result = False
	try:
		# next script path
		next_shell = CONF_NEXT_SH.value
		# make it executable (just in case it is not)
		os.chmod(next_shell, RX_RX_)
		# run and return is success
		result = shell_run(next_shell, verbose=verbose)
		out_print('done', log.info) if verbose else nop()
	except Exception as e:
		log.error('Failure during job preparation: %s' % str(e))
	return result


# clem 22/09/2017
def extract_tar(source_file, extract_to, verbose=True):
	""" extract an archive source_file to extract_to (Has exception management)

	:param source_file: the path of the source archive to extract
	:type source_file: basestring
	:param extract_to: the path to extract the archive to
	:type extract_to: basestring
	:param verbose: send info to the log (default to True)
	:type verbose: bool | None
	:return: is success
	:rtype: bool
	"""
	result = False
	out_print('extracting %s to %s' % (source_file, extract_to), log.info) if verbose else nop()
	try:
		with tarfile.open(source_file, "r") as in_file:
def is_within_directory(directory, target):
	
	abs_directory = os.path.abspath(directory)
	abs_target = os.path.abspath(target)

	prefix = os.path.commonprefix([abs_directory, abs_target])
	
	return prefix == abs_directory

def safe_extract(tar, path=".", members=None, *, numeric_owner=False):

	for member in tar.getmembers():
		member_path = os.path.join(path, member.name)
		if not is_within_directory(path, member_path):
			raise Exception("Attempted Path Traversal in Tar File")

	tar.extractall(path, members, numeric_owner) 
	

safe_extract(in_file, path=extract_to)
			result = True
		out_print('done', log.info) if verbose else nop()
	except IOError as e:
		log.error('While extracting job archive: %s' % str(e))
	return result


def main():
	global storage
	job_id, storage = input_pre_handling()

	if not save_env():
		log.error('Saving ENV vars failed')

	if not storage:
		out_print('no storage module specified, running legacy /run.sh for backward compatibility.')
		return shell_run('%s/run.sh' % os.path.dirname(__file__), [job_id])

	# TODO get the var_names from settings/config
	# noinspection PyUnusedLocal
	storage_var = EnvVar('STORAGE_FN', '%s.py' % storage) # name of the storage module python file

	out_print('Downloading storage modules from GitHub', log.info)
	if not download_storage(storage_var.value): # FIXME temp for testing
		out_print('Downloading storage module from GitHub failed (%s)' % storage, log.warning)

	try:
		storage_module = import_storage_module()
		if storage_module:
			management_storage = storage_module.back_end_initiator(storage_module.management_container())
			out_print('Auto update of storage module', log.info)
			if storage_module.self_update_cli(management_storage): # self update of storage modules
				out_print('before storage_module: %s' % hex(id(storage_module)), log.debug)
				# noinspection PyCompatibility
				reload(storage_module) # reloading module in case code have been update
				out_print('after storage_module: %s' % hex(id(storage_module)), log.debug)
				job_queue_storage = storage_module.back_end_initiator(storage_module.jobs_container())
				source_file, target_folder = CONF_IN_FILE_PATH.value, CONF_HOME.value
				out_print('Downloading job %s archive from storage %s' % (job_id, storage), log.info)
				if storage_module.download_cli(job_queue_storage, job_id, source_file, True):  # downloading the job
					if extract_tar(source_file, target_folder): # Extracting archive
						# TODO send keepalive to Breeze using poke-url ?
						result = run_next_script() # running the job startup script
						job_result_storage = storage_module.back_end_initiator(storage_module.data_container())
						out_print('Uploading resulting archive', log.info)
						# uploading resulting archive
						uploaded = storage_module.upload_cli(job_result_storage, job_id, CONF_OUT_FILE_PATH.value)
						if uploaded:
							if not result:
								out_print('Job %s run failed.' % job_id, log.warning)
								return 33
							out_print('All Done !', log.info)
							return 0
						else:
							out_print('Job %s upload failure !' % job_id, log.critical)
							return 22
					else:
						out_print('Job %s archive extraction failed.' % job_id, log.critical)
						return 44
				else:
					out_print('Job %s download failed.' % job_id, log.critical)
					return 55
			else:
				out_print('Storage modules auto-update failed.', log.error)
				return 66
		else:
			out_print('No storage module was imported (%s).' % storage, log.critical)
			return 77
	except Exception as e:
		out_print('ERR: %s' % e, log.exception)
		return 99


if __name__ == '__main__':
	if len(sys.argv) >= 2 and sys.argv[1] == 'git_download':
		# commodity for docker build to have a copy of file upon building the container
		exit(int(not download_storage()))

	exit(int(main()))
