echo "Setup Tempest"
# get latest tempest repo
rm -rf /tmp/tempest && git clone http://git.openstack.org/openstack/tempest /tmp/tempest

# install tempest and init configuration
pip install tempest/
