#!/usr/bin/env python
# -*- coding: utf-8 -*-

from pathlib import Path
from setuptools import setup, find_packages

requirements = Path("requirements.txt").read_text().strip().splitlines()

long_description = Path("README.md").read_text()

pkg = "mpv_history_daemon"
setup(
    author="Sean Breckenridge",
    author_email="seanbrecke@gmail.com",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: End Users/Desktop",
        "Natural Language :: English",
        "Programming Language :: Python :: 3",
    ],
    description="Daemon which connects to active mpv instances, saving a history of what I watch/listen to",
    long_description=long_description,
    long_description_content_type="text/markdown",
    install_requires=requirements,
    name=pkg,
    packages=find_packages(include=[pkg]),
    package_data={pkg: ["py.typed"]},
    entry_points={
        "console_scripts": ["mpv-history-daemon = mpv_history_daemon.__main__:cli"]
    },
    license="http://www.apache.org/licenses/LICENSE-2.0",
    scripts=["bin/mpv_history_daemon_restart"],
    url="https://github.com/seanbreckenridge/mpv-history-daemon",
    version="0.1.2",
)
