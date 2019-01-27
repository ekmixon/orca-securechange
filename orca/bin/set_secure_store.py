#!/usr/local/orca/python/bin/python3

import sys
import getpass
import argparse

sys.path.append("/usr/local/orca/lib")
from common.secret_store import SecretDb
from pytos.common.logging.logger import setup_loggers
from pytos.common.functions.config import Secure_Config_Parser
from pytos.common.functions import str_to_bool

CREDENTIAL_ITEMS = ["securetrack", "securechange"]
conf = Secure_Config_Parser(config_file_path="/usr/local/orca/conf/custom.conf")
secret_helper = SecretDb()


def get_cli_args():
    example_text = '''

The script will update the secure DB with cerdentials for the Tufin PS scripts.
In order to set the credentials for optional items, use the -s flag and a comma separated list of items to set.
If a specific credential has already been set, you can use the -o flag to overwrite existing credentials.

Example:
    Overwrite default values:           set_secure_store.py -o
    Adding smtp and ldap credentials:   set_secure_store.py -s smtp,ldap
    Deleting smtp credentials:          set_secure_store.py -d smtp
    Viewing existing keys:              set_secure_store.py -v
    '''
    parser = argparse.ArgumentParser(description=example_text, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-o", "--overwrite", action="store_true", dest="overwrite",
                        help="Prompt for overwriting of existing values.", default=False)
    parser.add_argument("-s", "--set-for",
                        dest="optional_credentials_to_set",
                        help="A comma separated list of credentials to set.")
    parser.add_argument("-d", "--delete_key",
                        dest="delete_key",
                        help="Deleting key from secure DB file")
    parser.add_argument("-v", "--view", help="Show all the existing keys", default=False, action="store_true")
    args = parser.parse_args()
    try:
        args.optional_credentials_to_set = args.optional_credentials_to_set.split(",")
    except AttributeError:
        pass
    if args.optional_credentials_to_set:
        args.overwrite = True
    return args


def delete_key(key):
    try:
        confirm = str_to_bool(
            input("Are you sure you want to delete the credentials for key {}? [y/n]\n".format(key)).lower())
    except ValueError:
        print("Failed to confirm response, key {} wasn't deleted.".format(key))
    else:
        if not confirm:
            return
        try:
            secret_helper.delete_section(key)
        except (KeyError, ValueError) as e:
            msg = "Failed to delete credentials for key '{}' in secure DB".format(key)
            print(msg)
        else:
            print("Credentials for the key '{}' was deleted".format(key))


def show_existing_keys():
    username_items = (item for item in secret_helper.db if item.endswith(SecretDb.USERNAME_SUFFIX))
    for item in username_items:
        print('Configured {} username: {}'.format(item.replace(SecretDb.USERNAME_SUFFIX, ''),
                                                  secret_helper._get_encrypted(item)))


def main():
    cli_args = get_cli_args()
    setup_loggers(conf.dict("log_levels"), log_dir_path="/var/log", log_file="ps_orca_logger.log")

    if cli_args.view:
        show_existing_keys()
        sys.exit()

    if cli_args.delete_key:
        delete_key(cli_args.delete_key)
        sys.exit()

    print("This script is used to securely store credentials used by the Tufin PS scripts.")
    print("Press Control+C to skip at each step, Control+D to exit or Enter to input data.")

    credential_items_to_set = CREDENTIAL_ITEMS
    if cli_args.optional_credentials_to_set:
        credential_items_to_set = cli_args.optional_credentials_to_set
    credentials = {}
    for credential_item in credential_items_to_set:
        username_key = "username_" + credential_item
        password_key = "password_" + credential_item
        try:
            try:
                credentials[username_key] = secret_helper.get_username(credential_item)
            except ValueError:
                credentials[username_key] = None

            try:
                credentials[password_key] = secret_helper.get_password(credential_item)
            except ValueError:
                credentials[password_key] = None

            if not credentials[username_key] or cli_args.overwrite:
                print("\r\rPlease enter the username for {}:".format(credential_item), end=' ')
                username_string = input()
                secret_helper.set_username(credential_item, username_string)
                print("\r\rUsername for {} set.".format(credential_item))
            else:
                print("\r\rUsername for {} already set, skipping.".format(credential_item))
            if not credentials[password_key] or cli_args.overwrite:
                password_valid = False
                password_string = ""
                while not password_valid:
                    password_string = getpass.unix_getpass(
                        "\r\rPlease enter the password for {}:".format(credential_item))
                    confirm_password_string = getpass.unix_getpass(
                        "\r\rPlease confirm the password for {}:".format(credential_item))
                    if password_string == confirm_password_string:
                        password_valid = True
                    else:
                        print("\r\rThe passwords for {} do not match.".format(credential_item))
                secret_helper.set_password(credential_item, password_string)
                print("\r\rPassword for {} set.".format(credential_item))
            else:
                print("\r\rPassword for {} already set, skipping.".format(credential_item))
        except KeyboardInterrupt:
            sys.stdout.write("\r\r" + 75 * " ")
            continue
        except EOFError:
            print("\nControl+D pressed, exiting.")
            sys.exit(0)
    print("\r\r")

    sys.exit(0)


if __name__ == '__main__':
    main()
