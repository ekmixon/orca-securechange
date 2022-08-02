import logging

from pytos.securechange.helpers import Secure_Change_Helper
from pytos.securechange.xml_objects.rest import Step_Field_Approve_Reject, Step_Field_Text, Step_Field_Text_Area
from pytos.common.functions import Secure_Config_Parser
from pytos.common.definitions.xml_tags import Attributes
from pytos.common.logging.definitions import THIRD_PARTY_LOGGER_NAME
from .placeholders import PlaceHolders
from common.secret_store import SecretDb

secret_helper = SecretDb()
conf = Secure_Config_Parser(config_file_path="/usr/local/orca/conf/custom.conf")
sc_cred = (secret_helper.get_username('securechangeworkflow'), secret_helper.get_password('securechangeworkflow'))
sc_host = conf.get("securechange", "host")
sc_helper = Secure_Change_Helper(sc_host, sc_cred)
logger = logging.getLogger(THIRD_PARTY_LOGGER_NAME)


def get_first_field_in_ticket(ticket, **kwargs):
    for step in ticket.steps[::-1]:
        task = step.get_last_task()
        try:
            field = task.get_field_list_by_type(kwargs['field_type'])[0]
        except IndexError:
            continue
        return field
    return None


def approve_reject_on_severity(ticket, severity):
    logger.debug(f"In approve_reject_on_high for ticket id '{ticket.id}'")
    current_task = ticket.get_current_task()
    approve_field = current_task.get_field_list_by_type(Attributes.FIELD_TYPE_APPROVE_REJECT)[0]
    if multi_access_request_field := get_first_field_in_ticket(
        ticket, field_type=Attributes.FIELD_TYPE_MULTI_ACCESS_REQUEST
    ):
        for ar in multi_access_request_field.access_requests:
            for security_policy_violation in ar.risk_analysis_result.security_policy_violations:
                if security_policy_violation.severity.lower() == severity.lower():
                    approve_field.approved = False
                    msg = "The ticket has been rejected by the script. The severity was {}."
                    approve_field.reason = msg.format(security_policy_violation.severity)
                    break
            else:
                continue
            break
        else:
            approve_field.approved = True
            approve_field.reason = "The ticket has been approved by the script"
        sc_helper.put_field(approve_field)


class Functions:
    @staticmethod
    def advance(ticket, **kwargs):
        logger.debug(f"Execute trigger advance for ticket id '{ticket.id}'")
        current_task = ticket.get_current_task()
        logger.debug(f"Advancing step name '{ticket.get_current_step().name}'")
        mandatory_fields_status = False
        for field in current_task.fields:
            if isinstance(field, Step_Field_Approve_Reject) and not field.approved and not field.reason :
                field.approve("Approved by integration script")
                mandatory_fields_status = True
            if isinstance(field, (Step_Field_Text, Step_Field_Text_Area)) and not field.get_field_value():
                field.set_field_value("Set by integration script")
                mandatory_fields_status = True

        if not mandatory_fields_status:
            current_task.remove_all_fields()
        current_task.mark_as_done()
        try:
            sc_helper.put_task(current_task)
        except (IOError, ValueError) as e:
            raise IOError(f"Failed to advance step. Error was: '{e}'")

    @classmethod
    def advance_if_fully_implemented(cls, ticket, **kwargs):
        logger.debug(
            f"Execute trigger advance if fully implemented for ticket id '{ticket.id}'"
        )

        if multi_access_request_field := get_first_field_in_ticket(
            ticket, field_type=Attributes.FIELD_TYPE_MULTI_ACCESS_REQUEST
        ):
            try:
                designer_results = multi_access_request_field.get_designer_results(
                    conf.get_username("securechange"),
                    conf.get_password("securechange")
                )
            except IOError as e:
                logger.error("Failed to get designer results.")
                logger.error(f"Error: '{e}'")
            else:
                if designer_results.is_implemented():
                    cls.advance(ticket, **kwargs)

    @classmethod
    def approve_reject(cls, ticket, **kwargs):
        logger.debug(f"In approve_reject for ticket id '{ticket.id}'")
        current_task = ticket.get_current_task()
        approve_field = current_task.get_field_list_by_type(Attributes.FIELD_TYPE_APPROVE_REJECT)[0]
        if PlaceHolders.risk_status(ticket).lower() == 'yes':
            approve_field.approved = False
            approve_field.reason = "The ticket has been rejected by the script"
        else:
            approve_field.approved = True
            approve_field.reason = "The ticket has been approved by the script"

        sc_helper.put_field(approve_field)

    @classmethod
    def approve_reject_on_critical(cls, ticket, **kwargs):
        logger.debug(f"In approve_reject_on_high for ticket id '{ticket.id}'")
        approve_reject_on_severity(ticket, 'critical')

    @classmethod
    def approve_reject_on_high(cls, ticket, **kwargs):
        logger.debug(f"In approve_reject_on_high for ticket id '{ticket.id}'")
        approve_reject_on_severity(ticket, 'high')

    @classmethod
    def cancel_ticket(cls, ticket, **kwargs):
        logger.info(f"Canceling ticket id '{ticket.id}'")
        try:
            sc_helper.cancel_ticket(ticket.id)
        except (ValueError, IOError) as e:
            logger.error(e)

    @staticmethod
    def do_not_send_request_if_the_previous_step_skipped(ticket, **kwargs):
        logger.info("Checking if previous step skipped")
        try:
            return ticket.get_previous_step().is_skipped()
        except (ValueError, IOError, KeyError) as e:
            logger.error(f"Failed to check if previous step skipped. Error: '{e}'")

    @staticmethod
    def do_not_send_request_if_skip_checkbox_checked(ticket, **kwargs):
        logger.info("Find if the skipped checkbox was selected")
        try:
            previous_step_task = ticket.get_previous_step().get_last_task()
            skipped_checkbox_field = previous_step_task.get_field_list_by_name('skip', case_sensitive=False)[0]
            return skipped_checkbox_field.is_checked()
        except (ValueError, IOError, KeyError) as e:
            logger.error(
                f"Failed to check if the checkbox field in the previous step was skipped. Error: '{e}'"
            )

