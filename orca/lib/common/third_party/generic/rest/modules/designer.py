import logging


from pytos.common.functions import Secure_Config_Parser
from pytos.common.definitions.xml_tags import Attributes
from pytos.common.logging.definitions import THIRD_PARTY_LOGGER_NAME
from pytos.securechange.xml_objects.restapi.step.access_request.designer import DesignerResult
from common.secret_store import SecretDb

conf = Secure_Config_Parser(config_file_path="/usr/local/orca/conf/custom.conf")
logger = logging.getLogger(THIRD_PARTY_LOGGER_NAME)
secret_helper = SecretDb()


def designer_commands(ticket):
    for step in ticket.steps[::-1]:
        task = step.get_last_task()
        try:
            multi_ar_field = task.get_field_list_by_type(Attributes.FIELD_TYPE_MULTI_ACCESS_REQUEST)[0]
        except IndexError:
            continue
        sc_cred = (
            secret_helper.get_username('securechangeworkflow'),
            secret_helper.get_password('securechangeworkflow')
        )
        designer_results = multi_ar_field.get_designer_results(*sc_cred)
        if not designer_results:
            return ''
        device_to_commands = {}
        for device_suggestion in designer_results.device_suggestion:
            try:
                commands = multi_ar_field.get_designer_commands(device_suggestion.management_id, *sc_cred)
            except IOError as e:
                logger.info(e)
                continue
            device_to_commands[device_suggestion.management_id] = str(commands)
        if device_to_commands:
            return str(device_to_commands)


def designer_status(ticket):
    for step in ticket.steps[::-1]:
        task = step.get_last_task()
        try:
            multi_ar_field = task.get_field_list_by_type(Attributes.FIELD_TYPE_MULTI_ACCESS_REQUEST)[0]
        except IndexError:
            continue

        if hasattr(multi_ar_field, 'designer_result'):
            is_failed = multi_ar_field.designer_result.status == DesignerResult.DESIGNER_CANNOT_COMPUTE
            return "Error: Problem with Designer" if is_failed else ""
    return ''


def designer_results_json(ticket):
    for step in ticket.steps[::-1]:
        task = step.get_last_task()
        try:
            multi_ar_field = task.get_field_list_by_type(Attributes.FIELD_TYPE_MULTI_ACCESS_REQUEST)[0]
        except IndexError:
            continue

        if hasattr(multi_ar_field, 'designer_result') and \
                        multi_ar_field.designer_result.status != DesignerResult.DESIGNER_CANNOT_COMPUTE:
            sc_cred = (
                secret_helper.get_username('securechangeworkflow'),
                secret_helper.get_password('securechangeworkflow')
            )
            if response := multi_ar_field.get_designer_results(
                *sc_cred, as_json=True
            ):
                return response.decode()
    return ''