import base64
import logging
import os
import pickle
from getpass import getpass

from Crypto.Cipher import AES
from pbkdf2 import PBKDF2

from pytos.common.logging.definitions import COMMON_LOGGER_NAME

logger = logging.getLogger(COMMON_LOGGER_NAME)


class Secret_Store_Helper(object):
    """
    This class is used to store and retrieve secret values to disk in a secure manner.
    :cvar PASSPHRASE_FILE: The name of the file to which the passphrase will be written.
    :cvar SECRETSDB_FILE: The name of the file to which the passphrase will be written.
    :cvar SALT_SEED: The encryption seed used to store secrets.
    :cvar PASSPHRASE_SIZE: The default size of automatically generated passphrases.
    :cvar KEY_SIZE: The default key size used to encrypt values.
    :cvar BLOCK_SIZE:
    :cvar IV_SIZE: The default size for the initialization vector used to encrypt.
    """
    PASSPHRASE_FILE = '/usr/local/orca/conf/secret.passphrase'
    SECRETSDB_FILE = '/usr/local/orca/conf/secret.db'
    SALT_SEED = 'EYn7OBDGQ0DKTyWe2I9XoGMeSWEUEoYL'
    PASSPHRASE_SIZE = 64
    KEY_SIZE = 32
    BLOCK_SIZE = 16
    IV_SIZE = 16

    def __init__(self, secret_data_path=None):

        if secret_data_path:
            self.passphrase_path = secret_data_path + "/secret.passphrase"
            self.secretdb_path = secret_data_path + "/secret.db"
        else:
            self.passphrase_path = Secret_Store_Helper.PASSPHRASE_FILE
            self.secretdb_path = Secret_Store_Helper.SECRETSDB_FILE

        self.db = {}
        # Load passphrase
        try:
            with open(self.passphrase_path) as passphrase_file_obj:
                b64_passphrase = passphrase_file_obj.read()
            if len(b64_passphrase) == 0:
                raise IOError("Passphrase length can not be 0.")
            self.passphrase = base64.b64decode(b64_passphrase)
        except IOError:
            logger.debug("Passphrase file does not exist, recreating.")
            self._create_passphrase()
        self._init_secret_db()
        self._load_passphrase()

    def _create_passphrase(self):
        # Create a new passphrase if one does not exist.
        try:
            with open(self.passphrase_path, 'wb') as passphrase_file_obj:
                passphrase = os.urandom(Secret_Store_Helper.PASSPHRASE_SIZE)
                passphrase_file_obj.write(bytes(base64.b64encode(passphrase)))

                # If the passphrase has to be regenerated, the old secrets file is irretrievable and should be removed.
                try:
                    os.remove(self.secretdb_path)
                except OSError:
                    pass
        except PermissionError as error:
            logger.warn("Could not open passphrase file with write access.")
            raise error

    def _load_passphrase(self):
        with open(self.passphrase_path, 'rb') as passphrase_file_obj:
            b64_passphrase = passphrase_file_obj.read()
        if len(b64_passphrase) == 0:
            raise IOError("Passphrase length can not be 0.")
        self.passphrase = base64.b64decode(b64_passphrase)

    def _init_secret_db(self):
        # Load or create secrets database:
        try:
            self.read_db_file()
        except (IOError, EOFError):
            db = {}
            self.write_db_file(db)

    def read_db_file(self):
        with open(self.secretdb_path, 'rb') as secrets_db_file_obj:
            try:
                self.db = pickle.load(secrets_db_file_obj)
            except (UnicodeDecodeError, EOFError):
                raise IOError("Could not unpickle encrypted DB.")
        if self.db == {}:
            raise IOError("Encrypted DB is empty.")

    def write_db_file(self, db):
        with open(self.secretdb_path, 'wb') as secrets_db_file_obj:
            pickle.dump(db, secrets_db_file_obj)
            self._ensure_file_permissions()

    def _get_salt_for_key(self, key):
        return PBKDF2(key, Secret_Store_Helper.SALT_SEED).read(len(Secret_Store_Helper.SALT_SEED))

    def _encrypt(self, plaintext, salt):
        """ Pad plaintext, then encrypt it with a new, randomly initialised cipher. Will not preserve trailing whitespace in plaintext!"""

        # Initialize Cipher Randomly
        init_vector = os.urandom(Secret_Store_Helper.IV_SIZE)

        # Prepare cipher key:
        key = PBKDF2(self.passphrase, salt).read(Secret_Store_Helper.KEY_SIZE)

        cipher = AES.new(key, AES.MODE_CBC, init_vector)  # Create cipher

        return init_vector + cipher.encrypt(plaintext + ' ' * (
            Secret_Store_Helper.BLOCK_SIZE - (len(plaintext) % Secret_Store_Helper.BLOCK_SIZE)))  # Pad and encrypt

    def _decrypt(self, ciphertext, salt):
        """ Reconstruct the cipher object and decrypt. Will not preserve trailing whitespace in the retrieved value!"""

        # Prepare cipher key:
        key = PBKDF2(self.passphrase, salt).read(Secret_Store_Helper.KEY_SIZE)

        # Extract IV:
        init_vector = ciphertext[:Secret_Store_Helper.IV_SIZE]
        ciphertext = ciphertext[Secret_Store_Helper.IV_SIZE:]

        cipher = AES.new(key, AES.MODE_CBC,
                         init_vector)  # Reconstruct cipher (IV isn't needed for decryption so is set to zeros)

        return str(cipher.decrypt(ciphertext), encoding='utf8').rstrip(' ')  # Decrypt and depad

    def _ensure_file_permissions(self):
        os.chmod(self.passphrase_path, 0o664)
        os.chmod(self.secretdb_path, 0o664)

    def set(self, key, value):
        """ Store key-value pair safely and save to disk."""

        self.db[key] = self._encrypt(value, self._get_salt_for_key(key))
        with open(self.secretdb_path, 'wb') as secrets_db_file_obj:
            pickle.dump(self.db, secrets_db_file_obj)
            self._ensure_file_permissions()

    def get(self, key):
        """ Fetch key-value pair."""
        try:
            return self._decrypt(self.db[key], self._get_salt_for_key(key))
        except IndexError:
            logger.error("Could not find encrypted value '%s' .", key)

    def ensure(self, key):
        """ Test if key is stored, if not, prompt the user for it while hiding their input from shoulder-surfers."""
        if not key in self.db:
            self.set(key, getpass('Please enter a value for "%s":' % key))


