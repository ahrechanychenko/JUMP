#!/bin/bash

echo "Clone Pylarion library"
rm -rf pylarion
git clone https://code.engineering.redhat.com/gerrit/pylarion

echo "Copy Pylarion config to home directory"
rm -rf ~/.pylarion
#cp rhos-qe-core-installer/tripleo/polarion/.pylarion ~/
cp JUMP/.pylarion ~/


echo "Setup Pylarion library"
cd pylarion && python setup.py install  && cd ../

echo "Setup Tempest"
# get latest tempest repo
rm -rf /tmp/tempest && git clone http://git.openstack.org/openstack/tempest /tmp/tempest

# install tempest and init configuration
pip install tempest/
