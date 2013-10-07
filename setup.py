#!/usr/bin/env python

from setuptools import setup

fp = open("README.txt", "r")
try:
    readme = fp.read()
finally:
    fp.close()

setup(name='pyvendapin',
      version='0.1',
      description='support the Vendapin serial protocol in Python',
      long_description=readme,
      license='GPLv3+',
      author='Hans-Christoph Steiner',
      author_email='hans@eds.org',
      url='https://github.com/eighthave/pyvendapin',
      py_modules = ['vendapin'],
      install_requires = ['pyserial'],
      classifiers = [
          'Intended Audience :: Developers',
          'License :: OSI Approved :: GNU General Public License (GPL)',
          'Programming Language :: Python :: 2',
          'Topic :: Software Development :: Libraries :: Python Modules',
          'Topic :: Office/Business :: Financial :: Point-Of-Sale',
          'Topic :: System :: Hardware'],
)

