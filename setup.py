'''
Flask-Session-Management
-----------
Flask-Session-Management provides session management for Flask.
'''

import os
import sys

from setuptools import setup

module_path = os.path.join(os.path.dirname(__file__), 'flask_session_management.py')
version_line = [line for line in open(module_path)
                if line.startswith('__version_info__')][0]

__version__ = '.'.join(eval(version_line.split('__version_info__ = ')[-1]))

setup(name='Flask-Session-Management',
      version=__version__,
      url='https://github.com/nampnq/flask-session-management',
      license='MIT',
      author='Nam Pham',
      author_email='nampnq@gmail.com',
      description='Session management for Flask',
      long_description=__doc__,
      py_modules=['flask_session_management'],
      zip_safe=False,
      platforms='any',
      install_requires=['flask', 'redis'])
