import os
import six
import types


def nop():
	pass


class FilterableList(list):
	def filter_func(self, filt_func):
		assert callable(filt_func)
		return FilterableList(filter(filt_func, self))
	
	def __repr__(self):
		return '*%s' % six.text_type(super(FilterableList, self).__repr__())
	
	def __str__(self):
		return six.text_type(self.__repr__())


class FSObject(object):
	path = six.text_type()
	name = six.text_type()
	dir_name = six.text_type()
	is_file = False
	is_dir = False
	
	def __init__(self, path, *args, **kwargs):
		self.path = path if path[-1] != os.path.sep else path[:-1] # removes eventual trailing /
		self.name = os.path.basename(path)
		self.dir_name = os.path.dirname(path)
		
	def __repr__(self):
		char = u'F' if self.is_file else u'D'
		return six.text_type('%s<%s>' % (char, self.name))
	
	def __str__(self):
		return six.text_type(self.path)


class FileObject(FSObject):
	is_file = True
	is_dir = False
	
	def get_file_handle(self, mode='r', buffering=None):
		return open(self.path, mode, buffering) if buffering is not None else open(self.path, mode)


class DirObject(FSObject):
	is_file = False
	is_dir = True
	pass
		

class WalkObject(object):
	path = ''
	dir_list = FilterableList
	file_list = FilterableList

	def __init__(self, walk_object):
		"""
		
		:param walk_object: (path, dir_list, file_list)
		:type walk_object: (str, list, list)
		"""
		assert isinstance(walk_object, tuple) and len(walk_object) == 3
		self.path = walk_object[0]
		# self.dir_list = FilterableList([self.new_path(x) for x in walk_object[1]])
		self.dir_list = FilterableList(walk_object[1])
		self.file_list = FilterableList(walk_object[2])
	
	# def convert(self, a_list):
	# 	return apply(lambda x: self.new_path(x), a_list)
	
	def new_path(self, a_name):
		return '%s%s%s' % (self.path, os.path.sep, a_name)
	
	def filter_files(self, filter_func):
		self.file_list = self.file_list.filter_func(filter_func)
	
	def filter_directories(self, filter_func):
		self.dir_list = self.dir_list.filter_func(filter_func)
	
	@property
	def data(self):
		return self.path, self.dir_list, self.file_list
	
	def __str__(self):
		return '<WO:%s>' % six.text_type(self.data)


class ConfigGenerator(object):
	path = six.text_type()
	verbose = False
	_walker_list = list()  # type: list[WalkObject, ]
	_filter_ext = list()  # type: list[six.text_type, ]
	_exclude = list()  # type: list[six.text_type, ]
	recursive = True  # type: bool
	
	def __init__(self, a_path, exclude=list(), recursive=True, verbose=False):
		self.verbose = verbose
		self.path = a_path if a_path[-1] != os.path.sep else a_path[:-1]  # removes eventual trailing /
		self._exclude = exclude
		self.recursive = recursive
	
	def __str__(self):
		return six.text_type(self.walker_list)
	
	@property
	def walker_list(self):
		if not self._walker_list:
			self._walker_list = self._walker()
		return self._walker_list
	
	def _walker(self):
		"""

		:return:
		:rtype: list[WalkObject]
		"""
		walking = [i for i in os.walk(self.path)]
		walk_list = walking if self.recursive else filter(lambda w: w[0] == self.path, walking)
		return [WalkObject(x) for x in walk_list]
	
	# return result
	
	def gen(self):
		for each1 in self.walker_list:
			print('%s' % each1)
			# for each2 in each1.dir_list:
				#  ConfigGenerator(each2).gen()
				#  print('\t%s' % each2)


ConfigGenerator('/home/clem/_tmp/').gen()
exit(0)
