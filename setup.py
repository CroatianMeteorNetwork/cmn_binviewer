import sys
from cx_Freeze import setup, Executable

# Dependencies are automatically detected, but it might need fine tuning.
includefiles = ['gifsicle.exe', 'noimage.bin', 'CMN_binViewer_readme.txt', 'config.ini', 'icon.ico', 'CMN_binViewer_manual.pdf', 'CHANGELOG.txt']

exclude_libs = ['_ssl', 'pyreadline', 'doctest','optparse', 'pickle', 'matplotlib', "BaseHTTPServer", "SocketServer", "dateutil", "email", "httplib", "itertools", "mpl_toolkits", "numpy.f2py", "pydoc_data", "urllib", "urllib2", "xml", "zipfile", "zipimport", "scipy.sparse.linalg.eigen.arpack", "scipy.sparse._sparsetools"]

build_exe_options = {"packages": ["scipy.special._ufuncs_cxx"], "optimize": 2, 'include_files':includefiles, "excludes":exclude_libs, "include_msvcr":True, "icon": "icon.ico"}

# GUI applications require a different base on Windows (the default is for a
# console application).
base = None
if sys.platform == "win32":
    base = "Win32GUI"

setup(  name = "CMN_binViewer",
        version = "1.0",
        options = {"build_exe": build_exe_options},
        executables = [Executable("CMN_binViewer.py", base=base)])