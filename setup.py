from setuptools import setup, find_packages


setup(
    name='canvascli',
    version='0.2.0',
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
