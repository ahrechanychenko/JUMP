#!/usr/bin/python

import os
from pylarion import work_item
import sys
import argparse
import subprocess
import logging
import pprint
from ssl import SSLError
from suds import WebFault

logging.getLogger('suds.client').setLevel(logging.CRITICAL)

parser = argparse.ArgumentParser(
    description="Compare list of upstream tempest test "
                "with list test cases "
                "where automation-test-id == tempest test path in Polarion")
parser.add_argument("--project_id",
                    help="polarion project id, "
                         "\n for example - RHELOpenStackPlatform",
                    required=True)

parser.add_argument("--polarion_user",
                    default="rhos_machine",
                    type=str,
                    help="polarion user in short format, "
                         "by default - rhosp_machine")

parser.add_argument("--polarion_password",
                    default="polarion",
                    type=str,
                    help="polarion user in short format, "
                         "by default - polarion")

parser.add_argument("--dry_run",
                    type=bool,
                    help="generate xml files with missed tempest "
                         "test cases and don't upload them to Polarion")
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
POLARION_USER = args.polarion_user
POLARION_PASS = args.polarion_user
DRY_RUN = args.dry_run


def get_tempest_test_list():
    """
    1) check if tempest workspace cloud-test exist and init it doesn't exist
    2) run 'tempest run -l' to get list of default test
    Returns:
        list with names of tempest test
    """
    # check if we already have tempest workspace
    process = subprocess.Popen("tempest workspace list",
                               shell=True,
                               stdout=subprocess.PIPE)
    out, err = process.communicate()
    if len(out.split('\n')[1]) == 0:
        subprocess.check_call('cd /tmp/tempest && '
                              'tempest init cloud-test || true',
                              shell=True)
    subprocess.check_call('rm -rf /tmp/test_tempest_updater '
                          '&& mkdir /tmp/test_tempest_updater',
                          shell=True)
    # get list of test
    process = subprocess.Popen("cd /tmp/tempest/cloud-test && tempest run -l",
                               shell=True,
                               stdout=subprocess.PIPE)
    out, err = process.communicate()
    tempest_test = out.split('\n')

    # remove empty values
    tempest_test = filter(None, tempest_test)

    # return list of test
    return tempest_test[5:]


def generate_testcase_xml_file(file_path, project_id,
                               posneg, title,
                               description,
                               automation_test_id):
    """
    Generate xml for each missed test case which must exist in Polarion
    Args:
        file_path: str , path to storing xml file.
        project_id: str, Polarion project ID.
        posneg: str, test case Pos/Neg
        title: str, title of test case
        description: str, description of test case
        automation_test_id: str, automation-test-id for test case
    """

    # generate content for writing to xml file
    template = """<?xml version="1.0" ?>
<testcases project-id="{project_id}">
  <<testcase status-id="approved">
    <title>{title}</title>
    <description>{description}</description>
    <custom-fields>
      <custom-field content="automated" id="caseautomation"/>
      <custom-field content="{automation_test_id}" id="automation-test-id"/>
      <custom-field content="001" id="automation-env"/>
      <custom-field content="medium" id="caseimportance"/>
      <custom-field content="Polarion-testing" id="casecomponent"/>
      <custom-field content="acceptance" id="caselevel"/>
      <custom-field content="{posneg}" id="caseposneg"/>
      <custom-field content="functional" id="testtype"/>
    </custom-fields>
    <linked-work-items>
        <linked-work-item workitem-id="RHELOSP-21959" role-id="verifies"/>
    </linked-work-items>
  </testcase>
</testcases>
""".format(project_id=project_id,
           title=title,
           description=description,
           posneg=posneg,
           automation_test_id=automation_test_id)
    # write file
    with open('{file_path}/{name}.xml'.format(
            file_path=file_path,
            name=automation_test_id),
            mode="w+") as f:
        f.write(template)
    os.path.isfile("{}/{name}.xml".format(file_path, name=automation_test_id))


