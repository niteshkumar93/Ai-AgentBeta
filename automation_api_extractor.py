# automation_api_extractor.py

from typing import List, Dict
import xml.etree.ElementTree as ET


def extract_failed_tests_automation_api(uploaded_file) -> List[Dict]:
    """
    Extract failures from AutomationAPI XML reports.

    This is a placeholder implementation.
    Failure detection logic will be added later.
    """

    uploaded_file.seek(0)
    content = uploaded_file.read()

    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return []

    failures = []

    # --------------------------------------------
    # PLACEHOLDER STRATEGY
    # --------------------------------------------
    # Currently:
    # - Parses testcases
    # - Does NOT decide failure yet
    # - Returns empty list safely
    #
    # Later you can add:
    # - Status code validation
    # - API response checks
    # - Assertion failures
    # --------------------------------------------

    for testcase in root.findall(".//testcase"):
        name = testcase.attrib.get("name", "Unknown_API_Test")

        # Example placeholders (extend later)
        failure_node = testcase.find("failure") or testcase.find("error")
        if failure_node is None:
            continue

        failures.append({
            "testcase": name,
            "testcase_path": testcase.attrib.get("classname", ""),
            "error": failure_node.attrib.get("message", "API Failure"),
            "details": failure_node.text or "",
            "apiEndpoint": testcase.attrib.get("endpoint", "Unknown"),
            "httpMethod": testcase.attrib.get("method", "Unknown"),
            "statusCode": testcase.attrib.get("status", "Unknown"),
        })

    return failures
