import logging

from pytos.securechange.helpers import Secure_Change_Helper
from pytos.securechange.xml_objects.restapi.step.access_request.accessrequest import Any_Access_Request_Device
from pytos.common.functions import Secure_Config_Parser
from pytos.common.definitions.xml_tags import Attributes
from pytos.common.logging.definitions import THIRD_PARTY_LOGGER_NAME
from common.secret_store import SecretDb

conf = Secure_Config_Parser(config_file_path="/usr/local/orca/conf/custom.conf")
logger = logging.getLogger(THIRD_PARTY_LOGGER_NAME)
secret_helper = SecretDb()
sc_cred = (secret_helper.get_username('securechangeworkflow'), secret_helper.get_password('securechangeworkflow'))
sc_host = conf.get("securechange", "host")
sc_helper = Secure_Change_Helper(sc_host, sc_cred)


def firewall_list(ticket):
    for step in ticket.steps[::-1]:
        task = step.get_last_task()
        try:
            field = task.get_field_list_by_type(Attributes.FIELD_TYPE_MULTI_ACCESS_REQUEST)[0]
        except IndexError:
            continue

        targets = {}
        for ar in field.access_requests:
            for t in ar.targets.get_contents():
                if isinstance(t, Any_Access_Request_Device):
                    return 'Any'
                else:
                    if hasattr(t, 'management_name') and t.management_name != t.object_name:
                        target = "{}/{}".format(t.management_name, t.object_name)
                    else:
                        target = t.object_name
                    targets.setdefault(ar.order, []).append(target)
        return str(targets)
    else:
        msg = "The approve-reject status has not been found in all of the ticket id '{}' steps"
        logger.warning(msg.format(ticket.id))


def assignee(ticket):
    assignee = ticket.get_last_step().get_last_task().assignee
    if not assignee or assignee == 'N/A':
        for step in ticket.steps[::-1]:
            task = step.get_last_task()
            if task.assignee == 'N/A':
                continue
            return task.assignee
    return assignee


def redo_reason(ticket):
    try:
        return ticket.comments[-1].content
    except IndexError:
        logger.warning('No comment in the ticket for redo placeholder')
        return ''


def reject_reason(ticket):
    try:
        return ticket.comments[-1].content
    except IndexError:
        logger.warning('No comment in the ticket for redo placeholder')
        return ''


def ticket_start_time(ticket):
    submitted_time = sc_helper.get_ticket_history_by_id(ticket.id)[0].as_time_obj()
    return submitted_time.strftime("%Y/%m/%d %H:%M:%S")


def ticket_end_time(ticket):
    close_time = sc_helper.get_ticket_history_by_id(ticket.id)[-1].as_time_obj()
    return close_time.strftime("%Y/%m/%d %H:%M:%S")


def automatic_step_failure_reason(ticket):
    histories = sc_helper.get_ticket_history_by_id(ticket.id)
    for history in histories[::-1]:
        if 'Automatic step failed' in history.description:
            return history.description
    return ''


def step_handler(ticket):
    try:
        step = ticket.get_current_step()
    except KeyError:
        logger.warning("Cannot get assignee from current step for ticket id '{}'".format(ticket.id))
        return ''
    else:
        return ', '.join(task.assignee for task in step.tasks)


def step_name(ticket):
    try:
        step = ticket.get_current_step()
    except KeyError:
        logger.warning("Cannot get step name from current step for ticket id '{}'".format(ticket.id))
        return ''
    return step.name


def ticket_link(ticket):
    link_template = "https://{}/securechangeworkflow/pages/myRequest/myRequestsMain.seam?ticketId={}"
    ticket_link = link_template.format(ticket.sc_hostname, ticket.id)
    return ticket_link