class SecretDb(Secret_Store_Helper):
    PASSWORD_SUFFIX = "_password"
    USERNAME_SUFFIX = "_username"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _get_encrypted(self, key):
        """
        Get an encrypted value from the Secure Store.
        :param key: The key for the encrypted value to get.
        :type key: str
        """
        try:
            return self.get(key)
        except KeyError:
            return None

    def _set_encrypted(self, key, value):
        """
        Set an encrypted value in the Secure Store.
        :param key: The key for the encrypted value to set.
        :type key: str
        :param value: The value to set for the specified key.
        :type value: str
        """
        return self.set(key, value)

    def get_password(self, key):
        """
        Convenience function that gets a password from the Secure Store (appends the string "_password" to the
        requested key.
        :param key: The key for the encrypted password to get. (The key that will be used is key + "_password")
        :type key: str
        """
        try:
            return self._get_encrypted(key + self.PASSWORD_SUFFIX)
        except KeyError:
            return None

    def set_password(self, key, value):
        """
        Convenience function that sets a password in the Secure Store (appends the string "_password" to the
        requested key.
        :param key: The key for the encrypted password to set. (The key that will be used is key + "_password")
        :type key: str
        """
        return self._set_encrypted(key + self.PASSWORD_SUFFIX, value)

    def get_username(self, key):
        """
        Convenience function that gets a username from the Secure Store (appends the string "_username" to the
        requested key.
        :param key: The key for the encrypted username to get. (The key that will be used is key + "_username")
        :type key: str
        """
        return self._get_encrypted(key + self.USERNAME_SUFFIX)

    def set_username(self, key, value):
        """
        Convenience function that sets a username in the Secure Store (appends the string "_username" to the
        requested key.
        :param key: The key for the encrypted username to set. (The key that will be used is key + "_username")
        :type key: str
        """
        return self._set_encrypted(key + self.USERNAME_SUFFIX, value)

    def delete_section(self, section):
        if not self.db:
            msg = "Secret DB file is empty"
            logger.info(msg)
            raise ValueError(msg)

        db = self.db
        for suffix in [self.USERNAME_SUFFIX, self.PASSWORD_SUFFIX]:
            try:
                del db[section + suffix]
            except KeyError as e:
                msg = "Failed to delete section '{}', Error: '{}'".format(section + suffix, e)
                raise KeyError(msg)
        self.write_db_file(db)