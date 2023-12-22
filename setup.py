from setuptools import setup, find_packages

setup(
    name='AskSurf',
    version='0.2',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'requests',
        'tqdm',
    ],
    entry_points='''
        [console_scripts]
        surf=AskSurf.cli:main
    ''',
)