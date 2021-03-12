#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup, find_packages

requirements = [
    "click",
    "python-mpv-jsonipc",
    "logzero",
]

setup(
    author="Sean Breckenridge",
    author_email="seanbrecke@gmail.com",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: End Users/Desktop",
        "Natural Language :: English",
        "Programming Language :: Python :: 3",
    ],
    install_requires=requirements,
    license="MIT",
    name="mpv_history_daemon",
    packages=find_packages(include=["mpv_history_daemon"]),
    entry_points={
        "console_scripts": ["mpv-history-daemon = mpv_history_daemon.__main__:main"]
    },
    scripts=["bin/mpv_history_daemon_exec"],
    url="https://github.com/seanbreckenridge/mpv-history-daemon",
    version="0.1.0",
)
