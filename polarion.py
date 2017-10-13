#!/usr/bin/python

import datetime
import os
from pylarion import test_run
import sys
import argparse

parser = argparse.ArgumentParser(description="Send results of test-case to Polarion test run ")
parser.add_argument("--project_id",
                    help="polarion project id, \n for example - RHELOpenStackPlatform", required=True)
parser.add_argument("--test_run_id",
                    help="polarion test run id, \n for example - 20170809-2057", required=True)
parser.add_argument("--polarion_user", default="rhos_machine", type=str,
                    help="polarion user in short format, by default - rhosp_machine")
parser.add_argument("--jenkins_build_url",
                    help="url for jenkins build where test was executed", required=True)
parser.add_argument("--duration",
                    help="duration time, for example 1.123", required=True, type=float)
parser.add_argument('--testcases', required=True, help="list of testcases and their results - passed|failed \n "
                                                       "for example: 'TEST_CASE1=passed, TEST_CASE2=failed'")

args = parser.parse_args()

# check for CA
try:
   os.environ["REQUESTS_CA_BUNDLE"]
except KeyError:
   print "Please set the environment variable REQUESTS_CA_BUNDLE"
   sys.exit(1)

# reload sys to use "utf8" instead of "unicode"
reload(sys)
sys.setdefaultencoding('utf8')

# get variables values
PROJECT_ID = args.project_id
TEST_RUN_ID = args.test_run_id
BUILD_URL = args.jenkins_build_url
POLARION_USER = args.polarion_user
DURATION = args.duration
TEST_CASES = dict((x, y) for x, y in [tuple(i.split('=')) for i in args.testcases.split(',')])


def update_polarion_test_run(tr_instance,
                             test_cases,
                             test_comment=BUILD_URL,
                             executed_by=POLARION_USER,
                             executed=datetime.datetime.now(),
                             duration=DURATION):
    for test_case_id in test_cases:
        while True:
            try:
                tr_instance.update_test_record_by_fields(
                    test_case_id,
                    test_cases[test_case_id],
                    test_comment,
                    executed_by,
                    executed,
                    duration)
                break
            except:
                continue


if __name__ == "__main__":
    while True:
        try:
            tr = test_run.TestRun(test_run_id=TEST_RUN_ID, project_id=PROJECT_ID)
            break
        except:
            continue

    if tr.status == "notrun":
        tr.status = "inprogress"
        while True:
            try:
                tr.update()
                break
            except:
                continue

    update_polarion_test_run(tr,
                             TEST_CASES,
                             test_comment=BUILD_URL,
                             executed_by=POLARION_USER,
                             executed=datetime.datetime.now(),
                             duration=DURATION)
