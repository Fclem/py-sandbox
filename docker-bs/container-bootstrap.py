#!/usr/bin/python
from __future__ import print_function
from github import Github
from plumbum import local
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


# clem 30/08/2017 form line 203 @ https://goo.gl/Wquh6Z clem 08/04/2016 + 10/10/2016
def this_function_caller_name(delta=0):
	""" Return the name of the calling function's caller

	:param delta: change the depth of the call stack inspection
	:type delta: int

	:rtype: str
	"""
	import sys
	return sys._getframe(2 + delta).f_code.co_name if hasattr(sys, "_getframe") else ''


# TODO throw an error if key is invalid, otherwise azure keeps on returning "resource not found" error
# clem 22/09/2016 duplicated from utilities/__init__
def get_key_bis(name=''):
	if name.endswith('_secret'):
		name = name[:-7]
	if name.startswith('.'):
		name = name[1:]
	try:
		full_path = '%s/.%s_secret' % (__dir_path__, name)
		print('accessing key at %s from %s' % (full_path, this_function_caller_name()))
		with open(full_path) as f:
			return str(f.read())[:-1]
	except IOError:
		log.warning('could not read key %s' % name)
	return ''


# TODO all these from config/ENV
GIT_HUB_COMMIT = '9cd13cd4e23c5fcc2cbc044b1bbda2b26c5e6f63'
GIT_HUB_USERNAME = 'Fclem'
GIT_HUB_REPO = 'isbio2'
GIT_HUB_TOKEN = get_key_bis('git_token')
GIT_HUB_FOLDER_PATH = 'isbio/storage/'


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
		log.info("export %s='%s'" % self.all)
		os.environ[self.name] = self._value
		self._exported = True
		
	@property
	def value(self):
		return self._value


# TODO all these from config/ENV
CONF_RES_FOLDER = EnvVar('RES_FOLDER', '/res')
CONF_IN_FILE = EnvVar('IN_FILE', "in.tar.xz")                              # file name to use for the input/job set archive
CONF_OUT_FILE = EnvVar('OUT_FILE', "out.tar.xz")                           # file name to use fot the output/result archive
CONF_OUT_FILE_PATH = EnvVar('OUT_FILE_PATH', "%s/" + CONF_OUT_FILE.value)  # path to the final archive to be created
CONF_NEXT_SH = EnvVar('NEXT_SH', "%s/run.sh")                              # path of the next file to run
###
RX_RX_ = 0o550
RW_RW_ = 0o660


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
	
	@property
	def user(self):
		if not self._user:
			self._user = self._git_hub_client.get_user(self._git_user_name)
		return self._user
	
	@property
	def repo(self):
		if not self._repo:
			log.debug('getting %s/%s' % (self._git_user_name, self._git_repo_name))
			self._repo = self.user.get_repo(self._git_repo_name)
		return self._repo
	
	def download(self, content_file, save_to=None, do_fail=False):
		""" Download and saves the specified content file
		
		:param content_file: the GithubObject to be downloaded as from self.repo.get_dir_contents or
		self.repo.get_contents
		:type content_file: github.ContentFile.ContentFile
		:param save_to: an optional path to save the file to. If None use the name from github and stores it in the
		local folder
		:type save_to: str
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
			log_to('%s on %s %s' % (e.strerror, content_file.path, save_to ))
			if e.errno == 13: # Permission denied
				os.chmod(save_to, RW_RW_)
			return self.download(content_file, save_to, True)
		log.debug('%s % 8s\t%s' % (content_file.sha, human_readable_byte_size(content_file.size), content_file.name))
		if is_executable:
			os.chmod(save_to, RX_RX_)
		return True


def input_pre_handling():
	""" Parse arguments from command line

	:return: (job_id, storage)
	:rtype: tuple[basestring, basestring]
	"""
	assert len(sys.argv) >= 2
	
	job_id = str(sys.argv[1])
	storage = '' if len(sys.argv) <= 2 else str(sys.argv[2])
	
	return job_id, storage


def get_var(var_name, *more_vars):
	a_list = list()
	var_value = os.environ.get(var_name, '')
	for each in more_vars:
		a_list.append(os.environ.get(each, ''))
	if a_list:
		a_list = tuple([var_value] + a_list)
	else:
		a_list = (var_value)
	# print(a_list)
	return a_list

# TODO replace theses vars by generics from config
# export('AZURE_STORAGE_ACCOUNT', "breezedata")                 # Azure blob storage account name
# export('STORAGE_FN', "blob_storage_module.py")    # name of the blob-storage interface module python file (for
# azure-storage)
# export('AZURE_KEY_FN', ".azure_pwd_%s_secret" % get_var('AZURE_STORAGE_ACCOUNT'))    # file in which to save the
#  azure storage secret
# export('AZURE_PY', "%s/%s" % get_var('RES_FOLDER', 'AZURE_STORAGE_FN'))    # full path
# of the  azure-storage python interface
# RELEVANT_COMMIT = '02646ed76e75a141d9ec671c68eab1a5439f48bb'
# print(os.environ)


def download_storage(storage):
	if not os.path.exists(storage):
		git_hub = GitHubDownloader(GIT_HUB_USERNAME, GIT_HUB_TOKEN, GIT_HUB_REPO)
		storage_dir = git_hub.repo.get_dir_contents(GIT_HUB_FOLDER_PATH, ref=GIT_HUB_COMMIT)
		
		log.info('Downloading storage modules from GitHub...')
		for each in storage_dir:
			git_hub.download(each)
		log.debug('done, %s files downloaded' % len(storage_dir))
		

def main():
	job_id, storage = input_pre_handling()
	log.debug('job_id: %s\nstorage: %s' % (job_id, storage))
	
	if not storage:
		print('no storage module specified, running run.sh for backward compatibility.')
		base_path = os.path.dirname(__file__)
		print('$ %s/run.sh' % base_path)
		print(local['%s/run.sh' % base_path](job_id))
		exit()
	
	# TODO get the var_names from settings/config
	EnvVar('JOB_ID', job_id)                # Job id, i.e. job file to download from storage
	storage_var = EnvVar('STORAGE_FN', '%s.py' % storage) # name of the storage module python file
	os.chdir(get_var('RES_FOLDER'))
	
	download_storage(storage_var.value)
	
	log.debug('getting job %s from %s backend' % (job_id, storage_var.value))
	# ./$AZURE_STORAGE_FN load $JOB_ID
	# FIXME dummy
	# EnvVar('AZURE_KEY', '')
	next_run = local['./%s' % storage_var.value]
	log.debug('$ %s load %s' % (next_run, job_id))
	print(next_run('load', job_id))
	

if __name__ == '__main__':
	main()
