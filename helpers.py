import os
import re
import subprocess
import logging
import pprint
import time

from suds.client import Client
from ssl import SSLError
from xml.dom import minidom
from suds import WebFault

from pylarion import work_item

logging.getLogger('suds.client').setLevel(logging.CRITICAL)


def process_xml(out_xml, custom_fields, properties,
                polarion_tempest_test_cases=None, xml_file=None, manual_test_cases=None,
                jenkins_build_url=None):
    if manual_test_cases:
        xml_file = minidom.Document()
        test_suites = xml_file.createElement("testsuite")
        xml_file.appendChild(test_suites)
        test_suites.setAttribute("tests", "{}".format(len(manual_test_cases)))
        test_suites.setAttribute("failures", "{}".format(manual_test_cases.values().count("failed")))
        for test in manual_test_cases:
            test_cases_el = xml_file.createElement("testcase")
            test_cases_el.setAttribute("classname", "test")
            test_cases_el.setAttribute("name", "{}".format(test))
            if manual_test_cases[test] == "failed":
                failure_el = xml_file.createElement("failure")
                failure_el.setAttribute("type","failure")
                test_cases_el.appendChild(failure_el)
            test_suites.appendChild(test_cases_el)

    elif polarion_tempest_test_cases:
        xml_file = minidom.parse(xml_file)
    else:
        print "Cannot proceed without xml with tempest results"
        exit(1)
    res_doc = minidom.Document()
    test_suites = res_doc.createElement('testsuites')

    new_properties = res_doc.createElement('properties')

    write_testsuite_settings(
        custom_fields, new_properties, res_doc, 'polarion-custom-')
    write_testsuite_settings(
        properties, new_properties, res_doc, 'polarion-')
    test_suites.appendChild(new_properties)

    # process all the testcases within testsuite
    for test_case_xml in xml_file.getElementsByTagName('testcase'):
        name = test_case_xml.attributes['name'].value
        classname = test_case_xml.attributes['classname'].value

        try:
            if not classname:
                continue
            if not manual_test_cases:
                full_name = "{}.{}".format(classname, name)
                full_name_without_uuid = re.match(
                    r'(.*)\[(.*id-)*(.*)\].*', full_name).group(1)
                if full_name_without_uuid.split(".")[0] != "tempest":
                    full_name_without_uuid = "tempest."+full_name_without_uuid
                if full_name_without_uuid not in polarion_tempest_test_cases.keys():
                    print "Test with automation-test id {} not exist in Polarion.Skip it".format(full_name_without_uuid)
                    continue
                print "Writing polarion-testcase-id: {}".format(polarion_tempest_test_cases[full_name_without_uuid])
            properties = xml_file.createElement('properties')
            new_property = xml_file.createElement('property')
            new_property.setAttribute('name', 'polarion-testcase-id')
            if manual_test_cases:
                new_property.setAttribute('value', name)
            else:
                new_property.setAttribute('value', polarion_tempest_test_cases[full_name_without_uuid])
            properties.appendChild(new_property)
            if jenkins_build_url:
                new_property = xml_file.createElement('property')
                new_property.setAttribute('name', 'polarion-testcase-comment')
                new_property.setAttribute('value', jenkins_build_url)
                properties.appendChild(new_property)
            test_case_xml.appendChild(properties)

        except (AttributeError, IndexError):
            pass

    for test_suite_xml in xml_file.getElementsByTagName('testsuite'):
        test_suites.appendChild(test_suite_xml)
    res_doc.appendChild(test_suites)
    with open(out_xml, 'w') as res_file:
        res_file.write(res_doc.toxml())


def write_testsuite_settings(fields, xml_element, xml_file, prefix):
    for name, value in fields.items():
        new_property = xml_file.createElement('property')
        new_property.setAttribute('name', prefix + name)
        new_property.setAttribute('value', str(value))
        xml_element.appendChild(new_property)


def process_properties_fields(args_fields):
    custom_fields = {}
    if args_fields is not None:
        for field in args_fields.split(','):
            key, value = field.split('=')
            custom_fields[key.strip()] = value.strip()
    return custom_fields


