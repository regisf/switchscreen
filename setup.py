#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import shutil
import os

from distutils.core import setup

import switchscreen

shutil.copyfile("switchscreen.py", "switchscreen")

setup(
    name = "switchscreen",
    version = switchscreen.__version__,
    description = "",
    author = u"Régis FLORET",
    author_mail = "regisfloret@gmail.com",
    url = "http://code.google.com/p/switchscreen/",
    scripts = [
        'switchscreen',
    ]
)

os.remove("switchscreen")