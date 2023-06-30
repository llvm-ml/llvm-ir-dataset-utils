#!/usr/bin/env bash

set -ex

# Python deps
pip3 install pipenv
pipenv lock
pipenv sync --system