from __future__ import print_function
import __generated as generated
# from __generated import *
import os

__path__ = os.path.realpath(__file__)
__dir_path__ = os.path.dirname(__path__)
__file_name__ = os.path.basename(__file__)


def nop():
	pass


class FilterableList(list):
	def filt_ext(self, filter_list=list()):
		return FilterableList(filter(lambda w: not filter_list or ('.' in w and w.split('.')[-1] in filter_list), self))
	
	def filter_out(self, filter_list=list()):
		return FilterableList(filter(lambda w: not filter_list or w not in filter_list, self))
	
	def __repr__(self):
		return '*%s' % str(super(FilterableList, self).__repr__())
	
	def __str__(self):
		return str(self.__repr__())
	

class WalkObject(object):
	path = ''
	dir_list = list
	file_list = list
	
	def __init__(self, walk_object):
		assert isinstance(walk_object, tuple) and len(walk_object) == 3
		self.path = walk_object[0]
		self.dir_list = walk_object[1]
		self.file_list = FilterableList(walk_object[2])
		
	@property
	def data(self):
		return self.path, self.dir_list, self.file_list
	
	def __str__(self):
		return '<WO:%s>' % str(self.data)
	

def walker(a_path, filter_ext=list(), filter_out=list(), recursive=False, verbose=False):
	if verbose:
		sup = '' if not filter_ext else ' with ext filter %s' % str(filter_ext)
		sup3 = '' if not filter_out else ' with filter_out %s' % str(filter_out)
		sup2 = '' if not recursive else ' with recursion'
		print('walking dir %s%s%s%s' % (a_path, sup, sup3, sup2))
	walking = [i for i in os.walk(a_path)]
	result = list()
	walk_list = walking if recursive else filter(lambda w: w[0] == a_path, walking)
	print('walk_list: %s' % walk_list) if verbose else nop()
	for walk_item in [WalkObject(x) for x in walk_list]:
		print('walk_item: %s' % walk_item) if verbose else nop()
		result += walk_item.file_list.filt_ext(filter_ext).filter_out(filter_out)
		# for file_name in walk_item.file_list.filt_ext(filter_ext):
		# 	result.append(file_name)
		# 	print('file_name: %s' % file_name) if verbose else nop()
	return result


class ConfigGenerator(object):
	file_list = list()
	
	def __init__(self, a_path=__dir_path__, filter_ext=list(), filter_out=list()):
		filter_ext = filter_ext or ['py']
		filter_out = filter_out or ['__init__.py']
		self.file_list = walker(a_path, filter_ext, filter_out)

	def __str__(self):
		return str(self.file_list)
	
	def gen(self):
		with open(generated.self_path, 'w') as a_file:
			for each in self.file_list:
				sup = """from utilz import magic_const, MagicAutoConstEnum
	
				"""
			a_file.write("""

	@magic_const
	def AzureCloud(): pass



# Static object describing available Environments
# noinspection PyMethodParameters,PyPep8Naming
class ConfigPrototypeList(MagicAutoConstEnum):
	%s
			""" % sup)
