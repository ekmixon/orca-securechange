import logging
from copy import deepcopy

from pytos.common.definitions.xml_tags import Attributes
from pytos.common.logging.definitions import THIRD_PARTY_LOGGER_NAME
from pytos.securechange.xml_objects.restapi.step.access_request.risk import Violation_Any_Source, Violation_Any_Destination, \
    Violation_Any_Service, Violation_Not_Allowed_Group_Member_service_Object, \
    Violation_Allowed_Group_Member_service_Object, Violation_Group_Destination, Violation_Group_Source, \
    RestrictedCellViolation, BlockedOnlyCellViolation


logger = logging.getLogger(THIRD_PARTY_LOGGER_NAME)
NO_RISK = "no risk"


def risk_status(ticket):
    for step in ticket.steps[::-1]:
        task = step.get_last_task()
        try:
            multi_access_request_field = task.get_field_list_by_type(Attributes.FIELD_TYPE_MULTI_ACCESS_REQUEST)[0]
        except IndexError:
            continue
        for ar in multi_access_request_field.access_requests:
            if ar.risk_analysis_result.has_risk():
                return "YES"
        return "NO"
    else:
        logger.warning("Risk status has not been found in all of the ticket steps")


def risk_results(ticket):
    def get_string_of_resources(resources):
        items = []
        violations_objects = (Violation_Any_Source, Violation_Any_Destination, Violation_Any_Service)
        violation_group_objects = (Violation_Not_Allowed_Group_Member_service_Object,
                                   Violation_Allowed_Group_Member_service_Object, Violation_Group_Source,
                                   Violation_Group_Destination)
        for resource in resources:
            if isinstance(resource, violations_objects) or resource is None:
                items.append("Any")
            elif isinstance(resource, violation_group_objects):
                items.append(resource.group_member_path)
            else:
                items.append(resource.name)
        return ', '.join(items)

    risk_analysis_results_template = {
        "severity": None,
        "violations": {
            "sources": None,
            "destinations": None,
            "violating_services": None
        },
        "security_requirements": {
            "policy": None,
            "from_zone": None,
            "to_zone": None,
            "allowed_services": None
        }
    }
    risk_results_per_ar = {}
    for step in ticket.steps[::-1]:
        task = step.get_last_task()
        try:
            multi_access_request_field = task.get_field_list_by_type(Attributes.FIELD_TYPE_MULTI_ACCESS_REQUEST)[0]
        except IndexError:
            continue

        for ar in multi_access_request_field.access_requests:
            if NO_RISK == ar.risk_analysis_result.status.lower().strip():
                risk_results_per_ar[ar.order] = NO_RISK
                continue
            ar_violation_list = []
            for violation in ar.risk_analysis_result.security_policy_violations:
                violation_dict = deepcopy(risk_analysis_results_template)
                matrix = violation.matrix_cell_violation
                allowed_services, violating_services = "Block All", "All services"
                if isinstance(matrix, (RestrictedCellViolation,)):
                    allowed_services = get_string_of_resources(matrix.allowed_services)
                    violating_services = get_string_of_resources(matrix.not_allowed_services)
                elif isinstance(matrix, (BlockedOnlyCellViolation,)):
                    allowed_services = get_string_of_resources(matrix.blocked_services)
                    violating_services = get_string_of_resources(matrix.not_blocked_services)

                violation_dict['severity'] = violation.severity
                violation_dict['violations']['sources'] = get_string_of_resources(matrix.sources)
                violation_dict['violations']['destinations'] = get_string_of_resources(matrix.destinations)
                violation_dict['violations']['violating_services'] = violating_services
                violation_dict["security_requirements"]["policy"] = violation.security_zone_matrix.name
                violation_dict["security_requirements"]["from_zone"] = matrix.from_zone
                violation_dict["security_requirements"]["to_zone"] = matrix.to_zone
                violation_dict["security_requirements"]["allowed_services"] = allowed_services
                ar_violation_list.append(violation_dict)
            risk_results_per_ar[ar.order] = ar_violation_list
        return risk_results_per_ar
    else:
        logger.warning("No risk status has been found in all of the ticket steps")
        return risk_results_per_ar