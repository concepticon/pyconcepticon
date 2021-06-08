from setuptools import setup, find_packages


setup(
    name='pyconcepticon',
    version='2.8.0',
    description='programmatic access to concepticon-data',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    license='Apache 2.0',
    classifiers=[
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
    ],
    author='',
    author_email='forkel@shh.mpg.de',
    url='https://github.com/concepticon/pyconcepticon',
    keywords='data linguistics',
    packages=find_packages(where='src'),
    package_dir={'': 'src'},
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        'attrs>=18.1.0',
        'pybtex>=0.22.2',
        'csvw>=1.4.5',
        'clldutils>=3.4',
        'cldfcatalog>=1.3',
        'cdstarcat',
        'nameparser',
        'termcolor',
        'tabulate',
    ],
    extras_require={
        'dev': [
            'tox',
            'flake8',
            'wheel',
            'twine',
        ],
        'test': [
            'pytest>=5.4',
            'pytest-mock',
            'pytest-cov',
            'coverage>=4.2',
        ],
    },
    entry_points={
        'console_scripts': [
            'concepticon=pyconcepticon.__main__:main',
        ]
    },
)
