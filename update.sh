#!/bin/bash


echo "Updating RSimulator..."
python3 setup.py sdist bdist_wheel
python3 -m pip install ./dist/rsimulator-1.0.0-py3-none-any.whl --force-reinstall
echo "Removing build folders..."
rm -rf build dist *.egg-info
echo "RSimulator updated successfully!"
