from setuptools import setup, find_packages

setup(
    name="AskSurf",
    version="3.0.0",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "llama-cpp-python",
        "huggingface_hub",
        "fastapi",
        "uvicorn",
        "httpx",
        "toml",
        "halo",
        "pygments",
        "climage",
        "python-magic",
        "pypdf2",
        "docxpy",
        "requests",
    ],
    entry_points="""
        [console_scripts]
        surf=AskSurf.cli:main
    """,
)
