#!/bin/bash

#Strings
DEFAULT_LOG_LEVEL="WARNING"
LOG_DOMAINS="common helpers reports requests mail sql third_party xml web"
PYTHON_MAJOR_VERSION="3.6"
PYTHON_MINOR_VERSION="8"
TOMCAT_USER="tomcat"
APACHE_GROUP="apache"
TARGET_MD5SUM="__MD5SUM_PLACE_HOLDER__"
TARGET_SHA256SUM="__SHA256SUM_PLACE_HOLDER__"
TITLE="__TITLE_PLACE_HOLDER__"
VERSION=__VERSION_PLACE_HOLDER__
EASY_INSTALL_STRING="import sys; new=sys.path[sys.__plen:]; del sys.path[sys.__plen:]; p=getattr(sys,'__egginsert',0); sys.path[p:p]=new; sys.__egginsert = p+len(new)"
TUFIN_PS_TITLE="SecureChange and Orca integration installer"


#Paths
TAR="/bin/tar"
ORCA_INSTALL_DIR="/usr/local/orca"
CUSTOM_CONF_FILE="custom.conf"
VERSION_FILE="${ORCA_INSTALL_DIR}/PS-version"
INSTALL_LOG="${ORCA_INSTALL_DIR}/install.log"
ORCA_PYTHON_DIR="${ORCA_INSTALL_DIR}/python"
ORCA_LOG_FILE="/var/log/ps_orca_logger.log"
ORCA_PID_DIR="/var/run/orca"
ORCA_INIT_DIR="${ORCA_INSTALL_DIR}/init"
OS_INIT_DIR="/etc/init.d"
PS_FOLDERS=(${ORCA_INSTALL_DIR} ${ORCA_PID_DIR})

#Commands
shopt -s extglob
ORIGINAL_USER=$(logname)
MKDIR=$(which mkdir)
${MKDIR} -p ${ORCA_INSTALL_DIR}
RPM_EXISTS=$(which rpm >> ${INSTALL_LOG} 2>&1;echo $?)
CHKCONFIG_EXISTS=$(which chkconfig >> ${INSTALL_LOG} 2>&1;echo $?)
TOMCAT_USER_EXISTS=$(id ${TOMCAT_USER} >> ${INSTALL_LOG} 2>&1;echo $?)
APACHE_GROUP_EXISTS=$(id ${APACHE_GROUP} >> ${INSTALL_LOG} 2>&1;echo $?)
SUDO_EXISTS=$(which sudo >> ${INSTALL_LOG} 2>&1;echo $?)
SHA256SUM_EXISTS=$(which sha256sum >> ${INSTALL_LOG} 2>&1;echo $?)


get_current_installed_version() {
    if [ -f ${VERSION_FILE} ]; then
        CURRENT_VERSION=$(awk '{print $2}' ${VERSION_FILE})
    else
        CURRENT_VERSION=0
    fi
}