def get_polarion_tempest_test_cases():
    """
        Get all tempest test from Polarion
        1) Connect to Polarion and get test_cases object via querry
        2) return dict  {automation-test-id:test_case_id}
        Returns:
            dict: {automation-test-id:test_case_id}
    """
    for i in range(0, 50):
        try:
            test_cases = work_item.TestCase.query(
                query="automation-test-id:tempest.* AND automation-env:001",
                project_id='RHELOpenStackPlatform')
            break
        except SSLError:
            continue
        except WebFault:
            continue
        except:
            continue

    try:
        test_cases
    except NameError:
        test_cases = None
        print "Cannot connect to Polarion Server in 50 attemts"
        exit(1)

    automation_test_id_dict = {}
    dublicates = []
    for test in test_cases:
        for i in range(0, 200):
            try:
                test_id = test.get_custom_field(
                    'automation-test-id').value.encode()
                if test_id in automation_test_id_dict.keys():
                    print "test with that {} and {} id exist .skip it".format(test_id, test.work_item_id)
                    dublicates.append(test.work_item_id)
                automation_test_id_dict[test_id] = test.work_item_id
                break
            except SSLError:
                if i == 199:
                    print "Test {} was skipped".format(test.work_item_id)
                continue
            except WebFault:
                if i == 199:
                    print "Test {} was skipped".format(test.work_item_id)
                continue
            except:
                if i == 199:
                    print "Test {} was skipped".format(test.work_item_id)
                continue
    
    #due to unstable polarion check if we have some skipped test
    for test in test_cases:
        if test.work_item_id not in automation_test_id_dict.values():
            print "test {} was skip. Update dict".format(test.work_item_id)
            for i in range(0, 10):
                try:
                    test_id = test.get_custom_field(
                    'automation-test-id').value.encode()
                    if test_id in automation_test_id_dict.keys():
                        print "test with that {} and {} id exist .skip it".format(test_id, test.work_item_id)
                        dublicates.append(test.work_item_id)
                    automation_test_id_dict[test_id] = test.work_item_id
                    break
                except SSLError:
                    print "Test {} was skipped. Retry".format(test.work_item_id)
                    if i == 9:
                        print "Test {} was skipped. Cannot connect to polarion after 10 attempts".format(test.work_item_id)
                    continue
                except WebFault:
                    print "Test {} was skipped. Retry".format(test.work_item_id)
                    if i == 9:
                        print "Test {} was skipped. Cannot connect to polarion after 10 attempts".format(test.work_item_id)
                    continue
                except:
                    print "Test {} was skipped. Retry".format(test.work_item_id)
                    if i == 9:
                        print "Test {} was skipped. Cannot connect to polarion after 10 attempts".format(test.work_item_id)
                    continue
    print "dublicates count - {}".format(len(dublicates)
    pprint.pprint(dublicates)
    return automation_test_id_dict


def check_tempest_test_in_polarion(tempest_lst, path):
    """
    Check if tempest test already exist in Polarion
    and if not - generate xml for importing
    :param tempest_lst: list, list with tempest tests
    :param path: str, path in system for storing xml,
    by default - '/tmp/test_tempest_updater'
    """
    automation_test_id_dict = get_polarion_tempest_test_cases()
    print len(automation_test_id_dict)
    pprint.pprint(automation_test_id_dict)
    pprint.pprint(tempest_lst)

    for test in tempest_lst:
        print "check test {}".format(test)
        if test.split("[")[0] not in automation_test_id_dict:
            print "\n {} doesn't exist in Polarion, " \
                  "generate xml for it".format(test.split("[")[0])
            generate_testcase_xml_file(
                file_path=path,
                project_id=PROJECT_ID,
                posneg="negative" if "negative" in test else "positive",
                title="tempest test which covers {}".format(
                    test.split("[")[0]),
                description="",
                automation_test_id=test.split("[")[0])
        else:
            print "\n tempest test {} exist in Polarion {} project " \
                  "and covered by {}".format(test.split("[")[0],
                                             PROJECT_ID,
                                             automation_test_id_dict[test.split("[")[0]])


def update_test_cases_in_polarion(path):
    """
        Upload test cases which cover
        missed tempest tests via curl to stage job
    """
    list_of_xml = [f for f in os.listdir(path) if
                   os.path.isfile(os.path.join(path, f))]
    for xml_file in list_of_xml:
        cmd = 'curl -k -u rhosp_machine:polarion -X POST ' \
              '-F file=@/{}/{} ' \
              'https://polarion.engineering.redhat.com' \
              '//polarion/import/testcase'.format(path, xml_file)
        print "{} was upload to Polarion".format(xml_file)
        subprocess.check_call(cmd,
                              shell=True)

if __name__ == "__main__":
    tempest_list = get_tempest_test_list()
    print "tempest test count in upstream - {}".format(ilen(tempest_list))
    check_tempest_test_in_polarion(tempest_list, '/tmp/test_tempest_updater')
    if DRY_RUN:
        print "\n dry-run completed, xml files was generate"
        exit(0)
    else:
        update_test_cases_in_polarion(path='/tmp/test_tempest_updater')
