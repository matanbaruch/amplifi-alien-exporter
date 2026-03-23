#!/usr/bin/env python3
"""
Setup script for amplifi-alien-exporter.
For modern builds, see pyproject.toml.
"""

from setuptools import setup

# Read the version from amplifi_exporter.py
with open("amplifi_exporter.py") as f:
    for line in f:
        if line.startswith("VERSION"):
            version = line.split("=")[1].strip().strip('"')
            break

setup(
    version=version,
)
