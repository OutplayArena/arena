from importlib.metadata import version, PackageNotFoundError

try:
    __version__: str = version("arena")
except PackageNotFoundError:
    __version__ = "0.0.0+dev"

ARENA_VERSION: str = __version__