def get_tempest_test_list(xml_file):
    """
    1) Parse xml file and generate list with tempest.path
    Returns:
        list with names of tempest test
    """
    xml_file = minidom.parse(xml_file)
    tempest_list = []
    for test_case_xml in xml_file.getElementsByTagName('testcase'):
        name = test_case_xml.attributes['name'].value
        classname = test_case_xml.attributes['classname'].value
        if not classname:
            continue
        tempest_list.append(classname + "." + name)
    return tempest_list


def generate_testcase_xml_file(file_path, project_id,
                               posneg, title,
                               description,
                               automation_test_id,
                               component):
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
  <testcase status-id="approved">
    <title>{title}</title>
    <description>{description}</description>
    <custom-fields>
      <custom-field content="automated" id="caseautomation"/>
      <custom-field content="{automation_test_id}" id="automation-test-id"/>
      <custom-field content="001" id="automation-env"/>
      <custom-field content="medium" id="caseimportance"/>
      <custom-field content="{component}" id="casecomponent"/>
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
           automation_test_id=automation_test_id,
           component=component)
    # write file
    with open('{file_path}/{name}.xml'.format(
            file_path=file_path,
            name=automation_test_id),
            mode="w+") as f:
        f.write(template)
    os.path.isfile("{file_path}/{name}.xml".format(file_path=file_path, name=automation_test_id))


def get_polarion_tempest_test_cases(project):
    """
        Get all tempest test from Polarion
        1) Connect to Polarion and get test_cases object via query
        2) Create dict  {automation-test-id:test_case_id}
        Returns:
            automation_test_id_dict:, dict {automation-test-id:test_case_id}
    """
    for i in range(0, 5):
        try:
            test_cases = work_item.TestCase.query(
                query="automation-test-id:tempest.* AND automation-env:001",
                project_id=project, fields=["automation-test-id", "work_item_id"])
            break
        except SSLError:
            time.sleep(60)
            continue
        except WebFault:
            time.sleep(60)
            continue
        except:
            time.sleep(60)
            continue

    try:
        test_cases
    except NameError:
        test_cases = None
        print "Cannot connect to Polarion Server in 5 minutes."
        exit(1)

    automation_test_id_dict = {}
    duplicates = []
    print "Get all test cases from Polarion with automation-test-id:tempest.* and automation-env:001"
    for test in test_cases:
        for i in range(0, 200):
            try:
                test_id = getattr(test, 'automation-test-id').encode()
                if test_id in automation_test_id_dict.keys():
                    duplicates.append("{} and {} have the same automation-test-id:{}".format(
                        test.work_item_id, automation_test_id_dict[test_id], test_id))
                    break
                else:
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

    # due to unstable polarion check if we have some skipped test
    for test in test_cases:
        test_id = getattr(test, 'automation-test-id').encode()
        if test_id not in automation_test_id_dict.keys():
            print "test {} was skip. Update dict".format(test.work_item_id)
            for i in range(0, 10):
                try:
                    automation_test_id_dict[test_id] = test.work_item_id
                    break
                except SSLError:
                    print "Test {} was skipped. Retry".format(test.work_item_id)
                    if i == 9:
                        print "Test {} was skipped. Cannot connect to polarion after 10 attempts".format(
                            test.work_item_id)
                    continue
                except WebFault:
                    print "Test {} was skipped. Retry".format(test.work_item_id)
                    if i == 9:
                        print "Test {} was skipped. Cannot connect to polarion after 10 attempts".format(
                            test.work_item_id)
                    continue
                except:
                    print "Test {} was skipped. Retry".format(test.work_item_id)
                    if i == 9:
                        print "Test {} was skipped. Cannot connect to polarion after 10 attempts".format(
                            test.work_item_id)
                    continue
    print "List of duplicated test with automation-test-id:tempest* and automation-env:001"
    pprint.pprint(duplicates)
    print "\n Full list of tests with automation-test-id:tempest* and automation-env:001"
    pprint.pprint(automation_test_id_dict)
    return automation_test_id_dict


