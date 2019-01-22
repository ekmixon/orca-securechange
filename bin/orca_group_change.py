#!/opt/tufin/securitysuite/ps/python/bin/python3

import argparse
import enum
import io
import ipaddress
import logging
import socket
import struct
import sys
import time
import traceback
import daemonize
import json

sys.path.append("/opt/tufin/securitysuite/ps/lib")
from Secure_Common import REST_Exceptions
from Secure_Track.Helpers import Secure_Track_Helper
from Secure_Common.Logging.Logger import setup_loggers
from Secure_Common.Logging.Defines import COMMON_LOGGER_NAME
from Secure_Common.REST_Functions.Config import Secure_Config_Parser
from Secure_Change.Helpers import Secure_Change_Helper
from Secure_Common.REST_Defines.XML_Tags import Attributes
from Secure_Common.REST_Requests import POST_Request, GET_Request
from Secure_Track.XML_Objects.REST.Rules import Group_Network_Object, Subnet_Network_Object, Host_Network_Object, \
    Range_Network_Object
from Secure_Change.XML_Objects.REST import Ticket, Group_Change_Node, Elements, XML_List, Group_Change_Member_Object, \
    TYPE_HOST

logger = logging.getLogger(COMMON_LOGGER_NAME)
conf = Secure_Config_Parser()
sc_helper = Secure_Change_Helper.from_secure_config_parser(conf)
st_helper = Secure_Track_Helper.from_secure_config_parser(conf)
orca_host = conf.get("orca_integration", "host")
ticket_template_path = conf.get("orca_integration", "change_group_ticket_template_path")
group_path_url = conf.get("orca_integration", "group_path_url")
orca_update_task_url = conf.get("orca_integration", "orca_update_task_url")

PID_FILE = '/var/run/ps/orca_sync.pid'
CHANGE_ADDED_STATUS = "ADDED"
CHANGE_CREATE_STATUS = "CREATE"
NOT_CHANGE_STATUS = "NOT_CHANGED"
SUPPORTED_MODELS = ['Panorama_device_group', 'cp_domain_r80plus', 'asa', 'junos', 'fmg_adom']

# TODO: Should be taken from config
ORCA_TOKEN = "Bearer 964b1025-ba64-455f-b751-07ed40dbdef0"
DEFAULT_POOL_INTERVAL = 60


class OrcaStatuses(enum.Enum):
    Pending = 0
    Running = 1
    Succeeded = 2
    Failed = 3


class OrcaClient:
    def __init__(self, host, url_path, username=None, password=None):
        self.host = host
        self.url_path = url_path
        self.login_data = self.get_login_data(username, password)
        self.headers = {"Content-Type": "application/json",
                        'Authorization': ORCA_TOKEN}

    def get_login_data(self, username, password):
        login_data = {'username': username, 'password': password} if all((username, password)) else None
        return login_data

    def get_group_memebers(self):
        logger.debug("Getting group name and members")
        try:
            response = GET_Request(self.host, self.url_path, headers=self.headers,
                                   expected_status_codes=200, verify_ssl=False,
                                   login_data=self.login_data).response.content.decode('utf-8')
        except (ValueError, IOError, REST_Exceptions.REST_HTTP_Exception) as error:
            msg = "Failed to get new tickets from orca. Error: {}".format(error)
            logger.error(msg)
            raise IOError
        logger.debug("Got the response: {}".format(response))
        return json.loads(response)

    def update_orca_ticket(self, uuid, ticket_id, status, msg, group_name, url_path=None, sc_url='N/A'):
        if url_path is None:
            url_path = self.url_path
        try:
            body = {
                "taskId": uuid,
                "ticketId": str(ticket_id),
                "status": status,
                "message": msg,
                "name": group_name,
                "url": sc_url
            }
            response = POST_Request(self.host, url_path, headers=self.headers, body=json.dumps(body),
                                    expected_status_codes=[200, 201, 204], verify_ssl=False,
                                    login_data=self.login_data).response.content.decode('utf-8')
            logger.debug("Got response: {}".format(response))
        except (ValueError, IOError, REST_Exceptions.REST_HTTP_Exception) as error:
            msg = "Failed to update ticket {} on Orca as updated. Error: {}".format(uuid, error)
            logger.error(msg)
            raise IOError


def get_cli_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("-s", "--sleep-time", type=int, help="Sleep time between fetching emails.",
                        default=DEFAULT_POOL_INTERVAL)
    parser.add_argument("-n", "--no-daemonize", action="store_true", default=False,
                        help="Don't run the script in the background.")
    parser.add_argument("--debug", action="store_true", help="Print out logging information to STDOUT.")
    args = parser.parse_args()
    return args


def valid_device_ids(d_tree):
    device_ids = []
    for d in d_tree:
        if d._is_virtual:
            continue
        if d.has_children() and not d._parent:
            device_ids.extend(valid_device_ids(d._children))
        else:
            if d.model in SUPPORTED_MODELS:
                device_ids.append(d.id)
    return device_ids


