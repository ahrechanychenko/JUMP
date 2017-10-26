import argparse
import time

from helpers import get_polarion_tempest_test_cases
from helpers import update_test_cases_with_tempest_tests
from helpers import manual_update_polarion_test_run
from helpers import get_test_run_instance
from helpers import process_properties_fields
from helpers import process_xml


def main():
    parser = argparse.ArgumentParser(
        description='JUMP tools for updating Polarion Test Runs \n '
                    'The tool support two ways: \n'
                    '1) xml mode - parse tempest xml file and update using Polarion XUnit importer'
                    '2) manual test case update from command line')
    parser.add_argument('--xml-file', help='The xUnit xml resulting file',
                        required=False)
    parser.add_argument('--output-xml', help='The resulting xml file',
                        default='result.xml')
    parser.add_argument('--user-id', help='The user',
                        default='rhosp_machine')
    parser.add_argument('--project-id', help='The project id',
                        default='RHELOpenStackPlatform')
    parser.add_argument('--testrun-finished',
                        help='Specifies whether the testrun should be finished',
                        action='store_false')
    parser.add_argument('--include-skipped',
                        help='Include skipped test cases',
                        action='store_true')
    parser.add_argument('--testrun-title',
                        help='Test run title',
                        default='Generated by CI')
    parser.add_argument('--testrun-id',
                        help='Test run id (name)',
                        required=True)
    parser.add_argument('--custom-fields',
                        help='Custom fields separated with commas')
    parser.add_argument('--properties',
                        help='Properties separated with commas')
    parser.add_argument("--jenkins_build_url",
                        help="url for jenkins build where test was executed", required=False)
    parser.add_argument("--duration",
                        help="duration time, for example 1.123", required=True, type=float)
    parser.add_argument('--testcases', required=False, help="list of testcases and their results - passed|failed \n "
                                                            "for example: 'TEST_CASE1=passed, TEST_CASE2=failed'")
    parser.add_argument('--update_testcases', type=bool, required=False, help="Sync Polarion test cases with tests from xml file")
    parser.add_argument("--dry_run",
                        type=bool,
                        help="generate xml files with missed tempest "
                             "test cases and don't upload them to Polarion")

    args = parser.parse_args()
    if args.xml_file:
        if args.update_testcases:
            update_test_cases_with_tempest_tests(args.xml_file, args.project_id, args.dry_run)
            print "\n wait for 5 minutes after importing test cases before update test run\n "
            time.sleep(5*60)
        custom_fields = process_properties_fields(args.custom_fields)
        properties = {
            "project-id": args.project_id,
            "user-id": args.user_id,
            "set-testrun-finished": args.testrun_finished,
            "include-skipped": args.include_skipped,
            "testrun-id": args.testrun_id,
            "testrun-title": args.testrun_title
        }
        if args.dry_run:
            print "skip updating results due to dry_run"
        else:
            test_cases = get_polarion_tempest_test_cases(args.project_id)
            process_xml(args.xml_file,
                        args.output_xml,
                        custom_fields=custom_fields,
                        properties=properties,
                        polarion_test_cases=test_cases)
    elif args.testcases:
        manual_testcases = dict((x, y) for x, y in [tuple(i.split('=')) for i in args.testcases.split(',')])
        test_run_instance = get_test_run_instance(test_run_id=args.testrun_id, project_id=args.project_id)
        manual_update_polarion_test_run(tr_instance=test_run_instance,
                                        test_cases=manual_testcases,
                                        test_comment=args.jenkins_build_url,
                                        executed_by=args.user_id,
                                        duration=args.duration)
    else:
        print "Please choose between xml mode and manual"

if __name__ == "__main__":
    main()
