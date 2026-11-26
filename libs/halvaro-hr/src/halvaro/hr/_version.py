# Version of halvaro-hr. The released version comes from the Git tag halvaro-hr/v<major>.<minor>.<patch>: the build (setuptools-scm, see pyproject.toml) writes _version_scm.py next to
# this file (git-ignored, so the tree stays clean and the wheel is consistent) and it ends up in the wheel. A checkout that was not built has no _version_scm.py and uses the committed
# fallback below, so the tests and the code index see a stable value. Nobody edits a version number by hand for a release: tag it.
try:
    from ._version_scm import __version__
except ImportError:  # not built from a tag
    __version__ = "1.0.0"