def get_group_objects_by_name(group_name, device_ids):
    logger.info("Getting all groups from all devices by name '{}' from first step".format(group_name))
    net_group_to_update = []
    network_objects = st_helper.network_object_text_search(group_name, "name", exact_match=True)
    for network_object in network_objects:
        if isinstance(network_object, Group_Network_Object) and network_object.display_name == group_name \
                and network_object.device_id in device_ids:
            net_group_to_update.append(network_object)
    logger.debug('Groups have been found: {}'.format(','.join([g.display_name for g in net_group_to_update])))
    return net_group_to_update


def get_edited_groups(groups_to_update, g_members):
    def get_members():
        logger.info("removing member from group '{}'".format(group.name))
        members = []
        is_deleted = False
        tmp_resolved_members = resolved_members[:]
        for member in group.members[:]:
            m_obj = st_helper.network_object_text_search(member.uid.replace('{','').replace('}', ''), "uid", exact_match=True, filter='uid')[0]
            if isinstance(m_obj, Subnet_Network_Object):
                cidr = sum([bin(int(x)).count("1") for x in m_obj.netmask.split(".")])
                ip_str = "{}/{}".format(m_obj.ip, cidr)
                o_type = 'NETWORK'
                object_details = ip_str
            elif isinstance(m_obj, Range_Network_Object):
                object_details = '[{}-{}]'.format(m_obj.first_ip, m_obj.last_ip)
                o_type = 'range'
                ip_str = object_details
            else:
                ip_str = m_obj.ip
                o_type = 'HOST'
                object_details = m_obj.ip

            if ip_str not in tmp_resolved_members:
                status = "DELETED"
                is_deleted = True
            else:
                status = NOT_CHANGE_STATUS
                tmp_resolved_members.remove(ip_str)

            new_member = Group_Change_Member_Object(name=m_obj.display_name,
                                                    num_id=None,
                                                    object_type=o_type,
                                                    object_details=object_details,
                                                    management_name=device.name,
                                                    management_id=device.id,
                                                    object_updated_status='EXISTING_NOT_EDITED',
                                                    uid=m_obj.uid,
                                                    status=status,
                                                    comment=m_obj.comment,
                                                    attr_type='Object')
            members.append(new_member)
        return tmp_resolved_members, is_deleted, members

    def get_new_members(device_id, device_name):
        logger.info('Getting new members')
        members = []
        tmp_members = left_resolved_members[:]
        network_objects = st_helper.get_network_objects_for_device(device_id)
        for network_object in network_objects:
            if isinstance(network_object, Subnet_Network_Object):
                o_type = 'NETWORK'
                cidr = sum([bin(int(x)).count("1") for x in network_object.netmask.split(".")])
                ip_cidr = "{}/{}".format(network_object.ip, cidr)
                if ip_cidr not in tmp_members:
                    continue
                tmp_members.remove(ip_cidr)
                object_detail = "{}/{}".format(network_object.ip, network_object.netmask)
            elif isinstance(network_object, Host_Network_Object) and network_object.ip in tmp_members:
                o_type = TYPE_HOST
                object_detail = network_object.ip
                tmp_members.remove(network_object.ip)
            else:
                continue

            new_member = Group_Change_Member_Object(name=network_object.display_name,
                                                    num_id=None,
                                                    object_type=o_type,
                                                    object_details=object_detail,
                                                    management_name=device_name,
                                                    management_id=device_id,
                                                    status=CHANGE_ADDED_STATUS,
                                                    comment="Added by Orca as object",
                                                    attr_type='Object',
                                                    object_updated_status='EXISTING_NOT_EDITED')
            members.append(new_member)

        # if no object found in device, create new device and add it to the group
        if tmp_members:
            for ip in tmp_members:
                if '/' in ip:
                    o_type = 'NETWORK'
                    ip, cidr = ip.split('/')
                    mask = socket.inet_ntoa(struct.pack('!I', (1 << 32) - (1 << 32 - int(cidr))))
                    object_detail = "{}/{}".format(ip, mask)
                    index_value = "{}/{}".format(ip, cidr)
                else:
                    o_type = TYPE_HOST
                    object_detail = ip
                    index_value = ip
                name = g_members[resolved_members.index(index_value)]
                try:
                    ipaddress.IPv4Address(name)
                except ipaddress.AddressValueError:
                    name = "{}_{}".format(name, ip)
                else:
                    name = "{}_{}".format(o_type, ip)
                new_member = Group_Change_Member_Object(
                    name=name,
                    num_id=None,
                    object_type=o_type,
                    object_details=object_detail,
                    management_name=None,
                    management_id=device_id,
                    status=CHANGE_ADDED_STATUS,
                    object_updated_status='NEW',
                    comment="Added by Orca",
                    attr_type=o_type
                )
                members.append(new_member)
        return members

    group_changes = []
    try:
        resolved_members = []
        g_members = [g.replace('*.', '') for g in g_members]
        for g in g_members:
            logger.debug("Resolving: {}".format(g))
            resolved_members.append(socket.gethostbyname(g))
    except Exception as e:
        logger.error("One on the group member is not resolvable. Error: '{}'".format(e))
    else:
        logger.info("Resolved members: '{}'".format(resolved_members))
        for group in groups_to_update:
            logger.info("Edit group '{}'".format(group.to_xml_string()))
            device = st_helper.get_device_by_id(group.device_id)
            left_resolved_members, objects_deleted, new_members = get_members()
            logger.debug('New members: {}'.format(new_members))
            logger.debug('Resolved members: {}'.format(resolved_members))
            if left_resolved_members or objects_deleted:
                new_members.extend(get_new_members(device.id, device.name))
                group_change_node = Group_Change_Node(
                    name=group.display_name,
                    management_name=device.name,
                    management_id=device.id,
                    change_implementation_status='NOT_SUPPORTED',
                    members=XML_List(Elements.MEMBERS, new_members),
                    change_action="UPDATE"
                )
                # print(group_change_node.to_xml_string())
                group_changes.append(group_change_node)
    return group_changes


