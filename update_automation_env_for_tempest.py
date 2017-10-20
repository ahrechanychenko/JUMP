#!/usr/bin/python

import os
from pylarion import work_item
import sys
import argparse
import logging
from ssl import SSLError
import pprint
import time

logging.getLogger('suds.client').setLevel(logging.CRITICAL)

parser = argparse.ArgumentParser(
    description="Get Polarion test cases which have "
                "'automation-test-id':tempest.* and update automation-env to tempest")
parser.add_argument("--project_id",
                    help="polarion project id, "
                         "\n for example - RHELOpenStackPlatform",
                    required=True)

parser.add_argument("--dry_run",
                    type=bool,
                    help="only check and print results")
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
DRY_RUN = args.dry_run

list_of_skipped_test = []


def get_test_case_with_incorrect_env():
    """
    Connect to Polarion and get test cases where automation-test-id:tempest.*
    :return: list, pylarion Testcase objects
    """
    for i in range(0,10):
        try:
            test_cases = work_item.TestCase.query(
                query="automation-test-id:tempest.* AND NOT automation-env:001",
                project_id=PROJECT_ID)
            break
        except SSLError:
            continue
        except:
            continue

    try:
        test_cases
    except NameError:
        test_cases = None
        print "Cannot connect to Polarion Server after ten attempts"
        exit(1)
    return test_cases

def get_test_case_objects_with_correct_automation_id():
    """
    Connect to Polarion and get test cases where automation-test-id:tempest.*
    :return: list, pylarion Testcase objects
    """
    for i in range(0,10):
        try:
            test_cases = work_item.TestCase.query(
                query="automation-test-id:tempest.* AND automation-env:001",
                project_id=PROJECT_ID)
            break
        except SSLError:
            continue
        except:
            continue

    try:
        test_cases
    except NameError:
        test_cases = None
        print "Cannot connect to Polarion Server after ten attempts"
        exit(1)
    return test_cases


def update_automation_env(test_obj, code):
    if DRY_RUN:
            pass
    else:
        try:
            setattr(test_obj, "automation-env", code)
            test_obj.update()
            print "test {} was update to automation-env:001".format(test_obj.work_item_id)
        except SSLError:
            print "cannot set attribute automation-env for test {} due to Polarion problems".format(test_obj.work_item_id)
        except:
            print "cannot set attribute automation-env for test {} due to Polarion problems".format(test_obj.work_item_id)


def update_test_with_wrong_automation_id(test_cases):
    """
    Update automation-env attribute in Testcase object and set to '001'-Tempest
    :param test_cases: list with Testcase objects
    :return: None
    """
    for test in test_cases:
        try:
            update_automation_env(test, '001')
        except SSLError:
            print "test {} wasn't update in due to Polarion problems.Skip it".format(test.work_item_id)
        except:
            print "test {} wasn't update in due to Polarion problems.Skip it".format(test.work_item_id)

if __name__ == "__main__":
    ts = get_test_case_with_incorrect_env()
    update_test_with_wrong_automation_id(ts)

