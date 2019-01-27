import enum
import json
import logging
import os
import re
import sys
from configparser import NoSectionError
from importlib import import_module

from pytos.securechange.helpers import Secure_Change_Helper
from pytos.securechange.xml_objects.rest import Step_Field_Approve_Reject, Step_Field_Date, Step_Field_Multi_Access_Request, \
    Step_Field_Multiple_Selection, Step_Field_Checkbox, Step_Field_Multi_Group_Change, \
    Step_Field_Multi_Hyperlink, Step_Field_Multi_Network_Object, Ticket
from pytos.common.logging.definitions import THIRD_PARTY_LOGGER_NAME
from pytos.common.functions import Secure_Config_Parser
from pytos.common.rest_requests import POST_Request, PUT_Request, RESTAuthMethods
from common.secret_store import SecretDb

from .default_functions import Functions
from .placeholders import PlaceHolders

secret_helper = SecretDb()
conf = Secure_Config_Parser(config_file_path="/usr/local/orca/conf/custom.conf")
logger = logging.getLogger(THIRD_PARTY_LOGGER_NAME)

templates_root_dir = '/usr/local/orca/templates'
SECURE_STORE_KEY = 'rest_integration'
AUTH_TOKEN_KEY = 'auth_header_integration'
plugins_root_dir = conf.get(SECURE_STORE_KEY, 'plugins_root_dir', default_value='/usr/local/orca/plugins')


class Timing(enum.Enum):
    ENTER = 'enter'
    LEAVE = 'leave'


class RestClient:
    def __init__(self, hostname, username, password, proxy, protocol, auth_method, verify_ssl, header):
        self._protocol = protocol
        self._headers = header
        self._proxy_dict = proxy or {}
        self._login_data = {'username': username, 'password': password} if all((username, password)) else None
        self._hostname = hostname
        self.verify_ssl = verify_ssl
        self._auth_method = RESTAuthMethods.Basic if auth_method.lower() == 'basic' else RESTAuthMethods.Digest

    def post(self, endpoint, data, expected_status_codes):
        response = POST_Request(proxies=self._proxy_dict, hostname=self._hostname, uri=endpoint,
                            auth_method=self._auth_method, headers=self._headers, login_data=self._login_data,
                            body=json.dumps(data), protocol=self._protocol, verify_ssl=False,
                            expected_status_codes=expected_status_codes).response.content.decode('utf-8')
        return response if isinstance(response, str) else json.loads(response)

    def put(self, endpoint, data, expected_status_codes):
        response = PUT_Request(proxies=self._proxy_dict, hostname=self._hostname, uri=endpoint,
                           auth_method=self._auth_method, headers=self._headers, login_data=self._login_data,
                           body=json.dumps(data), protocol=self._protocol, verify_ssl=False,
                           expected_status_codes=expected_status_codes).response.content.decode('utf-8')
        return response if isinstance(response, str) else json.loads(response)


