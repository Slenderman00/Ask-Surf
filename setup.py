from setuptools import setup, find_packages

setup(
    name='AskSurf',
    version='0.1',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'requests',
        'tqdm',
    ],
    entry_points='''
        [console_scripts]
        surf=src.cli:main
    ''',
)