#!/bin/env bash

echo "Clone Pylarion Library"

if [[ -d pylarion ]]
then
    echo "Removing already existing dir $(pwd)/pylarion"
    rm -rf pylarion
fi

git clone https://code.engineering.redhat.com/gerrit/pylarion
if [[ ${?} -ne 0 ]]
then
    echo "Failed to clone 'pylarion' lib"
    exit 1
fi

# Config file is obtained separately
if [[ ! -f .pylarion ]]
then
    echo ".pylarion config file not found"
    exit 1
fi

# Do not copy .pylarion to user's $HOME unless requested
if [[ -n ${1} ]]
then
    echo "Copy Pylarion config to home directory"
    if [[ -e ~/.pylarion ]]
    then
        TMP_ID=${RANDOM}
        echo "Rename ~/.pylarion to ~/.pylarion.orig.${TMP_ID}"
        mv -f ~/.pylarion ~/.pylarion.orig.${TMP_ID}
    fi

    cp .pylarion ~/

else
    echo "Using $(pwd)/.pylarion"
fi

echo "Setup Pylarion library"
cd pylarion && python setup.py install && \
    pip install --upgrade pip && \
    pip install -r requirements.txt && cd ../
