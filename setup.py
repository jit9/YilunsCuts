from setuptools import setup

setup(
    name='cutslib',
    version='0.1.0',
    packages=['cutslib'],
    scripts=['bin/promote_version',
             'bin/cutspipe',
             'bin/run_cuts',
             'bin/submit_cuts',
             'bin/submit_cuts_tiger'],
    install_requires=['dotmap',
                      'configparser',
                      'pycook',
                      'future', # from here onwards will be moby2 deps
                      'numpy',
                      'matplotlib',
                      'scipy',
                      'astropy',
                      'ephem',
                      'pytz',
                      'h5py',
                      'profilehooks',
                      'fitsio',
                      'pyfits',],
    entry_points={'console_scripts': [
        'cuts=cutslib.cli:main'
    ]}
)
