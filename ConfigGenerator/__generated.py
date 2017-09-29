from utilz import magic_const, MagicAutoConstEnum
import os


self_path = os.path.realpath(__file__)


# Static object describing available Environments
# noinspection PyMethodParameters,PyPep8Naming
class ConfigPrototypeList(MagicAutoConstEnum):
	@magic_const
	def void(): pass
