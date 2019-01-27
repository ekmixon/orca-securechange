from datetime import datetime
from .modules import designer, risk, ticket_data, fields, verifier


class PlaceHolders:
    @staticmethod
    def current_time(ticket):
        return str(datetime.now().replace(microsecond=0))

    @staticmethod
    def date_only(ticket):
        return str(str(datetime.now().date()))

    @staticmethod
    def firewall_list(ticket):
        return ticket_data.firewall_list(ticket)

    @staticmethod
    def ticket_id(ticket):
        return ticket.id

    @staticmethod
    def ticket_subject(ticket):
        return ticket.subject

    @staticmethod
    def workflow_name(ticket):
        return ticket.workflow.name

    @staticmethod
    def ticket_requester(ticket):
        return ticket.requester

    @staticmethod
    def assignee(ticket):
        return ticket_data.assignee(ticket)

    @staticmethod
    def ticket_link(ticket):
        return ticket_data.ticket_link(ticket)

    @staticmethod
    def redo_reason(ticket):
        return ticket_data.redo_reason(ticket)

    @staticmethod
    def reject_reason(ticket):
        return ticket_data.reject_reason(ticket)

    @staticmethod
    def approve_reject_reason(ticket):
        return fields.approve_reject_reason(ticket)

    @staticmethod
    def approve_reject_status(ticket):
        return fields.approve_reject_status(ticket)

    @staticmethod
    def selected_plus_options(ticket):
        return fields.selected_plus_options(ticket)

    @staticmethod
    def step_handler(ticket):
        return ticket_data.step_handler(ticket)

    @staticmethod
    def step_name(ticket):
        return ticket_data.step_name(ticket)

    @staticmethod
    def risk_status(ticket):
        return risk.risk_status(ticket)

    @staticmethod
    def risk_results(ticket):
        return risk.risk_results(ticket)

    @staticmethod
    def verifier_status(ticket):
        return verifier.verifier_status(ticket)

    @staticmethod
    def ticket_start_time(ticket):
        return ticket_data.ticket_start_time(ticket)

    @staticmethod
    def ticket_end_time(ticket):
        return ticket_data.ticket_end_time(ticket)

    @staticmethod
    def designer_commands(ticket):
        return designer.designer_commands(ticket)

    @staticmethod
    def designer_status(ticket):
        return designer.designer_status(ticket)

    @staticmethod
    def designer_results_json(ticket):
        return designer.designer_results_json(ticket)

    @staticmethod
    def automatic_step_failure_reason(ticket):
        return ticket_data.automatic_step_failure_reason(ticket)