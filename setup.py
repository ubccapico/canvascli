from setuptools import setup, find_packages
from canvascli import __version__


setup(
    name='canvascli',
    version=__version__,

    description=' A CLI to reformat and review Canvas grades',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',

    author='Joel Ostblom',
    author_email='joelostblom@protonmail.com',
    url='https://github.com/joelostblom/canvascli',

    python_requires='>=3.6',
    py_modules=['canvascli'],
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'altair',
        'canvasapi',
        'click>=8.0.0',
        'pandas',
        'tabulate',
        'dataclassy'
    ],
    entry_points={
        'console_scripts': [
            'canvascli = canvascli.main:cli',
        ],
    },
)
