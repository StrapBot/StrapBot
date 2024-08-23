#!/bin/bash

CLIENT=${1:-1}
SERVER=${2:-0}

PIP=$(which -a "pip$3" | head -n 1)
PACKAGES="${@:2}"

if [ $CLIENT -ne 0 ] && [ $CLIENT -ne 1 ]; then
    echo "Invalid argument for CLIENT: $CLIENT"
    exit 1
fi

if [ $SERVER -ne 0 ] && [ $SERVER -ne 1 ]; then
    echo "Invalid argument for SERVER: $SERVER"
    exit 1
fi

if [ $CLIENT -eq 1 ]; then
    $PIP install -Ur requirements.txt
fi

if [ $SERVER -eq 1 ]; then
    $PIP install -Ur requirements.server.txt
fi