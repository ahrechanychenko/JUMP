#!/usr/bin/python

import os
from pylarion import work_item
import sys
import argparse
import subprocess
import logging
import requests
import json

logging.getLogger('suds.client').setLevel(logging.CRITICAL)

parser = argparse.ArgumentParser(description="Compare list of upstream tempest test "
                                             "with list test cases "
                                             "where automation-test-id == tempest test path in Polarion")
parser.add_argument("--project_id",
                    help="polarion project id, \n for example - RHELOpenStackPlatform", required=True)

parser.add_argument("--polarion_user", default="rhos_machine", type=str,
                    help="polarion user in short format, by default - rhosp_machine")

parser.add_argument("--polarion_password", default="polarion", type=str,
                    help="polarion user in short format, by default - polarion")
parser.add_argument("--dry_run", type=bool,
                    help="generate xml files with missed tempest test cases and don't upload them to Polarion")
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
    print "\n Install tempest \n"
    """ 
    1) clone upstream tempest
    2) install in in virtual 
    3) prepare tempest for work
    4) run 'tempest run -l' to get list of default test

    Returns:
        list with names of tempest test

    """
    # check if we already have tempest workspace
    process = subprocess.Popen("tempest workspace list", shell=True, stdout=subprocess.PIPE)
    out, err = process.communicate()
    if len(out.split('\n')[1]) == 0:
        subprocess.check_call('cd /tmp/tempest && tempest init cloud-test || true',
                              shell=True)
    subprocess.check_call('rm -rf /tmp/test_tempest_updater && mkdir /tmp/test_tempest_updater',
                          shell=True)
    # get list of test
    process = subprocess.Popen("cd /tmp/tempest/cloud-test && tempest run -l",
                               shell=True,
                               stdout=subprocess.PIPE)
    out, err = process.communicate()
    tempest_test = out.split('\n')

    # return list of test
    return tempest_test[5:]


def generate_testcase_xml_file(file_path, project_id, assignee, title, description, automation_test_id):
    """ 
    Generate xml for each missed test case which must exist in Polarion

    Args:
        file_path: str , path to storing xml file.
        project_id: str, Polarion project ID.
        assignee: str, person for assigning test case
        title: str, title of test case
        description: str, description of test case
        automation_test_id: str, automation-test-id for test case 

    """
    print "\n Generate xml file for {}  \n".format(automation_test_id)

    # generate content for writing to xml file
    template = """<?xml version="1.0" ?>
<testcases project-id="{project_id}">
  <testcase assignee-id="{assignee}" due-date="2016-09-30" initial-estimate="">
    <title>{title}</title>
    <description>{description}</description>
    <custom-fields>
      <custom-field content="automated" id="caseautomation"/>
      <custom-field content="{automation_test_id}" id="automation-test-id"/>
      <custom-field content="tempest" id="automation-env"/>
      <custom-field content="medium" id="caseimportance"/>
      <custom-field content="Polarion-testing" id="casecomponent"/>
      <custom-field content="component" id="caselevel"/>
      <custom-field content="positive" id="caseposneg"/>
      <custom-field content="yes" id="upstream"/>
      <custom-field content="functional" id="testtype"/>
      <custom-field content="setup" id="setup"/>
      <custom-field content="teardown by cleaning the workspace." id="teardown"/>
      <custom-field content="{github_url}" id="automation_script"/>
    </custom-fields>
  </testcase>
</testcases>
""".format(assignee=assignee,
           project_id=project_id,
           title=title,
           description=description,
           automation_test_id=automation_test_id,
           github_url=get_url_to_file_by_tempest_path(automation_test_id))
    # write file
    with open('{file_path}/{name}.xml'.format(file_path=file_path, name=automation_test_id), mode="w+") as f:
        f.write(template)
    #TODO just for debug, remove after debug was complete
    os.path.isfile("{}/{name}.xml".format(file_path,name=automation_test_id))


def get_test_case_id_by_automation_id(automation_id, project):
    """ 
        Check if automation_id exist in polarion
        1) Connect to Polarion and via query 
        2) return "Not Found" or "Test Case ID"

        Args:
            automation_id: str, automation-test-id for test case
            project: str, Polarion project ID

        Returns:
            str: "Not Found" or Polarion Test Case ID

        """
    test_case = work_item.TestCase.query(query="automation-test-id:{}".format(automation_id), project_id=project)
    if len(test_case) == 0:
        return "Not Found"
    else:
        return test_case[0].work_item_id


def check_tempest_test_in_polarion(tempest_list, assignee, path):
    for test in tempest_list:
        for i in range(0, 100):
            try:
                res = get_test_case_id_by_automation_id(test.split("[")[0], PROJECT_ID)
                if "Not Found" in res:
                    generate_testcase_xml_file(file_path=path,
                                               project_id=PROJECT_ID,
                                               assignee=assignee,
                                               title="tempest test which covers {}".format(test.split("[")[0]),
                                               description="",
                                               automation_test_id=test.split("[")[0])
                else:
                    print "\n tempest test {} exist in Polarion {} project and covered by {}".format(test.split("[")[0], PROJECT_ID, res)
                break
            except:
                continue

                
def get_url_to_file_by_tempest_path(tempest_path):
    querry_name = tempest_path.rsplit('.',1)[1]
    requests.packages.urllib3.disable_warnings()
    r = requests.get('https://api.github.com/search/code?q={}+repo:openstack/tempest'.format(querry_name), verify=False)
    return json.loads(r.content)['items'][0]['html_url']

  
def update_test_cases_in_polarion(path):
    """ 
        Upload test cases which covering missed tempest tests via curl to stage job 


    """
    list_of_xml = [f for f in os.listdir(path) if
                   os.path.isfile(os.path.join(path, f))]
    for xml_file in list_of_xml:
        cmd = 'curl -k -u rhosp_machine:polarion -X POST ' \
              '-F file=@/{}/{} ' \
              'https://polarion.engineering.redhat.com//polarion/import/testcase'.format(path, xml_file)
        print "{} was upload to Polarion".format(xml_file)
        subprocess.check_call(cmd,
                              shell=True)


if __name__ == "__main__":
    tempest_list = get_tempest_test_list()
    check_tempest_test_in_polarion(tempest_list, "rhosp-user", path='/tmp/test_tempest_updater')
    if DRY_RUN:
        print "\n dry-run completed, xml files was generate"
        exit(0)
    else:
        update_test_cases_in_polarion(path='/tmp/test_tempest_updater')

