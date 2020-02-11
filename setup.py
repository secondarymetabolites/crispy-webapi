import os
from setuptools import setup

def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

long_description = read('README.md')

version_py = os.path.join('crispy_webapi', 'version.py')
version = read(version_py).strip().split('=')[-1].replace("'", "").strip()

install_requires = [
    "crispy-models",
    "Flask",
    "Jinja2",
    "MarkupSafe",
    "Werkzeug",
    "itsdangerous",
    "redis",
    "feedparser",
    "gunicorn",
]

tests_require = [
    "mockredispy-kblin",
    "pytest",
    "pytest-cov",
    "pytest-flask",
]


setup(name='crispy-webapi',
    version=version,
    install_requires=install_requires,
    tests_require=tests_require,
    author='SecondaryMetabolites.org packaging team',
    author_email='kblin@biosustain.dtu.dk',
    description='A REST-like web API for CRISPy',
    long_description=long_description,
    long_description_content_type='text/markdown',
    packages=['crispy_webapi'],
    url='https://github.com/secondarymetabolites/crispy-service/',
    license='GNU Affero General Public License',
    classifiers=[
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Development Status :: 4 - Beta',
        'Intended Audience :: Science/Research',
        'Topic :: Scientific/Engineering :: Bio-Informatics',
        'License :: OSI Approved :: GNU Affero General Public License v3 or later (AGPLv3+)',
        'Operating System :: OS Independent',
        ],
    extras_require={
        'testing': tests_require,
        },
)