def update_groups(groups, orca_id, group_name):
    logger.debug("Groups to update '{}'".format(groups))
    if groups:
        ticket = Ticket.from_file(ticket_template_path)
        ticket.subject = "Generated from Orca ID {}".format(orca_id)
        current_task = ticket.get_last_step().get_last_task()
        group_change_field = current_task.get_field_list_by_type(Attributes.FIELD_TYPE_MULTI_GROUP_CHANGE)[0]
        group_change_field.group_changes = groups
        orca_task_field = current_task.get_field_list_by_name('Orca Task ID')[0]
        orca_task_field.text = orca_id
        group_name_field = current_task.get_field_list_by_name('Group Name')[0]
        group_name_field.text = group_name
        logger.debug("The new ticket is:\n{}".format(ticket.to_xml_string()))
        try:
            ticket_id = sc_helper.post_ticket(ticket)
        except (ValueError, IOError) as e:
            logger.error(e)
            ticket_id = None

        logger.info("SC ticket id '{}' was created".format(ticket_id))
        return ticket_id


def monitor_loop(sleep_time=DEFAULT_POOL_INTERVAL, debug=False):
    setup_loggers(conf.dict("log_levels"), log_to_stdout=debug)
    while True:
        orca_client = OrcaClient(orca_host, group_path_url)
        try:
            orca_response = orca_client.get_group_memebers()
            if orca_response['groups']:
                # orca_response['groups'][0]['name'] = 'LA-G-1'
                # orca_response = {'groups': [{'name': 'aaavvv', 'destinations': ['api.timezonedb.com']}], 'id':'123'}
                device_ids = valid_device_ids(st_helper.get_device_tree())
                logger.debug("Device ids: {}".format(device_ids))
                for group in orca_response['groups']:
                    g_name, members = group['name'], group['destinations']
                    if not members:
                        msg = "Destinations are missing"
                        orca_client.update_orca_ticket(orca_response["id"], 'N/A', status=OrcaStatuses.Failed.value,
                                                       msg=msg,
                                                       group_name=g_name, url_path=orca_update_task_url)
                        continue

                    groups_to_update = get_group_objects_by_name(g_name, device_ids)
                    if not groups_to_update:
                        msg = "Group name '{}' could not be found".format(g_name)
                        orca_client.update_orca_ticket(orca_response["id"], 'N/A', status=OrcaStatuses.Failed.value, msg=msg,
                                                       group_name=g_name, url_path=orca_update_task_url)
                        continue

                    # only if group has been found
                    edited_groups = get_edited_groups(groups_to_update, members)
                    ticket_link = 'N/A'
                    if edited_groups:
                        ticket_id = update_groups(edited_groups, orca_response['id'], group_name=g_name)
                        if ticket_id:
                            status = OrcaStatuses.Running.value
                            ticket_link = sc_helper.get_ticket_link(ticket_id)
                            msg = "SecureChange ticket has been submitted"
                        else:
                            status = OrcaStatuses.Failed.value
                            msg = "Could not create a ticket ..."

                        orca_client.update_orca_ticket(orca_response["id"], ticket_id, status=status, msg=msg,
                                                       group_name=g_name, url_path=orca_update_task_url,
                                                       sc_url=ticket_link)
                    else:
                        msg = "Update is not required the group is identical"
                        logger.info(msg)
                        orca_client.update_orca_ticket(orca_response["id"], 'N/A', status=OrcaStatuses.Succeeded.value,
                                                       msg=msg, group_name=g_name, url_path=orca_update_task_url)
            else:
                logger.info("No need to update a group. Group is equal to null")
        except Exception as error:
            exception_buffer = io.StringIO()
            traceback.print_exc(file=exception_buffer)
            logger.debug("An error occurred: '%s', Traceback: '%s'", error, exception_buffer.getvalue())

        logger.info("Sleeping for %s seconds.", sleep_time)
        time.sleep(sleep_time)


def main():
    cli_args = get_cli_args()
    setup_loggers(conf.dict("log_levels"), log_to_stdout=cli_args.debug)
    if cli_args.no_daemonize:
        monitor_loop(cli_args.sleep_time, cli_args.debug)
    else:
        daemon = daemonize.Daemonize(app="Orca Sync", pid=PID_FILE, action=monitor_loop, verbose=True)
        daemon.start()


if __name__ == '__main__':
    main()
