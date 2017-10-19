#!/usr/bin/python

import os
from pylarion import work_item
import sys
import argparse
import logging
from ssl import SSLError

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


def get_test_case_objects():
    """
    Connect to Polarion and get test cases where automation-test-id:tempest.*
    :return: list, pylarion Testcase objects 
    """
    for i in range(0, 500):
        try:
            test_cases = work_item.TestCase.query(
                query="automation-test-id:tempest.*",
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
        print "Cannot connect to Polarion Server in 100 attemts"
        exit(1)
    return test_cases


def update_automation_env(test_obj, code):
    for i in range(0,500):
        try:
            if DRY_RUN:
                pass
            else:
                setattr(test_obj, "automation-env", code)
                test_obj.update()
                break
        except SSLError:
            continue
        except:
            continue


def update_automation_env(test_cases):
    """
    Check automation-env attribute in Testcase object and set to '001'-Tempest
    :param test_cases: list with Testcase objects
    :return: None
    """

    for test in test_cases:
        for i in range(0,500):
            try:
                if test.get_custom_field('automation-env').value is None:
                    update_automation_env(test, '001')
                    print "test {} doesn't have automation-env".format(test.work_item_id)
                    break
                elif test.get_custom_field('automation-env').value.id.encode() != "001":
                    update_automation_env(test, '001')
                    print "test {} have automation-env:{} so change it to tempest- 001".format(test.work_item_id, test.get_custom_field('automation-env').value.id.encode())
                    break
                else:
                    print "test {} have automation-env:tempest".format(test.work_item_id)
                    break
            except SSLError:
                continue
            except:
                continue


if __name__ == "__main__":
    ts = get_test_case_objects()
    update_automation_env(ts)