def get_project_for_tempest_path(tempest_path):
    """
    :param tempest_path: str, tempest full path
    :return: str, project_id
    """
    #get tempest component from api test
    component = {"compute":"Nova", "network":"Neutron", "image":"Glance",
                 "object_storage":"Ceph", "volume":"Cinder", "identity":"Keystone"}

    if tempest_path.split(".",3)[1] == "api":
        try:
            project = component[tempest_path.split(".",3)[2]]
        except KeyError:
            project = "Unclassified"
    else:
        project = "Unclassified"

    return project


def check_tempest_test_in_polarion(tempest_lst, xml_dir, project):
    """
    Check if tempest test already exist in Polarion
    and if not - generate xml for importing
    :param tempest_lst: list, list with tempest tests
    :param xml_dir: str, path in system for storing xml,
    by default - '/tmp/test_tempest_updater'
    """
    automation_test_id_dict = get_polarion_tempest_test_cases(project)
    generated_list = []
    for test in tempest_lst:
        print "check test {}".format(test)
        if test.split("[")[0].split(".")[0] == "tempest":
            automation_test_id = test.split("[")[0]
        else:
            automation_test_id = "tempest." + test.split("[")[0]
        if automation_test_id not in automation_test_id_dict:
            generated_list.append(automation_test_id)
            generate_testcase_xml_file(
                file_path=xml_dir,
                project_id=project,
                posneg="negative" if "negative" in test else "positive",
                title="{}".format(
                    automation_test_id.rsplit('.', 1)[1]),
                description="",
                automation_test_id=automation_test_id,
                component=get_project_for_tempest_path(test))
        else:
            print "tempest test {} exist in Polarion {} project " \
                  "and covered by {}\n".format(test.split("[")[0],
                                             project,
                                             automation_test_id_dict[test.split("[")[0]])
    if len(generated_list)>0:
        print "Generated xml files for next automation-test-id:"
        pprint.pprint(generated_list)
        print "\n"


def upload_test_cases_in_polarion(path):
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
        subprocess.check_call(cmd,
                              shell=True)
        print "{} was upload to Polarion".format(xml_file)


def update_test_run(xml_file, test_run_id):
    cmd = 'curl -k -u rhosp_machine:polarion -X POST ' \
          '-F file=@./{} ' \
          'https://polarion.engineering.redhat.com' \
          '//polarion/import/xunit'.format(xml_file)
    subprocess.check_call(cmd,
                          shell=True)
    print "Test run {} was updated with tempest results".format(test_run_id)


def get_test_case_with_incorrect_env(project_id):
    """
    Connect to Polarion and get test cases where automation-test-id:tempest.*
    :return: list, pylarion Testcase objects
    """
    for i in range(0,10):
        try:
            test_cases = work_item.TestCase.query(
                query="automation-test-id:tempest.* AND NOT automation-env:001",
                project_id=project_id)
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


def get_test_case_objects_with_correct_automation_id(project_id):
    """
    Connect to Polarion and get test cases where automation-test-id:tempest.*
    :return: list, pylarion Testcase objects
    """
    for i in range(0,10):
        try:
            test_cases = work_item.TestCase.query(
                query="automation-test-id:tempest.* AND automation-env:001",
                project_id=project_id)
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


def update_test_cases_with_tempest_tests(xml_file, project, path, dry_run):
    tempest_list = get_tempest_test_list(xml_file)
    print "\nCheck for missed test cases from xml in Polarion \n"
    if os.path.isdir(path):
        os.system("cd {} && rm -rf *".format(path))
    else:
        os.mkdir(path)
    check_tempest_test_in_polarion(tempest_lst=tempest_list, xml_dir=path, project=project)
    if dry_run:
        print "DRY_MODE ENABLED: Skip uploading test cases"
    else:
        if len([name for name in os.listdir(path) if os.path.isfile(
                os.path.join(path, name))]) > 0:
            upload_test_cases_in_polarion(path=path)
            print "\n wait for 10 minutes after importing test cases before update test run\n "
            time.sleep(10 * 60)
        else:
            print "All test cases from xml file are exist in Polarion"

