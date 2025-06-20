from setuptools import setup, find_packages

setup(
    name='rsimulator',
    version='1.0.0',
    packages=find_packages(),
    include_package_data=True,
    package_data={
        "rsimulator": ["network/interface/zmq/*.yaml"]
    },
    install_requires=[],
    extras_require={
        'all': ['pyyaml', 'zmq', 'transitions']
    },
    author='Riccardo Griffo',
    author_email='riccardogriffo1995@gmail.com',
    description='RGriffo utilities for general purposes',
    classifiers=[
        'Programming Language :: Python :: 3',
        'Operating System :: OS Independent',
    ],
)
