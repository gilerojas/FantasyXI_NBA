"""
Setup configuration for FantasyXI NBA.
"""

from setuptools import setup, find_packages

setup(
    name="fantasyxi",
    version="0.1.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "espn-api",
        "nba-api",
        "pandas",
        "openpyxl",
        "thefuzz[speedup]",
        "python-dateutil",
    ],
    python_requires=">=3.9",
)