#!/bin/bash

source ../.venv/bin/activate
pip3 install --upgrade build twine
cd ..
echo `pwd`
python3 -m build
#python3 -m twine upload --repository testpypi --verbose dist/*
python3 -m twine upload --verbose dist/*
rm -r douglog.egg-info
rm -r dist
