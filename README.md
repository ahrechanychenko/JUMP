Installation
===============
```
git clone https://github.com/levor23/JUMP

cd JUMP
virtualenv venv
source venv/bin/activate

.prepare_pylarion.sh

export path to RH certificate
export REQUESTS_CA_BUNDLE=/etc/pki/ca-trust/source/anchors/...RH_CERT...

```

Usage
======

To upload manual test results to Polarion:

```
python jump.py --testrun-id=$TESTRUNID  --testcases=$TEST_CASES

'$TESTRUNID' - polarion test_run_id,
'$TEST_CASES' - "test_case_id1:result(passed|failed), test_case_id2:result(passed|failed)..."
```

To upload tempest test results
```
python jump.py --testrun-id=$TESTRUNID --xml-file=$TEMPEST_XML_FILE

'$TEMPEST_XML_FILE' - path to xml with tempest results
```
If you want to sync test cases from xml with test cases with automation-test-id:tempest.* and automation-env:001 in Polarion  add "--update_testcases=True"


If you want to attach Jenkins build URL where test was execute - add "--jenkins_build_url $JENKINS_BUILD_URL"

In case of any import errors the logs can be found here: http://ops-qe-logstash-2.rhev-ci-vms.eng.rdu2.redhat.com:9981/polarion/RHELOpenStackPlatform/
