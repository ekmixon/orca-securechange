import logging

from pytos.common.definitions.xml_tags import Attributes
from pytos.common.logging.definitions import THIRD_PARTY_LOGGER_NAME

logger = logging.getLogger(THIRD_PARTY_LOGGER_NAME)


def verifier_status(ticket):
    logger.debug(
        f"Validating if ARs on ticket id '{ticket.id}' are already implemented"
    )

    for step in ticket.steps[::-1]:
        task = step.get_last_task()
        try:
            ar_field = task.get_field_list_by_type(Attributes.FIELD_TYPE_MULTI_ACCESS_REQUEST)[0]
        except IndexError:
            continue

        verified = [ar.verifier_result.is_implemented() if ar.verifier_result else False for ar in
                    ar_field.access_requests]
        return "Fully implemented" if all(verified) else "Not implemented"
    logger.warning("No verifier status has been found in all of the ticket steps")
    return "Not Implemented"