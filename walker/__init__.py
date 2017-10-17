import os
import six


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


class WalkObject(object):
	path = ''
	dir_list = FilterableList
	file_list = FilterableList
	
	def __init__(self, walk_object):
		assert isinstance(walk_object, tuple) and len(walk_object) == 3
		self.path = walk_object[0]
		self.dir_list = FilterableList(walk_object[1])
		self.file_list = FilterableList(walk_object[2])
	
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
	path = str()
	verbose = False
	_walker_list = list()  # type: list[WalkObject, ]
	_filter_ext = list()  # type: list[six.text_type, ]
	_exclude = list()  # type: list[six.text_type, ]
	recursive = True  # type: bool
	
	def __init__(self, a_path, exclude=list(), recursive=True, verbose=False):
		self.verbose = verbose
		self.path = a_path
		# self._filter_ext = filter_ext
		self._exclude = exclude
		self.recursive = recursive
	
	# self.walker_list = walker(a_path, _filter_ext, _exclude, verbose=verbose)
	
	def __str__(self):
		return str(self.walker_list)
	
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
		# result = list()
		# for walk_item in [WalkObject(x) for x in walk_list]:
		# 	# walk_item.filter_files(bool)
		# 	result.append(walk_item)
		return [WalkObject(x) for x in walk_list]
	
	# return result
	
	def gen(self):
		for each1 in self.walker_list:
			print('%s' % each1)
			for each2 in each1.dir_list:
				# ConfigGenerator(each2).gen()
				print('\t%s' % each2)
	
	# for each2 in each1.file_list:
	# s	print('\t%s' % each2)


ConfigGenerator('/home/clem/_tmp/').gen()
exit(0)
