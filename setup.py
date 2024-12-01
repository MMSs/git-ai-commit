from setuptools import setup, find_packages

setup(
    name="git-ai-commit",
    version="0.1.0",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'click',
        'openai',
        'pyyaml',
        'gitpython',
        'rich',
    ],
    entry_points={
        'console_scripts': [
            'gcommit=src.cli:main',
        ],
    },
)