detect_script_package_path_and_size() {
    SOURCE="${BASH_SOURCE[0]}"
    while [ -h "${SOURCE}" ]; do
        INSTALL_SCRIPT_DIR="$( cd -P "$( dirname "${SOURCE}" )" && pwd )"
        SOURCE="$(readlink --canonicalize --no-newline "${SOURCE}")"
        [[ ${SOURCE} != /* ]] && SOURCE="${INSTALL_SCRIPT_DIR}/${SOURCE}"
    done
    INSTALL_SCRIPT_DIR="$( cd -P "$( dirname "${SOURCE}" )" && pwd )"

    #remember our file name
    INSTALL_SCRIPT_FILE=${INSTALL_SCRIPT_DIR}/$(basename "${0##*/}")

    SKIP=$(awk '/^__TARFILE_FOLLOWS__/ { print NR + 1; exit 0; }' "${INSTALL_SCRIPT_FILE}")
}


check_hash(){
    if [[ ${SHA256SUM_EXISTS} == 0 ]]; then
        check_sha256sum
    else
        check_md5sum
    fi
}


check_md5sum() {
    FILE_MD5SUM=$(tail -n +${SKIP} "${INSTALL_SCRIPT_FILE}" | md5sum | awk '{print $1}')

    if [ "${TARGET_MD5SUM}" != "${FILE_MD5SUM}" ]
    then
        print_to_log "MD5sum of embedded archive is corrupt, exiting."
        exit 1
    else
        print_to_log "MD5sum of embedded archive is valid, continuing."
    fi
}


check_sha256sum() {
    FILE_SHA256SUM=$(tail -n +${SKIP} "${INSTALL_SCRIPT_FILE}" | sha256sum | awk '{print $1}')

    if [ "${TARGET_SHA256SUM}" != "${FILE_SHA256SUM}" ]
    then
        print_to_log "SHA256sum of embedded archive is corrupt, exiting."
        exit 1
    else
        print_to_log "SHA256sum of embedded archive is valid, continuing."
    fi
}


print_to_log() {
    echo "$@" | tee -a ${INSTALL_LOG}
}


extract_ps_files() {
    PATH_PREFIX=${1}
    if [[ ! -d "${PATH_PREFIX}${ORCA_INSTALL_DIR}" ]]; then
        print_to_log "Creating folder ${PATH_PREFIX}${ORCA_INSTALL_DIR}"
        mkdir -p ${PATH_PREFIX}${ORCA_INSTALL_DIR}
    fi

    print_to_log "Extracting files into ${PATH_PREFIX}${ORCA_INSTALL_DIR}"
    tail -n +${SKIP} "${INSTALL_SCRIPT_FILE}" | tar mxfj - -C ${PATH_PREFIX}${ORCA_INSTALL_DIR} &> /dev/null

    print_to_log "Extracting PS Python ${ORCA_PYTHON_DIR}/ps_python-${PYTHON_MAJOR_VERSION}.${PYTHON_MINOR_VERSION}.el6.tar.gz"
    if [[ -f "${ORCA_PYTHON_DIR}/ps_python-${PYTHON_MAJOR_VERSION}.${PYTHON_MINOR_VERSION}.el6.tar.gz" ]]; then
        tar zxf "${ORCA_PYTHON_DIR}/ps_python-${PYTHON_MAJOR_VERSION}.${PYTHON_MINOR_VERSION}.el6.tar.gz" -C ${ORCA_PYTHON_DIR}
    fi
}


create_folders() {
    for folder in "${PS_FOLDERS[@]}"; do
        if [[ ! -d "${folder}" ]]; then
            mkdir -p "${folder}"
        fi
    done
}


copy_init_scripts() {
    PATH_PREFIX=${1}
    print_to_log "Copying init scripts."
    if [ -d ${ORCA_INIT_DIR} ]; then
        print_to_log "Copying init scripts files."
        if [[ ! -d ${PATH_PREFIX}${OS_INIT_DIR} ]]; then
            mkdir -p ${PATH_PREFIX}${OS_INIT_DIR}
        fi
        cp -r ${ORCA_INIT_DIR}/* ${PATH_PREFIX}${OS_INIT_DIR} &> /dev/null
    fi
}


restart_init_scripts () {
    if [[ -d ${ORCA_INIT_DIR} ]]; then
        print_to_log "Restarting Orca init scripts"
        for file in ${ORCA_INSTALL_DIR}/init/*; do
            filename=$(basename ${file})
            print_to_log -n "Restarting "${filename}" ... "
            chmod 0755 ${OS_INIT_DIR}/${filename}
            chkconfig --add ${OS_INIT_DIR}/${filename}
            chkconfig --level 345 ${filename} on
            service ${filename} restart &> /dev/null
            service_rc=$?
            if [[ ${service_rc} == 0 ]]; then
                print_to_log "OK"
            else
                print_to_log "NOT OK"
            fi
        done
    fi
}


create_text_box() {
  local s=("$@") b w
  for l in "${s[@]}"; do
    ((w<${#l})) && { b="$l"; w="${#l}"; }
  done
#  tput setaf 4
  echo -e " #${b//?/#}#\n# ${b//?/ } #"
  for line in "${s[@]}"; do
    printf '# %s%*s%s #\n' "$(tput setaf 3)" "-$w" "$line" "$(tput setaf 4)"
  done
  echo "# ${b//?/ } #
 #${b//?/#}#"
#  tput sgr 0
}


validate_root() {
    # Make sure only root can run our script
    if [[ ${EUID} -ne 0 ]]; then
        print_to_log "This script must be run as root, exiting." 1>&2
        exit 1
    fi
}


copy_config_files() {
    if [ ! -f ${ORCA_INSTALL_DIR}/conf/${CUSTOM_CONF_FILE} ]; then
        print_to_log "No existing custom configuration file found, copying template."
        mv ${ORCA_INSTALL_DIR}/conf/${CUSTOM_CONF_FILE}.orig ${ORCA_INSTALL_DIR}/conf/${CUSTOM_CONF_FILE}
    else
        print_to_log "Existing custom configuration file found."
    fi
}


set_ps_permissions() {
    DEST_PREFIX=${1}
    print_to_log "Setting permissions."
    if [[ ${TOMCAT_USER_EXISTS} == 0 ]]; then
        if [[ ${APACHE_GROUP_EXISTS} == 0 ]]; then
            CHOWN_STRING=${TOMCAT_USER}:${APACHE_GROUP}
        else
            CHOWN_STRING=${TOMCAT_USER}
        fi
    else
        print_to_log "User ${TOMCAT_USER} does not exist, setting owner to current user (${ORIGINAL_USER})."
        CHOWN_STRING=${ORIGINAL_USER}
    fi

    for folder in ${DEST_PREFIX}${ORCA_INSTALL_DIR} ${ORCA_PID_DIR}; do
        if [[ -d ${folder} ]]; then
            chown ${CHOWN_STRING} ${folder} -R
        fi
    done

    touch ${ORCA_LOG_FILE}
    chown ${CHOWN_STRING} ${ORCA_LOG_FILE}
    chmod 0666 ${ORCA_LOG_FILE}
    chmod 0770 ${ORCA_PID_DIR}
    chmod 0755 ${DEST_PREFIX}${ORCA_INSTALL_DIR}
    chmod 0664 ${DEST_PREFIX}${ORCA_INSTALL_DIR}/conf -R
    chmod 0775 ${DEST_PREFIX}${ORCA_INSTALL_DIR}/conf
    chmod 0660 ${DEST_PREFIX}${ORCA_INSTALL_DIR}/templates -R
    chmod 0770 ${DEST_PREFIX}${ORCA_INSTALL_DIR}/templates
    chmod 0770 ${DEST_PREFIX}${ORCA_INSTALL_DIR}/bin -R
}


remove() {
    print_to_log "Stopping Orca Group Change service."
    service tufin-ps-orca-group-change stop
    print_to_log "Removing Tufin PS scripts folder."
    rm -rf ${ORCA_INSTALL_DIR}
}


initialize_secure_store() {
    if [[ ${TOMCAT_USER_EXISTS} == 0 ]]; then
        print_to_log "Setting TOS credentials:"
        if [[ ${SUDO_EXISTS} == 0 ]]; then
            sudo -u ${TOMCAT_USER} ${ORCA_INSTALL_DIR}/bin/set_secure_store.py
        else
            su ${TOMCAT_USER} -c ${ORCA_INSTALL_DIR}/bin/set_secure_store.py
        fi
    else
        print_to_log "User ${TOMCAT_USER} does not exist, cannot initialize credential store."
    fi

    print_to_log "Setting Orca credentials:"
    ${ORCA_INSTALL_DIR}/bin/set_secure_store.py -s auth_header_integration
}


create_text_box "${TUFIN_PS_TITLE}, Version ${VERSION}"
validate_root

print_help() {
    echo "The following parameters are valid:"
    echo -e "\t-h | --help\t\t\tPrint this help message."
    echo -e "\t-r | --remove\t\t\tRemove the Tufin PS Scripts package."
    echo -e "\t-x | --extract-only <\$PREFIX>\tOnly extract the Tufin PS Scripts package without installing."
    echo -e "\t\tIf \$PREFIX is not specified, the the files will be extracted to the default install path (${ORCA_INSTALL_DIR})."
    exit 0
}

OPTS=$(getopt -o hrx:ewW --long help,remove,extract-only:,skip-eggs,enable-web -n "${0}" -- "$@")
if [[ $? != 0 ]]; then
    echo "Could not parse arguments for ${0}"
    exit 1
fi

eval set -- "$OPTS"

while true; do
    case "${1}" in
        -h | --help) print_help
            shift
        ;;
        -r | --remove) remove
            exit 0
        ;;
        -x | --extract-only) EXTRACT_DEST_PREFIX="${2}"
            shift 2
            print_to_log "Extracting files only to ${EXTRACT_DEST_PREFIX}${ORCA_INSTALL_DIR}."
            detect_script_package_path_and_size
            check_hash
            extract_ps_files ${EXTRACT_DEST_PREFIX}
            set_ps_permissions ${EXTRACT_DEST_PREFIX}
            exit 0
        ;;
        --) shift
            break
        ;;
        * ) break
        ;;
    esac
done

detect_script_package_path_and_size
check_hash
create_folders
extract_ps_files
copy_config_files
copy_init_scripts
set_ps_permissions
initialize_secure_store
restart_init_scripts

print_to_log "SecureChange Orca integration installation completed"
echo "Version: ${VERSION}" > ${VERSION_FILE}
exit 0


# NOTE: Don't place any newline characters after the last line below.
__TARFILE_FOLLOWS__
