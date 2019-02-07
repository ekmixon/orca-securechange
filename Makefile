#Hardcoded data
LIGHT_FLAG_PLACEHOLDER=__LIGHT_FLAG_PLACEHOLDER__
TITLE_PLACE_HOLDER=__TITLE_PLACE_HOLDER__
MD5SUM_PLACEHOLDER=__MD5SUM_PLACE_HOLDER__
SHA256SUM_PLACEHOLDER=__SHA256SUM_PLACE_HOLDER__
VERSION_PLACEHOLDER=__VERSION_PLACE_HOLDER__
PS_SOLUTION_VERSION=__PS_SOLUTION_VERSION_PLACE_ORDER__
PYTHON_MAJOR_VER=3.6
PYTHON_MINOR_VER=8

#Get variables
MAKEFILE_DIR := $(shell pwd)

VERSION=1.0.0
FILE_LIST=bin conf init lib templates python
FILELIST_TO_CLEAN=setup_orca_ps_scripts.run self_extract_script.sh.tmp tufin_ps_scripts.tar.bz.tmp*
PACKAGE_NAME=setup_orca_ps_scripts-${VERSION}.run


fresh : package


package: ${PACKAGE_NAME}
${PACKAGE_NAME}: orca_ps_scripts.tar.bz.tmp
	@echo "Packaging Orca PS package."
	$(eval TARGET_SHA256SUM:=$(shell cat orca_ps_scripts.tar.bz.tmp.sha256sum))
	$(eval TARGET_MD5SUM:=$(shell cat orca_ps_scripts.tar.bz.tmp.md5sum))
	@cat self_extract_script.sh > self_extract_script.sh.tmp
	@sed -i "s/${VERSION_PLACEHOLDER}/${VERSION}/g" self_extract_script.sh.tmp
	@sed -i "s/${MD5SUM_PLACEHOLDER}/${TARGET_MD5SUM}/g" self_extract_script.sh.tmp
	@sed -i "s/${SHA256SUM_PLACEHOLDER}/${TARGET_SHA256SUM}/g" self_extract_script.sh.tmp
	@cat self_extract_script.sh.tmp orca_ps_scripts.tar.bz.tmp > setup_orca_ps_scripts.run
	@mv setup_orca_ps_scripts.run ${PACKAGE_NAME}
	@chmod +x ${PACKAGE_NAME}
	@rm -f @rm orca_ps_scripts.tar.bz.tmp* self_extract_script.sh.tmp sed*
	@sh ./scripts/github_release.sh github_api_token=${GITHUB_TOKEN} owner=Tufin repo=orca-securechange tag="v${VERSION}" filename=${PACKAGE_NAME}

orca_ps_scripts.tar.bz.tmp:
	@echo "Compress package"
	@cd ${MAKEFILE_DIR}/orca; tar pcjf orca_ps_scripts.tar.bz.tmp ${FILE_LIST}
	@mv ${MAKEFILE_DIR}/orca/orca_ps_scripts.tar.bz.tmp ${MAKEFILE_DIR}/
	@md5sum orca_ps_scripts.tar.bz.tmp | sed 's/\(.*\) \(.*\)/\1/g' |tr -d ' ' > orca_ps_scripts.tar.bz.tmp.md5sum
	@sha256sum orca_ps_scripts.tar.bz.tmp | sed 's/\(.*\) \(.*\)/\1/g' |tr -d ' ' > orca_ps_scripts.tar.bz.tmp.sha256sum