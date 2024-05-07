"""
run each unit test and collect its coverage information
"""

import json
import logging
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass

logging.basicConfig(level=logging.INFO)

JACOCO_FILE = "target/site/jacoco/jacoco.xml"
METRIC = "INSTRUCTIONS"


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
    filename = "data/sub_projects.json"
    with open(filename, "r", encoding="utf-8") as f:
        sub_projects = json.load(f)
    assert isinstance(sub_projects, list)
    assert isinstance(sub_projects[0], str)
    return sub_projects


def collect_test_methods() -> list[str]:
    filename = "data/test_methods.json"
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
    cmd = f"mvn test jacoco:report -Drat.skip=true -Dsurefire.failIfNoSpecifiedTests=false -Djacoco.skip=false -Dtest='{test_method}'"
    proc = subprocess.Popen(cmd, shell=True)
    ret = proc.wait()
    assert ret == 0


def get_report_path(test_method: str, sub_projects: list[str]) -> str:
    pass


def run_cov(test_method: str, sub_projects: list[str]) -> None:
    """
    run and then collect data(path needed)
    """
    run_ut(test_method)
    report_path = ""
    cov_records = extract_cov_report(report_path)
    logging.info(f"cov_record sample: {cov_records[0]}")
    rate = calculate_coverage(cov_records, METRIC)
    logging.info(f"{METRIC} coverage rate: {rate:.2f}")


def main():
    test_methods = collect_test_methods()
    sub_projects = collect_subprojects()
    for test_method in test_methods:
        run_cov(test_method, sub_projects)


if __name__ == "__main__":
    main()
