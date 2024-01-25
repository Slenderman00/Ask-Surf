from setuptools import setup, find_packages

setup(
    name='AskSurf',
    version='0.6.3',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'requests',
        'tqdm',
        'halo',
        'toml',
        'diffusers',
        'torch',
    ],
    entry_points='''
        [console_scripts]
        surf=AskSurf.cli:main
    ''',
)