#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import distutils
import subprocess
from os.path import dirname, join

from setuptools import setup, find_packages


def read(*args):
    return open(join(dirname(__file__), *args)).read()


class ToxTestCommand(distutils.cmd.Command):
    """Distutils command to run tests via tox with 'python setup.py test'.

    Please note that in our standard configuration tox uses the dependencies in
    `requirements/dev.txt`, the list of dependencies in `tests_require` in
    `setup.py` is ignored!

    See https://docs.python.org/3/distutils/apiref.html#creating-a-new-distutils-command
    for more documentation on custom distutils commands.
    """
    description = "Run tests via 'tox'."
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        self.announce("Running tests with 'tox'...", level=distutils.log.INFO)
        return subprocess.call(['tox'])


exec(read('pganonymize', 'version.py'))

install_requires = [
    'psycopg2-binary',
    'isort',
    'pgcopy',
    'Sphinx',
    'tqdm',
    'Faker',
    'cachetools',
    'pyyaml',
    'parmap'
]

tests_require = [
    'coverage',
    'flake8',
    'pydocstyle',
    'pylint',
    'pytest-pep8',
    'pytest-cov',
    'pytest',
]

setup(
    name='pganonymize',
    version=__version__,  # noqa
    description='Commandline tool to anonymize PostgreSQL databases',
    long_description=read('README.rst'),
    author='Henning Kage',
    author_email='henning.kage@rheinwerk-verlag.de',
    maintainer='Henning Kage',
    maintainer_email='henning.kage@rheinwerk-verlag.de',
    url='https://github.com/rheinwerk-verlag/pganonymize',
    license='MIT license',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Operating System :: POSIX',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Topic :: Database'
    ],
    packages=find_packages(include=['pganonymize*']),
    include_package_data=True,
    install_requires=install_requires,
    tests_require=tests_require,
    cmdclass={
        'test': ToxTestCommand,
    },
    entry_points={
        'console_scripts': [
            'pganonymize = pganonymize.__main__:main'
        ]
    }
)
