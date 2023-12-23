from setuptools import setup, find_packages

setup(
    name='AskSurf',
    version='0.5.5',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'requests',
        'tqdm',
        'crayons',
        'halo',
    ],
    entry_points='''
        [console_scripts]
        surf=AskSurf.cli:main
    ''',
)