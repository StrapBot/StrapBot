#!/bin/bash

PIP=$(which -a "pip$1" | head -n 1)
PACKAGES="${@:2}"

exec $PIP install -U $PACKAGES