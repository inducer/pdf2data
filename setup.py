#!/usr/bin/env python3
# -*- coding: latin1 -*-

from setuptools import setup, find_packages

setup(name="pdf2data",
      version="2019.1",
      description=(
          "Tools for extracting tabular data from PDFs, using pdfminer"),
      long_description=open("README.rst", "r").read(),
      classifiers=[
          'Development Status :: 4 - Beta',
          'Intended Audience :: Developers',
          'Intended Audience :: Other Audience',
          'Intended Audience :: Science/Research',
          'License :: OSI Approved :: MIT License',
          'Natural Language :: English',
          'Programming Language :: Python :: 3',
          'Topic :: Utilities',
          ],

      install_requires=["pdfminer.six"],

      scripts=["read-uiuc-fin-statement"],

      author="Andreas Kloeckner",
      url="https://github.com/inducer/pdf2data",
      author_email="inform@tiker.net",
      license="MIT",
      packages=find_packages())
