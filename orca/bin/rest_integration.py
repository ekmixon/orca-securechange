#!/usr/local/orca/python/bin/python3

import argparse
import logging
import shlex
import sys

from pytos.common.logging.logger import setup_loggers
from pytos.common.logging.definitions import COMMON_LOGGER_NAME
from pytos.common.functions.config import Secure_Config_Parser
from pytos.securechange.helpers import Secure_Change_Helper, Secure_Change_API_Handler

sys.path.append('/usr/local/orca/lib')
from common.secret_store import SecretDb
from common.third_party.generic.rest.template_client import JsonTemplateClient

secret_helper = SecretDb()
logger = logging.getLogger(COMMON_LOGGER_NAME)
conf = Secure_Config_Parser(config_file_path="/usr/local/orca/conf/custom.conf")
sc_cred = (secret_helper.get_username('securechange'), secret_helper.get_password('securechange'))
sc_host = conf.get("securechange", "host")
sc_helper = Secure_Change_Helper(sc_host, sc_cred)


def get_cli_args():
    parser = argparse.ArgumentParser('')
    parser.add_argument('--debug', action='store_true', help='Print out logging information to STDOUT.')
    return parser.parse_args(shlex.split(' '.join(sys.argv[1:])))


def main():
    cli_args = get_cli_args()
    setup_loggers(conf.dict('log_levels'), log_to_stdout=cli_args.debug,
                  log_dir_path="/var/log", log_file="ps_orca_logger.log")

    logger.info("Reading ticket info")
    try:
        ticket_info = sc_helper.read_ticket_info()
    except ValueError:
        logger.info("Testing")
        sys.exit(0)

    logger.info(f'Script is called for ticket id "{ticket_info.id}"')
    try:
        template_client = JsonTemplateClient.from_conf(sc_helper, sc_cred[0])
    except (NameError, ValueError) as error:
        logger.error(error)
        sys.exit(1)

    logger.info("before ticket")
    pre_step_name = ticket_info.current_stage_name
    ticket = sc_helper.get_ticket_by_id(ticket_info.id)
    logger.info("")
    logger.info("Ticket info")
    logger.info(ticket_info)
    logger.info("")
    ticket_handler = Secure_Change_API_Handler(ticket, ticket_info, sc_helper)
    logger.info("")
    logger.info(ticket_handler)
    logger.info("")
    triggers_for_step = ('ADVANCE', 'CREATE', 'RESUBMIT')
    ticket_handler.register_action(triggers_for_step, template_client.handle_step, ticket, pre_step_name)
    trigger_for_action = ('CLOSE', 'CANCEL', 'REJECT', 'REDO', 'REOPEN', 'PRE_ASSIGNMENT_SCRIPT', 'AUTOMATION_FAILED')
    func_args = (ticket, ticket_handler._get_trigger_action())
    ticket_handler.register_action(trigger_for_action, template_client.handle_action, *func_args)

    logger.info('before run')
    ticket_handler.run()
    sys.exit(0)


if __name__ == '__main__':
    main()