class JsonTemplateClient:
    def __init__(self, *, templates_root_dir=templates_root_dir, encoding='utf-8', specifier='#', **kwargs):
        """
        :param templates_root_dir: full path to the templates directory in SecureChange
        :param encoding:
        :param specifier: the sign that wrap the placeholder
        :param kwargs: should could contain attributes for the HTTP requests. can get the following arguments: hostname
                        protocol (https), verify_ssl [False|True], auth_mod [basic|digest], proxy {proxy_url}
        """
        self._templates_root_dir = templates_root_dir
        self._specifier = specifier
        self._encoding = encoding
        self._replacement_regex = re.compile(r'({0}.*?{0})'.format(self._specifier))
        self.kwargs = kwargs
        self.plugins = self._load_plugins()
        self.ticket = None
        self.sc_helper = kwargs.get('sc_helper', None)
        self.sc_username = kwargs.get('sc_username', None)

    @property
    def client(self):
        header = json.loads(self.kwargs.get('header', '{}').replace("'", '"'))
        if not header:
            header = {'Content-Type': 'application/json', 'Accept': 'application/json', 'charset': self._encoding}
        elif ('Content-Type' in header and 'application/json' != header['Content-Type']) or 'Content-Type' not in header:
            header['Content-Type'] = 'application/json'

        username = secret_helper.get_username(SECURE_STORE_KEY)
        password = secret_helper.get_password(SECURE_STORE_KEY)
        if not all((username, password)):
            auth_header_token = secret_helper.get_password(AUTH_TOKEN_KEY)
            if not auth_header_token:
                raise ValueError('Both username and password must be set, or authentication header must be provided')
            header.update({'Authorization': auth_header_token})
        try:
            hostname = self.kwargs['hostname']
        except KeyError:
            raise ValueError('Hostname is missing')

        params = {
            'username': username,
            'password': password,
            'hostname': hostname,
            'protocol': self.kwargs.get('protocol', 'https'),
            'verify_ssl': self.kwargs.get('verify_ssl', False),
            'auth_method': self.kwargs.get('auth_method', 'basic'),
            'proxy': self.kwargs.get('proxy', {}),
            'header': header
        }
        return RestClient(**params)

    def get_template(self, template_name):
        logger.debug("Loading template '{}' from '{}'".format(template_name, self._templates_root_dir))
        full_template_path = os.path.join(self._templates_root_dir, template_name)
        try:
            with open(full_template_path, encoding=self._encoding) as f:
                try:
                    return json.load(f)
                except ValueError as e:
                    raise IOError("Failed to load file as JSON. Error: '{}'".format(e))
        except OSError as error:
            raise IOError("Failed to read JSON template '{}'. Error: '{}'".format(template_name, error))

    def _get_fields_value(self, fields):
        values = []
        for field in fields:
            value = field.get_field_value() or ''
            if isinstance(field, Step_Field_Approve_Reject):
                status = 'Approved' if field.approved == "true" else 'Rejected'
                value = 'Status: {}; Reason: {}'.format(status, field.reason)
            elif isinstance(field, Step_Field_Checkbox):
                value = '[{}]'.format('X' if field.is_checked() else 'V')
            elif isinstance(field, Step_Field_Date):
                value = field.get_remedy_datetime()
            elif isinstance(field, (Step_Field_Multi_Access_Request, Step_Field_Multi_Group_Change)):
                value = field.to_pretty_str()
            elif isinstance(field, Step_Field_Multi_Hyperlink):
                value = '{}'.format(', '.join(o.url for o in field.hyperlinks))
            elif isinstance(field, (Step_Field_Multiple_Selection, Step_Field_Multi_Network_Object)):
                value = str(field)
            else:
                value = str(value)
            values.append(value)

        logger.debug("Returned values from fields: '{}'".format(values))
        return ', '.join(values)

    def _get_sc_field_name_from_placeholder(self, template_field_name):
        return template_field_name.strip(self._specifier)

    def _find_method(self, method_name):
        logger.debug("Looking for placeholder '{}' in functions".format(method_name))
        try:
            module = self.plugins['custom_functions']
            method = getattr(module, method_name)
        except (KeyError, AttributeError):
            logger.debug("The function name '{}' is not in custom functions, trying placeholder".format(method_name))
            method = getattr(PlaceHolders, method_name)
        return method

    def _apply_func_on_string(self, ticket, string, func):
        logger.info("In _apply_func_on_string. String: '{}', Func: '{}'".format(string, func))
        if func:
            try:
                method = self._find_method(func[0])
            except AttributeError as e:
                logger.error("Could not find the function '{}'".format(func[0]))
            else:
                string = method(ticket, string)
        return string

    def _find_replacement(self, ticket, step_name, placeholder, string_to_replace):
        ticket = self.sc_helper.get_ticket_by_id(ticket.id)
        ticket.sc_hostname = self.sc_helper.hostname
        f, *func = self._get_sc_field_name_from_placeholder(placeholder).split('|')
        try:
            method = self._find_method(f.lower())
        except AttributeError:
            logger.debug(
                "No placeholder function with place holder name '{}', trying field name".format(placeholder))
            logger.info("Getting field value for placeholder '{}'".format(placeholder))
            if step_name:
                logger.info("Parsing JSON template for step '{}'".format(step_name))
                step = ticket.get_step_by_name(step_name)
                fields = []
                for task in step.tasks:
                    fields.extend(task.get_field_list_by_name(f, case_sensitive=False))
                if fields:
                    replace_string = self._apply_func_on_string(ticket, self._get_fields_value(fields), func)
                    v = string_to_replace.replace(placeholder, replace_string)
                else:
                    logger.error("Step '{}' has no field '{}'".format(step_name, f))
                    v = placeholder
            else:
                logger.debug("Trying to find the field for placeholder '{}' in all of the steps".format(f))
                for step in ticket.steps[::-1]:
                    fields = []
                    for task in step.tasks:
                        fields.extend(task.get_field_list_by_name(f, case_sensitive=False))
                    if fields:
                        replace_string = self._apply_func_on_string(ticket, self._get_fields_value(fields), func)
                        v = string_to_replace.replace(placeholder, replace_string)
                        break
                else:
                    logger.error("Cannot find field name '{}' in ticket id '{}'".format(f, ticket.id))
                    v = placeholder
        else:
            replace_string = self._apply_func_on_string(ticket, str(method(ticket)), func)
            v = string_to_replace.replace(placeholder, replace_string)
        return v

    def _parse_json_template(self, ticket, step_name, json_data):
        """ Parse JSON file template
        :param ticket: SecureChange ticket object
        :param step_name:  SecureChange step name
        :param json_data: JSON data template
        :param callback: a function for the place holder
        :return: formatted JSON template
        """
        logger.info("Parsing JSON template")
        for k, v in json_data.items():
            if isinstance(v, dict):
                self._parse_json_template(ticket, step_name, json_data=v)
            elif isinstance(v, list):
                for item in v:
                    self._parse_json_template(ticket, step_name, json_data=item)
            elif isinstance(v, str):
                placeholders = self._replacement_regex.findall(v)
                for placeholder in placeholders:
                    v = self._find_replacement(ticket, step_name, placeholder, v)
                    json_data[k] = v
        return json_data

    def _update_response(self, response, response_template):
        logger.info("Updating response values in fields")
        if isinstance(response, dict) and isinstance(response_template, dict):
            for key in response:
                if key not in response_template:
                    logger.debug("Key '{}' has not been found in the response template, skipping".format(key))
                    continue
                placeholders = self._update_response(response[key], response_template[key])

                if not placeholders:
                    logger.warning("No placeholders have been found for key '{}'".format(key))
                else:
                    for placeholder in placeholders:
                        field_name = placeholder.strip(self._specifier)
                        step_task = self.ticket.get_last_task()
                        try:
                            field = step_task.get_field_list_by_name(field_name)[0]
                        except IndexError as e:
                            msg = "Field name '{}' could not be found in step name '{}'"
                            logger.error(msg.format(field_name, self.ticket.get_last_step().name))
                        else:
                            field.set_field_value(response[key])
                            try:
                                self.sc_helper.put_field(field)
                            except (ValueError, IOError) as error:
                                msg = "Failed to update field name '{}' in ticket id '{}', Error: '{}'"
                                logger.error(msg.format(field_name, self.ticket.id, error))
        else:
            placeholders = self._replacement_regex.findall(str(response_template))
            return placeholders

    def send(self, http_method, endpoint, body, expected_status_codes):
        """ Posting http request
        :param http_method: post or put
        :param endpoint: url path
        :param body: http payload
        :param expected_status_codes: http status code
        :return: None
        """
        logger.debug("Send JSON request: \nHTTP method: '{}'\n URL path: '{}'\n Body: '{}'".format(http_method, endpoint, body))
        method = getattr(self.client, http_method)
        response = method(
            endpoint=endpoint,
            data=body,
            expected_status_codes=expected_status_codes
        )
        logger.debug("Endpoint '{}' response: {}".format(endpoint, response))
        return response

    def reassign_task(self, ticket):
        reassigned = False
        ticket = self.sc_helper.get_ticket_by_id(ticket.id)
        last_task = ticket.get_last_step().get_last_task()
        if last_task.is_waiting_to_be_assigned():
            self.sc_helper.reassign_task_by_username(last_task, self.sc_username, 'Reassigned by integration script')
            ticket = self.sc_helper.get_ticket_by_id(ticket.id)
            reassigned = True
        return reassigned, ticket

    def reverse_reassigned_ticket(self, ticket, reassigned):
        last_task = ticket.get_last_step().get_last_task()
        if reassigned:
            ticket = self.sc_helper.get_ticket_by_id(ticket.id)
            step = ticket.get_last_step()
            new_last_task = step.get_last_task()
            if last_task.id == new_last_task.id:
                args = (ticket.workflow.id, step.name, new_last_task.name)
                participant = self.sc_helper.get_participants_by_task(*args)[0]
                self.sc_helper.reassign_task_by_username(new_last_task, participant, 'Reassigned by integration script')

    def pre_post_operations(self, ticket, func_names, **kwargs):
        if func_names:
            reassigned_status, ticket = self.reassign_task(ticket)
            last_method_status = None
            for func_name in func_names.replace(' ', '').split(','):
                logger.info("Executing function '{}'".format(func_name))
                try:
                    module = self.plugins['custom_functions']
                    method = getattr(module, func_name)
                    logger.debug("The method '{}' was found in custom functions".format(func_name))
                except (KeyError, AttributeError):
                    msg = "Cannot find the customized function '{}' in custom functions, looking in default functions"
                    logger.warning(msg.format(func_name))
                    try:
                        method = getattr(Functions, func_name)
                    except AttributeError:
                        logger.error("Cannot find post customized function '{}' in Functions".format(func_name))
                        return
                    logger.debug("The method '{}' was found in default functions".format(func_name))
                last_method_status = method(ticket, **kwargs)

            self.reverse_reassigned_ticket(ticket, reassigned_status)
            return last_method_status

    def run(self, ticket, **kwargs):
        """
        :param ticket: SecureChange ticket
        :param step_name:
        :param step_config: step configuration based on workflow and step name
        :param callback: A callback function for JSON place holder
        :return: None
        """
        self.ticket = ticket
        do_not_send_request = self.pre_post_operations(ticket, kwargs.get('pre', ''), **kwargs)
        try:
            template = self.get_template(kwargs['request_template_name'])
        except (IOError, KeyError) as e:
            logger.warning('Cannot get template')
        else:
            if not do_not_send_request:
                status_codes = kwargs.get('expected_status_codes', '200, 201, 204').split(',')
                expected_status_codes = [int(status) for status in status_codes if status]
                json_data = self._parse_json_template(ticket, kwargs.get('step_name', None), template)
                endpoint = kwargs['endpoint']
                response_template = kwargs.get('response_template_name', None)
                placeholders = self._replacement_regex.findall(endpoint)
                for placeholder in placeholders:
                    endpoint = self._find_replacement(ticket, kwargs.get('step_name', None), placeholder, endpoint)
                endpoints = endpoint.replace(' ', '').split(',')
                if len(endpoints) > 1:
                    response = self.send(kwargs['http_method'], endpoints[0], json_data, expected_status_codes)
                    url = kwargs['endpoint'].split(self._specifier)[0]
                    for id in endpoints[1:]:
                        new_endpoint = "{}{}".format(url, id)
                        response = self.send(kwargs['http_method'], new_endpoint, json_data, expected_status_codes)
                else:
                    response = self.send(kwargs['http_method'], endpoint, json_data, expected_status_codes)
                if response_template:
                    reassigned_status, ticket = self.reassign_task(ticket)
                    try:
                        response_json_template = self.get_template(response_template)
                    except IOError as e:
                        logger.error(e)
                    else:
                        self._update_response(response, response_json_template)
                    self.reverse_reassigned_ticket(ticket, reassigned_status)
            self.pre_post_operations(ticket, kwargs.get('post', ''), **kwargs)

    def handle_action(self, ticket, action):
        logger.info("In handle_action for ticket id '{}' and action '{}'".format(ticket.id, str(action)))
        if action == "CLOSE":
            last_step_task = ticket.get_last_step().get_last_task()
            if last_step_task.assignee == 'N/A' and last_step_task.status == 'N/A':
                action = "AUTOCLOSE"

        section_name = "integration {}-{}".format(ticket.workflow.name, action)
        try:
            action_config = conf.dict(section_name)
        except NoSectionError as error:
            logger.info("No section for action '{}'. Msg: '{}'".format(action, error))
            return None

        action_config['section_name'] = section_name
        self.run(ticket, **action_config)

    def handle_step(self, ticket, prev_step_name):
        logger.debug("In handle_step, Ticket id '{}' status is '{}'".format(ticket.id, ticket.status))

        if ticket.status.lower() == 'ticket closed':
            logger.debug("Ticket id '{}' status is '{}'".format(ticket.id, ticket.status))
            return

        if ticket.get_previous_step().name != prev_step_name:
            logger.debug("A skip step")
            return None

        previous_ticket_last_step_name = ticket.get_last_step().name
        ticket = self.sc_helper.get_ticket_by_id(ticket.id, predicate=Ticket.has_no_pending_tasks)
        section_name_template = 'integration {}-{}'
        try:
            current_step_name = ticket.get_current_step().name
        except IndexError:
            logger.warning("No current step name")
        else:
            if previous_ticket_last_step_name != current_step_name:
                msg = "Skipping, the current step name is: '{}', the script runs from step name: '{}'"
                logger.debug(msg.format(current_step_name, previous_ticket_last_step_name))
                return None
            logger.debug("Getting configuration for current step '{}'".format(current_step_name))
            section_name = section_name_template.format(ticket.workflow.name, current_step_name)
            try:
                current_step_config = conf.dict(section_name)
                logger.debug("Read current step configuration: '{}'".format(current_step_config))
            except NoSectionError as i:
                logger.info(i)
            else:
                if current_step_config.get('timing', Timing.ENTER.value).lower() == Timing.ENTER.value:
                    current_step_config['section_name'] = section_name
                    self.run(ticket, **current_step_config)

        try:
            previous_step_name = ticket.get_previous_step().name
        except IndexError:
            logger.warning("No previous step name")
        else:
            logger.debug("Getting configuration for previous step '{}'".format(previous_step_name))
            section_name = section_name_template.format(ticket.workflow.name, previous_step_name)
            try:
                prev_step_config = conf.dict(section_name)
            except NoSectionError as e:
                logger.info(e)
            else:
                if prev_step_config.get('timing', '').lower() == Timing.LEAVE.value:
                    prev_step_config['section_name'] = section_name
                    self.run(ticket, **prev_step_config)

    @staticmethod
    def _load_plugins():
        plugins = {}
        py_search = re.compile('custom_functions.py$', re.IGNORECASE)
        try:
            plugin_files = filter(py_search.search, os.listdir(plugins_root_dir))
        except FileNotFoundError as e:
            logger.info("No plugins directory was found. Error: '{}'".format(e))
        else:
            plugin_string_list = list(map(lambda fp: os.path.splitext(fp)[0], plugin_files))
            sys.path.append(plugins_root_dir)
            logger.info("Plugins to import: '{}'".format(plugin_string_list))
            for plugin_string in plugin_string_list:
                try:
                    module = import_module(plugin_string)
                    plugins.update({module.__name__: module})
                except ImportError as e:
                    logger.error(e)

            logger.info("Imported plugins: '{}'".format(plugins))
        return plugins

    @classmethod
    def from_conf(cls, sc_helper=None, sc_username=None):
        try:
            conf_data = conf.dict('integration setup')
        except NoSectionError as e:
            raise ValueError(str(e))
        conf_data['sc_helper'] = sc_helper
        conf_data['sc_username'] = sc_username
        logger.debug("Read setup configuration: '{}'".format(conf_data))
        return cls(**conf_data)
