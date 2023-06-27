#!/usr/bin/env bash

set -ex

pip3 install pipenv
pipenv lock
pipenv sync --system