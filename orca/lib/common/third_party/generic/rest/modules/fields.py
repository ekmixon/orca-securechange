import logging

from pytos.common.definitions.xml_tags import Attributes
from pytos.common.logging.definitions import THIRD_PARTY_LOGGER_NAME

logger = logging.getLogger(THIRD_PARTY_LOGGER_NAME)


def approve_reject_reason(ticket):
    for step in ticket.steps[::-1]:
        task = step.get_last_task()
        try:
            approve_reject_field = task.get_field_list_by_type(Attributes.FIELD_TYPE_APPROVE_REJECT)[0]
        except IndexError:
            continue
        return approve_reject_field.reason
    else:
        msg = "The approve-reject status has not been found in all of the ticket id '{}' steps"
        logger.warning(msg.format(ticket.id))


def approve_reject_status(ticket):
    for step in ticket.steps[::-1]:
        task = step.get_last_task()
        try:
            approve_reject_field = task.get_field_list_by_type(Attributes.FIELD_TYPE_APPROVE_REJECT)[0]
        except IndexError:
            continue
        status = 'Approved' if approve_reject_field.approved == "true" else 'Rejected'
        return status
    else:
        msg = "The approve-reject status has not been found in all of the ticket id '{}' steps"
        logger.warning(msg.format(ticket.id))


def selected_plus_options(ticket):
    for step in ticket.steps[::-1]:
        task = step.get_last_task()
        try:
            field = task.get_field_list_by_type(Attributes.FIELD_TYPE_DROP_DOWN_LIST)[0]
        except IndexError:
            continue
        return "{} selected from [{}]".format(field.selection, ', '.join(o.value for o in field.options))
    else:
        msg = "The drop down field has not been found in all of the ticket id '{}' steps"
        logger.warning(msg.format(ticket.id))