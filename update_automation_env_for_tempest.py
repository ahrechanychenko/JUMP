#!/usr/bin/python

import os
from pylarion import work_item
import sys
import argparse
import logging
from ssl import SSLError
import pprint

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

def get_test_case_objects():
    """
    Connect to Polarion and get test cases where automation-test-id:tempest.*
    :return: list, pylarion Testcase objects
    """
    for i in range(0,10):
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
        except SSLError:
            print "cannot set attribute automation-env for test {} due to Polarion problems".format(test_obj.work_item_id)
        except:
            print "cannot set attribute automation-env for test {} due to Polarion problems".format(test_obj.work_item_id)


def update_automation_env(test_cases):
    """
    Check automation-env attribute in Testcase object and set to '001'-Tempest
    :param test_cases: list with Testcase objects
    :return: None
    """
    global list_of_skipped_test
    list_of_test_with_incorrect_automation_id = []
    for test in test_cases:
        try:
            if test.get_custom_field('automation-env').value is None:
                list_of_test_with_incorrect_automation_id.append(test)
                print "test {} doesn't have automation-env".format(test.work_item_id)
            elif test.get_custom_field('automation-env').value.id.encode() != "001":
                list_of_test_with_incorrect_automation_id.append(test)
                print "test {} have automation-env:{} so change it to tempest- 001".format(test.work_item_id, test.get_custom_field('automation-env').value.id.encode())
            else:
                print "test {} have automation-env:tempest".format(test.work_item_id)
        except SSLError:
            print "test {} wasn't update in due to Polarion problems.Add to list of skipped test".format(test.work_item_id)
            list_of_skipped_test.append(test)
        except:
            print "test {} wasn't update in due to Polarion problems.Add to list of skipped test".format(test.work_item_id)
            list_of_skipped_test.append(test)
    print "\n Full list of skipped test due to Polarion connection issues"
    pprint.pprint(list_of_skipped_test)
    pprint.pprint(list_of_test_with_incorrect_automation_id)
    return list_of_test_with_incorrect_automation_id

def re_check_skipped_test(wrong_automation):
    global list_of_skipped_test
    while len(list_of_skipped_test)!=0:
        for test in list_of_skipped_test:
            try:
                if test.get_custom_field('automation-env').value is None:
                    list_of_test_with_incorrect_automation_id.append(test)
                    list_of_skipped_test.pop(test)
                    print "test {} doesn't have automation-env".format(test.work_item_id)
                elif test.get_custom_field('automation-env').value.id.encode() != "001":
                    list_of_test_with_incorrect_automation_id.append(test)
                    list_of_skipped_test.pop(test)
                    print "test {} have automation-env:{} so change it to tempest- 001".format(test.work_item_id,
                                                                                               test.get_custom_field(
                                                                                                   'automation-env').value.id.encode())
                else:
                    print "test {} have automation-env:tempest".format(test.work_item_id)
                    list_of_skipped_test.pop(test)
            except SSLError:
                print "test {} wasn't update in due to Polarion problems".format(test.work_item_id)
            except:
                print "test {} wasn't update in due to Polarion problems".format(test.work_item_id)
    return list_of_test_with_incorrect_automation_id


if __name__ == "__main__":
    ts = get_test_case_objects()
    correct_ts = get_test_case_objects_with_correct_automation_id()
    wrong_automation = update_automation_env(ts)
    wrong_automation_finally = re_check_skipped_test(wrong_automation)
    print len(ts), len(correct_ts), len(wrong_automation_finally)
