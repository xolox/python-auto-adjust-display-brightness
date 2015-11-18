#!/usr/bin/env python

# Setup script for the `auto-adjust-display-brightness' package.
#
# Author: Peter Odding <peter@peterodding.com>
# Last Change: November 18, 2015
# URL: https://github.com/xolox/python-auto-adjust-display-brightness

# Standard library modules.
import codecs
import os
import re

# De-facto standard solution for Python packaging.
from setuptools import setup, find_packages

# Find the directory where the source distribution was unpacked.
source_directory = os.path.dirname(os.path.abspath(__file__))

# Find the current version.
module = os.path.join(source_directory, 'aadb', '__init__.py')
for line in open(module, 'r'):
    match = re.match(r'^__version__\s*=\s*["\']([^"\']+)["\']$', line)
    if match:
        version_string = match.group(1)
        break
else:
    raise Exception("Failed to extract version from %s!" % module)

# Fill in the long description (for the benefit of PyPI)
# with the contents of README.rst (rendered by GitHub).
readme_file = os.path.join(source_directory, 'README.rst')
with codecs.open(readme_file, 'r', 'utf-8') as handle:
    readme_text = handle.read()

setup(
    name='auto-adjust-display-brightness',
    version=version_string,
    description="Automatically adjust Linux display brightness",
    long_description=readme_text,
    url='https://github.com/xolox/python-auto-adjust-display-brightness',
    author='Peter Odding',
    author_email='peter@peterodding.com',
    packages=find_packages(),
    install_requires=[
        'coloredlogs >= 0.8',
        'executor >= 1.7.1',
        'humanfriendly >= 1.42',
        'pyephem >= 3.7.5.2',
    ],
    entry_points=dict(console_scripts=[
        'auto-adjust-display-brightness = aadb:main',
    ]),
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Environment :: X11 Applications',
        'Intended Audience :: Developers',
        'Intended Audience :: Information Technology',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: MIT License',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Topic :: Desktop Environment',
        'Topic :: System :: Systems Administration',
        'Topic :: Utilities',
    ])
