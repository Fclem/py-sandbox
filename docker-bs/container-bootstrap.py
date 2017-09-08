#!/usr/bin/python
from __future__ import print_function
from github import Github
from plumbum import local
import sys
import os


def export(var_name, value):
	os.environ[var_name] = value


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
	print(a_list)
	return a_list


def main(job_id, storage):
	# TODO get the var_names from settings
	export('RES_FOLDER', "/res")
	export('AZURE_STORAGE_ACCOUNT', "breezedata")    # Azure blob storage account name
	export('IN_FILE', "in.tar.xz")                    # file name to use for the input/job set archive
	export('OUT_FILE', "out.tar.xz")                # file name to use fot the output/result archive
	home = get_var('HOME')
	export('OUT_FILE_PATH', "%s/%s" % (home, get_var('OUT_FILE')))        # path to the final archive to be created
	export('NEXT_SH', "%s/run.sh" % home)                # path of the next file to run
	export('JOB_ID', job_id)                            # Job id designate the file to be downloaded from Azure-storage
	export('AZURE_STORAGE_FN', storage)    # name of the azure-storage python file
	# export('STORAGE_FN', "blob_storage_module.py")    # name of the blob-storage interface module python file (for azure-storage)
	export('AZURE_KEY_FN', ".azure_pwd_%s_secret" % get_var('AZURE_STORAGE_ACCOUNT'))    # file in which to save the azure storage secret
	export('AZURE_PY', "%s/%s" % get_var('RES_FOLDER', 'AZURE_STORAGE_FN'))    # full path
	# of the  azure-storage python interface
	# RELEVANT_COMMIT = '02646ed76e75a141d9ec671c68eab1a5439f48bb'
	# print(os.environ)


if __name__ == '__main__':
	job_id, storage = input_pre_handling()
	print('job_id: %s\nstorage: %s' % (job_id, storage))
	
	if not storage:
		print('no storage module specified, running run.sh for backward compatibility.')
		base_path = os.path.dirname(__file__)
		print('$ %s/run.sh' % base_path)
		print(local['%s/run.sh' % base_path]())
		exit()
	
	main(job_id, storage)
