from setuptools import setup, find_packages

setup(
    name='AskSurf',
    version='0.6.4',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'requests',
        'tqdm',
        'halo',
        'toml',
        'transformers',
        'torch',
        'diffusers',
        'httpx',
        'llama-cpp-python==0.2.23',
        'accelerate',
        'climage',
        'protobuf',
        'sentencepiece'
    ],
    entry_points='''
        [console_scripts]
        surf=AskSurf.cli:main
    ''',
)
