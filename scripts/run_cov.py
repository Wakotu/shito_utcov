"""
run each unit test and collect its coverage information
"""

import argparse
import json
import logging
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass

logging.basicConfig(
    format="[%(levelname)s] %(asctime)s - %(name)s - %(message)s", level=logging.INFO
)

JACOCO_FILE = "target/site/jacoco/jacoco.xml"
METRIC = "INSTRUCTIONS"
PKG_PREFIX = "org.apache.shiro"
UT_COV_DIR = "ut_cov_data"

BASE_DIR = os.path.join(sys.path[0], "..")

debug = False


@dataclass
class CovRes:
    missed: int
    covered: int


@dataclass
class Location:
    package: str
    classes: str
    method: str


@dataclass
class CovRecord:
    loc: Location
    cov: dict[str, CovRes]


def collect_subprojects() -> list[str]:
    filename = os.path.join(BASE_DIR, "data/report_dir.json")
    with open(filename, "r", encoding="utf-8") as f:
        sub_projects = json.load(f)
    assert isinstance(sub_projects, list)
    assert isinstance(sub_projects[0], str)
    return sub_projects


def collect_test_methods() -> list[str]:
    filename = os.path.join(BASE_DIR, "data/test_methods.json")
    with open(filename, "r", encoding="utf-8") as f:
        test_methods = json.load(f)
    assert isinstance(test_methods, list)
    assert isinstance(test_methods[0], str)
    return test_methods


def extract_cov_report(file_path: str) -> list[CovRecord]:
    """
    filter the non-hit method, collect hitted flatten record
    """
    tree = ET.parse(file_path)
    root = tree.getroot()

    cov_records = []
    for package in root:
        assert package.tag == "package"
        for classes in package:
            assert classes.tag == "class"
            for method in classes:
                assert method.tag == "method"
                loc = Location(
                    package.attrib.get("name", ""),
                    classes.attrib.get("name", ""),
                    method.attrib.get("name", ""),
                )
                # construct CovRes
                cov = {}
                for counter in method:
                    assert counter.tag == "counter"
                    metric = counter.attrib.get("type", "")
                    missed = int(counter.attrib.get("missed", "0"))
                    covered = int(counter.attrib.get("covered", "0"))
                    cov[metric] = CovRes(missed, covered)
                cov_rec = CovRecord(loc, cov)
                cov_records.append(cov_rec)
    return cov_records


def calculate_coverage(records: list[CovRecord], metric: str) -> float:
    covered = 0
    missed = 0
    for rec in records:
        cov_res = rec.cov.get(metric)
        assert isinstance(cov_res, CovRes)
        covered += cov_res.covered
        missed += cov_res.missed
    return (covered) / (covered + missed)


def run_ut(test_method: str):
    global debug
    cmd = f"mvn clean test jacoco:report -Drat.skip=true -Dsurefire.failIfNoSpecifiedTests=false -Djacoco.skip=false -Dtest='{test_method}'"
    logging.info(f"command: {cmd}")
    err_log = "data/cmd_err.log"
    if debug:
        proc = subprocess.run(cmd.split(), text=True)
    else:
        proc = subprocess.run(
            cmd.split(), text=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
    ret = proc.returncode
    if ret != 0:
        with open(err_log, "w", encoding="utf-8") as f:
            f.write(proc.stdout + proc.stderr)
        logging.error(f"maven command failed: {cmd}")
        logging.error(f"refer to log file {err_log}")


def extract_method_name(method_name: str) -> Location:
    pat = r"^([\w.]+)\.(\w+)#(\w+)$"
    m = re.fullmatch(pat, method_name)
    assert m is not None
    return Location(m.group(1), m.group(2), m.group(3))


def is_project(dir: str) -> None:
    assert os.path.exists(os.path.join(dir, JACOCO_FILE))


def package_name2dir(package: str) -> str:
    return package.replace(".", "/")


def get_full_path(loc: Location) -> str:
    package_dir = loc.package.replace(".", "/")
    filename = loc.classes + ".java"

    for dirpath, dirs, filenames in os.walk("."):
        if not dirpath.endswith(package_dir):
            continue
        if not filename in filenames:
            continue
        return os.path.join(dirpath, filename)

    assert False


def check_valid_report_dir(report_dir: str, loc: Location) -> bool:
    file_path = os.path.join(report_dir, JACOCO_FILE)
    if not os.path.exists(file_path):
        return False

    tree = ET.parse(file_path)
    root = tree.getroot()

    flag = False
    for package in root:
        assert package.tag == "package"
        if not package.attrib.get("name", "") == loc.package:
            continue
        flag = True
        break
    return flag


def search_for_report_path(loc: Location, sub_projects: list[str]) -> str:
    """
    sub_project was defined by maven
    part of package name(prefix removed) does not always mapped to the sub project directory path
    solution: walk and find the full path of the test file, and then get sub project dir must be the prefix of it.
    candidates longest match
    required: contains jacoco report
    """
    global debug
    if debug:
        __import__("ipdb").set_trace()
    path = get_full_path(loc)
    report_dir = ""
    for dir in sub_projects:
        if not path.startswith(dir):
            continue
        if not check_valid_report_dir(dir, loc):
            continue
        if len(dir) > len(report_dir):
            report_dir = dir

    if len(report_dir) != 0:
        return os.path.join(report_dir, JACOCO_FILE)
    else:
        return ""


def get_report_path(test_method: str, sub_projects: list[str]) -> str:
    """
    get report xml  for corresponding UT, xml file resides in the corresponding subproject dir plus fixed target sub structure
    UT(method name) -> package -> sub project,
    sub project constitutes part of sub project
    """
    loc = extract_method_name(test_method)
    report_path = search_for_report_path(loc, sub_projects)
    return report_path


def persist_cov_data(test_method: str, cov_records: list[CovRes]):
    if not os.path.exists(UT_COV_DIR):
        os.mkdir(UT_COV_DIR)
    file_path = os.path.join(UT_COV_DIR, test_method)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(cov_records, f)


def run_and_collect_cov(test_method: str, sub_projects: list[str]) -> bool:
    """
    run and then collect data(path needed)
    """
    run_ut(test_method)
    report_path = get_report_path(test_method, sub_projects)
    # failed
    if len(report_path) == 0:
        return False
    cov_records = extract_cov_report(report_path)
    logging.info(f"cov_record sample: {cov_records[0]}")
    rate = calculate_coverage(cov_records, METRIC)
    logging.info(f"{METRIC} coverage rate: {rate:.2f}")
    return True


def main():
    global debug
    test_methods = collect_test_methods()
    sub_projects = collect_subprojects()
    succ = 0
    for ind, test_method in enumerate(test_methods):
        logging.info(f"running testmethod {ind+1}: {test_method}")
        flag = run_and_collect_cov(test_method, sub_projects)
        if not flag:
            logging.warning(f"running {ind+1} failed")
        else:
            succ += 1
        print()

        if debug:
            break
    logging.info(f"{succ} cases succeed among {len(test_method)} tries.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="run maven UT-coverage command and collect coverage informartion each"
    )
    parser.add_argument("-d", "--debug", help="debug mode", action="store_true")
    args = parser.parse_args()

    debug = args.debug
    main()
