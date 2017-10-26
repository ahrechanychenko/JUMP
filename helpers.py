import os
import re
import sys
import subprocess
import logging
import pprint
import datetime

from ssl import SSLError
from xml.dom import minidom
from suds import WebFault

from pylarion import test_run
from pylarion import work_item


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def process_xml(xml_file, out_xml, custom_fields, properties, polarion_test_cases):
    xml_file = minidom.parse(xml_file)

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
            full_name = "{}.{}".format(classname, name)
            full_name_without_uuid = re.match(
                r'(.*)\[(.*id-)*(.*)\].*', full_name).group(1)
            if full_name_without_uuid not in polarion_test_cases.keys():
                print "Test with automation-test id {} not exist in Polarion.Skip it".format(full_name_without_uuid)
                continue

            logger.info("Writing polarion-testcase-id: %s",
                        polarion_test_cases[full_name_without_uuid])
            properties = xml_file.createElement('properties')
            new_property = xml_file.createElement('property')
            new_property.setAttribute('name', 'polarion-testcase-id')
            new_property.setAttribute('value', polarion_test_cases[full_name_without_uuid])
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
        tempest_list.append(name+classname)
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
    for i in range(0, 50):
        try:
            test_cases = work_item.TestCase.query(
                query="automation-test-id:tempest.* AND automation-env:001",
                project_id=project, fields=["automation-test-id", "work_item_id"])
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
    duplicates = []
    for test in test_cases:
        for i in range(0, 200):
            try:
                test_id = getattr(test, 'automation-test-id').encode()
                if test_id in automation_test_id_dict.keys():
                    print "Dublicated test {} - with {} id. Skip it".format(test_id, test.work_item_id)
                    duplicates.append(test.work_item_id)
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
    print "duplicates count - {}".format(len(duplicates))
    return automation_test_id_dict


def get_project_for_tempest_path(tempest_path):
    """
    :param tempest_path: str, tempest full path
    :return: str, project_id
    """
    if any(("cinder" in tempest_path, "volume" in tempest_path)):
        if "compute" in tempest_path.rsplit('[')[1].split(',')[0]:
            return "Nova"
        elif any(("neutron" in tempest_path.rsplit('[')[1].split(',')[0],
                  "network" in tempest_path.rsplit('[')[1].split(',')[0])):
            return "Neutron"
        else:
            return "Cinder"
    elif "image" in tempest_path:
        if "compute" in tempest_path:
            return "Nova"
        elif any(("neutron" in tempest_path, "network" in tempest_path)):
            return "Neutron"
        elif "volume" in tempest_path:
            return "Cinder"
        else:
            return "Glance"
    elif "compute" in tempest_path:
        return "Nova"
    elif any(("neutron" in tempest_path, "network" in tempest_path)):
        return "Neutron"
    elif "object_storage" in tempest_path:
        return "Ceph"
    elif "identity" in tempest_path:
        return "Keystone"
    else:
        print "Cannot find project for {}. Set to default - PolarionTesting".format(tempest_path)
        return "Polarion-testing"


def check_tempest_test_in_polarion(tempest_lst, xml_dir, project):
    """
    Check if tempest test already exist in Polarion
    and if not - generate xml for importing
    :param tempest_lst: list, list with tempest tests
    :param path: str, path in system for storing xml,
    by default - '/tmp/test_tempest_updater'
    """
    automation_test_id_dict = get_polarion_tempest_test_cases(project)
    # print test with exist in polarion but didn't exist in upstream
    tempest_ids_from_xml = [x.split("[")[0] for x in tempest_lst]
    for test in tempest_lst:
        print "check test {}".format(test)
        if test.split("[")[0] not in automation_test_id_dict:
            print "\n {} doesn't exist in Polarion, " \
                  "generate xml for it".format(test.split("[")[0])
            generate_testcase_xml_file(
                file_path=xml_dir,
                project_id=project,
                posneg="negative" if "negative" in test else "positive",
                title="{}".format(
                    test.split("[")[0].rsplit('.', 1)[1]),
                description="",
                automation_test_id=test.split("[")[0],
                component=get_project_for_tempest_path(test))
        else:
            print "\n tempest test {} exist in Polarion {} project " \
                  "and covered by {}".format(test.split("[")[0],
                                             project,
                                             automation_test_id_dict[test.split("[")[0]])


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


def manual_update_polarion_test_run(tr_instance,
                             test_cases,
                             test_comment,
                             executed_by,
                             executed,
                             duration):
        for test_case_id in test_cases:
            try:
                tr_instance.update_test_record_by_fields(
                    test_case_id,
                    test_cases[test_case_id],
                    test_comment,
                    executed_by,
                    executed,
                    duration)

            except WebFault:
                print "test case {} was skip due to Polarion issue".format(test_case_id)
            except SSLError:
                print "test case {} was skip due to Polarion issue".format(test_case_id)
            except:
                print "test case {} was skip due to Polarion issue".format(test_case_id)


def get_test_run_instance(test_run_id, project_id):
    for i in range(0,10):
        try:
            tr = test_run.TestRun(test_run_id=test_run_id, project_id=project_id)
            break
        except WebFault:
            if i == 9:
                print "cannot get test run instance via pylarion during to connection issues"
            continue
        except SSLError:
            if i == 9:
                print "cannot get test run instance via pylarion during to connection issues"
            continue
        except:
            if i == 9:
                print "cannot get test run instance via pylarion during to connection issues"
            continue


def update_test_cases_with_tempest_tests(xml_file, project, dry_run):
    tempest_list = get_tempest_test_list(xml_file)
    check_tempest_test_in_polarion(tempest_lst=tempest_list, xml_dir='/tmp/test_tempest_updater', project=project)
    if dry_run:
        print "DRY_MODE ENABLED: Skip uploading test cases"
    else:
        upload_test_cases_in_polarion(path='/tmp/test_tempest_updater')

