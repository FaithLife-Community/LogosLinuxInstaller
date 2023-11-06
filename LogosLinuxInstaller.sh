#!/usr/bin/env bash
# shellcheck disable=SC2317
export LOGOS_SCRIPT_TITLE="Logos Linux Installer" # From https://github.com/ferion11/LogosLinuxInstaller
export LOGOS_SCRIPT_AUTHOR="Ferion11, John Goodman, T. H. Wright"
export LOGOS_SCRIPT_VERSION="3.7.5" # Script version for this Installer Script

#####
# Originally written by Ferion11.
# Modified to install Logoos 10 by Revd. John Goodman M0RVJ
# Made script agnostic to Logos and Verbum as well as version; made script functions abstract, added optargs, made CLI first class, general code refactoring by Revd. T. H. Wright
#####

# BEGIN ENVIRONMENT
if [ -z "${WINE64_APPIMAGE_FULL_VERSION}" ]; then WINE64_APPIMAGE_FULL_VERSION="v7.18-staging"; export WINE64_APPIMAGE_FULL_VERSION; fi
if [ -z "${WINE64_APPIMAGE_FULL_URL}" ]; then WINE64_APPIMAGE_FULL_URL="https://github.com/ferion11/LogosLinuxInstaller/releases/download/wine-devel-8.19/wine-devel_8.19-x86_64.AppImage"; export WINE64_APPIMAGE_FULL_URL; fi
if [ -z "${WINE64_APPIMAGE_FULL_FILENAME}" ]; then WINE64_APPIMAGE_FULL_FILENAME="$(basename "${WINE64_APPIMAGE_FULL_URL}")"; export WINE64_APPIMAGE_FULL_FILENAME; fi
if [ -z "${WINE64_APPIMAGE_VERSION}" ]; then WINE64_APPIMAGE_VERSION="v7.18-staging"; export WINE64_APPIMAGE_VERSION; fi
if [ -z "${WINE64_APPIMAGE_URL}" ]; then WINE64_APPIMAGE_URL="https://github.com/ferion11/LogosLinuxInstaller/releases/download/v10.0-1/wine-staging_7.18-x86_64.AppImage"; export WINE64_APPIMAGE_URL; fi
if [ -z "${WINE64_BOTTLE_TARGZ_URL}" ]; then WINE64_BOTTLE_TARGZ_URL="https://github.com/ferion11/wine64_bottle_dotnet/releases/download/v5.11b/wine64_bottle.tar.gz"; export WINE64_BOTTLE_TARGZ_URL; fi
if [ -z "${WINE64_BOTTLE_TARGZ_NAME}" ]; then WINE64_BOTTLE_TARGZ_NAME="wine64_bottle.tar.gz"; export WINE64_BOTTLE_TARGZ_NAME; fi
if [ -z "${WINE64_APPIMAGE_FILENAME}" ]; then WINE64_APPIMAGE_FILENAME="$(basename "${WINE64_APPIMAGE_URL}" .AppImage)"; export WINE64_APPIMAGE_FILENAME; fi
if [ -z "${APPIMAGE_LINK_SELECTION_NAME}" ]; then APPIMAGE_LINK_SELECTION_NAME="selected_wine.AppImage"; export APPIMAGE_LINK_SELECTION_NAME; fi
if [ -z "${WINETRICKS_URL}" ]; then WINETRICKS_URL="https://raw.githubusercontent.com/Winetricks/winetricks/5904ee355e37dff4a3ab37e1573c56cffe6ce223/src/winetricks"; export WINETRICKS_URL; fi
if [ -z "${LAUNCHER_TEMPLATE_URL}" ]; then LAUNCHER_TEMPLATE_URL="https://raw.githubusercontent.com/ferion11/LogosLinuxInstaller/master/Launcher-Template.sh"; export LAUNCHER_TEMPLATE_URL; fi
if [ -z "${CONTROL_PANEL_TEMPLATE_URL}" ]; then CONTROL_PANEL_TEMPLATE_URL="https://raw.githubusercontent.com/ferion11/LogosLinuxInstaller/master/controlPanel-Template.sh"; export CONTROL_PANEL_TEMPLATE_URL; fi
if [ -z "${WINETRICKS_DOWNLOADER+x}" ]; then WINETRICKS_DOWNLOADER="wget" ; export WINETRICKS_DOWNLOADER; fi
if [ -z "${WINETRICKS_UNATTENDED+x}" ]; then WINETRICKS_UNATTENDED="" ; export WINETRICKS_UNATTENDED; fi
if [ -z "${WORKDIR}" ]; then WORKDIR="$(mktemp -d /tmp/LBS.XXXXXXXX)"; export WORKDIR ; fi
if [ -z "${PRESENT_WORKING_DIRECTORY}" ]; then PRESENT_WORKING_DIRECTORY="${PWD}" ; export PRESENT_WORKING_DIRECTORY; fi
if [ -z "${LOGOS_FORCE_ROOT+x}" ]; then export LOGOS_FORCE_ROOT="" ; fi
if [ -z "${WINEBOOT_GUI+x}" ]; then export WINEBOOT_GUI="" ; fi
if [ -z "${EXTRA_INFO}" ]; then EXTRA_INFO="The following packages are usually necessary: winbind cabextract libjpeg8."; export EXTRA_INFO; fi
if [ -z "${DEFAULT_CONFIG_PATH}" ]; then DEFAULT_CONFIG_PATH="${HOME}/.config/Logos_on_Linux/Logos_on_Linux.conf"; export DEFAULT_CONFIG_PATH; fi
if [ -z "${LOGOS_LOG}" ]; then LOGOS_LOG="${HOME}/.local/state/Logos_on_Linux/install.log"; mkdir -p "${HOME}/.local/state/Logos_on_Linux"; touch "${LOGOS_LOG}"; export LOGOS_LOG; fi
if [ -z "${WINEDEBUG}" ]; then WINEDEBUG="fixme-all,err-all"; fi; export WINEDEBUG # Make wine output less verbose
if [ -z "${DEBUG}" ]; then DEBUG="FALSE"; fi; export DEBUG
if [ -z "${VERBOSE}" ]; then VERBOSE="FALSE"; fi; export VERBOSE

# END ENVIRONMENT
# BEGIN FUNCTION DECLARATIONS
usage() {
cat << EOF
$LOGOS_SCRIPT_TITLE, by $LOGOS_SCRIPT_AUTHOR, $LOGOS_SCRIPT_VERSION.

Usage: ./LogosLinuxInstaller.sh
Installs ${FLPRODUCT} Bible Software with Wine on Linux.

Options:
    -h   --help                 Prints this help message and exit.
    -v   --version              Prints version information and exit.
    -V   --verbose              Enable extra CLI verbosity.
    -D   --debug                Makes Wine print out additional info.
    -c   --config               Use the Logos on Linux config file when
                                setting environment variables. Defaults to:
                                \$HOME/.config/Logos_on_Linux/Logos_on_Linux.conf
                                Optionally can accept a config file provided by
                                the user.
    -b   --custom-binary-path   Set a custom path to search for wine binaries
                                during the install.
    -r   --regenerate-scripts   Regenerates the Logos.sh and controlPanel.sh
                                scripts using the config file.
    -F   --skip-fonts           Skips installing corefonts and tahoma.
    -f   --force-root           Sets LOGOS_FORCE_ROOT to true, which permits
                                the root user to run the script.
    -k   --make-skel            Make a skeleton install only.
EOF
}

die-if-running() {
	PIDF=/tmp/LogosLinuxInstaller.pid

	if [ -f "${PIDF}" ]; then
		if logos_continue_question "The script is already running on PID $(cat "${PIDF}"). Should it be killed to allow this instance to run?" "The script is already running. Exiting." "1"; then
			kill -9 "$(cat "${PIDF}")"
		fi
	fi
	trap 'rm -f -- "${PIDF}"' EXIT
	echo $$ > "${PIDF}"
}

die-if-root() {
	if [ "$(id -u)" -eq '0' ] && [ -z "${LOGOS_FORCE_ROOT}" ]; then
		logos_error "Running Wine/winetricks as root is highly discouraged. Use -f|--force-root if you must run as root. See https://wiki.winehq.org/FAQ#Should_I_run_Wine_as_root.3F"
	fi
}

verbose() { [[ $VERBOSE = true ]] && return 0 || return 1; };

debug() { [[ $DEBUG = true ]] && return 0 || return 1; };

setDebug() {
	DEBUG="true";
	VERBOSE="true";
	WINEDEBUG="";
	set -x;
	echo "Debug mode enabled." >> "${LOGOS_LOG}";
}

die() { echo >&2 "$*"; exit 1; };

t(){ type "$1"&>/dev/null; };

# Sources:
# https://askubuntu.com/a/1021548/680649
# https://unix.stackexchange.com/a/77138/123999
getDialog() {
	if [ -z "${DISPLAY}" ]; then
		logos_error "The installer does not work unless you are running a display"
		exit 1
	fi

	DIALOG=""
	DIALOG_ESCAPE=""

	if [[ -t 0 ]]; then
		verbose && echo "Running in terminal."
		while :; do
			t whiptail && DIALOG=whiptail && break
			t dialog && DIALOG=dialog && DIALOG_ESCAPE=-- && export DIALOG_ESCAPE && break
			if test "${XDG_CURRENT_DESKTOP}" != "KDE"; then
				t zenity && DIALOG=zenity && GUI=true && break
				#t kdialog && DIALOG=kdialog && GUI=true && break
			elif test "${XDG_CURRENT_DESKTOP}" == "KDE"; then
				#t kdialog && DIALOG=kdialog && GUI=true && break
				t zenity && DIALOG=zenity && GUI=true && break
			else
				echo "No dialog program found. Please install either dialog, whiptail, zenity, or kdialog";
			fi
		done;
	else
		verbose && echo "Running by double click." >> "${LOGOS_LOG}"
		while :; do
			if test "${XDG_CURRENT_DESKTOP}" != "KDE"; then
				t zenity && DIALOG=zenity && GUI=true && break
				#t kdialog && DIALOG=kdialog && GUI=true && break
			elif test "${XDG_CURRENT_DESKTOP}" == "KDE"; then
				#t kdialog && DIALOG=kdialog && GUI=true && break
				t zenity && DIALOG=zenity && GUI=true && break
			else
				no-diag-msg "No dialog program found. Please install either zenity or kdialog."
			fi
		done;
	fi; export DIALOG; export GUI;
}

have_dep() {
	command -v "$1" >/dev/null 2>&1
}

clean_all() {
	logos_info "Cleaning all temp files…"
	rm -fr "/tmp/LBS.*"
	rm -fr "${WORKDIR}"
	logos_info "done"
}

light_wineserver_wait() {
	${WINESERVER_EXE} -w | logos_progress "Waiting for ${WINE_EXE} to end properly…" "Waiting for ${WINE_EXE} to end properly…"
}

heavy_wineserver_wait() {
	wait_process_using_dir "${WINEPREFIX}" | logos_progress "Waiting for ${WINE_EXE} to end properly…" "Waiting for ${WINE_EXE} to end properly…"
	"${WINESERVER_EXE}" -w | logos_progress "Waiting for ${WINE_EXE} proper end" "Waiting for ${WINE_EXE} to end properly…"
}
mkdir_critical() {
	mkdir "$1" || logos_error "Can't create the $1 directory"
}

## BEGIN DIALOG FUNCTIONS
no-diag-msg() {
	echo "${1}" >> "${LOGOS_LOG}";
	xterm -hold -e printf "%s\n" "${1}";
	die;
}
cli_msg() {
	printf "%s\n" "${1}"
}
gtk_info() {
	zenity --info --width=300 --height=200 --text="$*" --title='Information'
}
gtk_progress() {
	zenity --progress --title="${1}" --text="${2}" --pulsate --auto-close --no-cancel
}
gtk_warn() {
	zenity --warning --width=300 --height=200 --text="$*" --title='Warning!'
}
gtk_error() {
	zenity --error --width=300 --height=200 --text="$*" --title='Error!'
}
logos_info() {
	INFO_MESSAGE="${1}"
	if [[ "${DIALOG}" == "whiptail" ]] || [[ "${DIALOG}" == "dialog" ]]; then
		cli_msg "${INFO_MESSAGE}"
	elif [[ "${DIALOG}" == "zenity" ]]; then
		gtk_info "${INFO_MESSAGE}";
		echo "$(date) ${INFO_MESSAGE}" >> "${LOGOS_LOG}";
	elif [[ "${DIALOG}" == "kdialog" ]]; then
		:
	fi
}
logos_progress() {
	PROGRESS_TITLE="${1}"
	PROGRESS_TEXT="${2}"
	if [[ "${DIALOG}" == "whiptail" ]] || [[ "${DIALOG}" == "dialog" ]]; then
		cli_msg "${PROGRESS_TEXT}"
	elif [[ "${DIALOG}" == "zenity" ]]; then
		gtk_progress "${PROGRESS_TITLE}" "${PROGRESS_TEXT}"
	elif [[ "${DIALOG}" == "kdialog" ]]; then
		:
	fi
}
logos_warn() {
    WARN_MESSAGE="${1}"
	if [[ "${DIALOG}" == "whiptail" ]] || [[ "${DIALOG}" == "dialog" ]]; then
	    cli_msg "${WARN_MESSAGE}"
	elif [[ "${DIALOG}" == "zenity" ]]; then
		gtk_warn "${WARN_MESSAGE}"
		echo "$(date) ${WARN_MESSAGE}" >> "${LOGOS_LOG}";
	elif [[ "${DIALOG}" == "kdialog" ]]; then
		:
	fi
}
logos_error() {
	WIKI_LINK="https://github.com/ferion11/LogosLinuxInstaller/wiki"
	TELEGRAM_LINK="https://t.me/linux_logos"
	MATRIX_LINK="https://matrix.to/#/#logosbible:matrix.org"
    ERROR_MESSAGE="${1}"
	SECONDARY="${2}"
	HELP_MESSAGE="If you need help, please consult:\n\n${WIKI_LINK}\n${TELEGRAM_LINK}\n${MATRIX_LINK}"
	if [[ "${DIALOG}" == "whiptail" ]] || [[ "${DIALOG}" == "dialog" ]]; then
	    cli_msg "${ERROR_MESSAGE}\n\n${HELP_MESSAGE}";
	elif [[ "${DIALOG}" == "zenity" ]]; then
		gtk_error "${ERROR_MESSAGE}\n\n${HELP_MESSAGE}";
		echo "$(date) ${ERROR_MESSAGE}" >> "${LOGOS_LOG}";
	elif [[ "${DIALOG}" == "kdialog" ]]; then
		:
	fi
	if [ -z "${SECONDARY}" ]; then
		rm /tmp/LogosLinuxInstaller.pid
		kill -SIGKILL "-$(($(ps -o pgid= -p "${$}")))"
	fi
	exit 1;
}
cli_question() {
	QUESTION_TEXT=${1}
	while true; do
		read -rp "${QUESTION_TEXT} [Y/n]: " yn

		case $yn in
			[yY]* ) return 0; break;;
			[nN]* ) return 1; break;;
			* ) echo "Type Y[es] or N[o].";; 
		esac
	done
}
cli_continue_question() {
	QUESTION_TEXT="${1}"
	NO_TEXT="${2}"
	SECONDARY="${3}"
	if ! cli_question "${QUESTION_TEXT}"; then logos_error "${NO_TEXT}" "${SECONDARY}"; fi
}
cli_acknowledge_question() {
	QUESTION_TEXT=${1}
	NO_TEXT="${2}"
	if ! cli_question "${QUESTION_TEXT}"; then logos_info "${NO_TEXT}"; fi
}
gtk_question() {
	if zenity --question --width=300 --height=200 --text "$@" --title='Question:'
	then return 0
	else return 1
	fi
}
gtk_continue_question() {
	QUESTION_TEXT="${1}"
	NO_TEXT="${2}"
	SECONDARY="${3}"
	if ! gtk_question "${QUESTION_TEXT}"; then logos_error "The installation was cancelled!" "${SECONDARY}"; fi
}
gtk_acknowledge_question() {
	QUESTION_TEXT="${1}"
	NO_TEXT=${2}
	if ! gtk_question "${QUESTION_TEXT}"; then logos_info "${NO_TEXT}"; fi
}
logos_continue_question() {
	QUESTION_TEXT="${1}"
	NO_TEXT=${2}
	SECONDARY="${3}"
	if [[ "${DIALOG}" == "whiptail" ]] || [[ "${DIALOG}" == "dialog" ]]; then
		cli_continue_question "${QUESTION_TEXT}" "${NO_TEXT}" "${SECONDARY}"
	elif [[ "${DIALOG}" == "zenity" ]]; then
		gtk_continue_question "${QUESTION_TEXT}" "${NO_TEXT}" "${SECONDARY}"
	elif [[ "${DIALOG}" == "kdialog" ]]; then
		:
	fi
}
logos_acknowledge_question() {
	QUESTION_TEXT="${1}"
	NO_TEXT="${2}"
	if [[ "${DIALOG}" == "whiptail" ]] || [[ "${DIALOG}" == "dialog" ]]; then
		cli_acknowledge_question "${QUESTION_TEXT}" "${NO_TEXT}"
	elif [[ "${DIALOG}" == "zenity" ]]; then
		gtk_acknowledge_question "${QUESTION_TEXT}" "${NO_TEXT}"
	elif [[ "${DIALOG}" == "kdialog" ]]; then
		:
	fi
}
cli_download() {
	# NOTE: here must be a limitation to handle it easily. $2 can be dir if it already exists or if it ends with '/'
	URI="${1}"
	DESTINATION="${2}"
	# extract last field of URI as filename:
	FILENAME="${URI##*/}"

	if [ "${DESTINATION}" != "${DESTINATION%/}" ]; then
		# it has '/' at the end or it is existing directory
		TARGET="${DESTINATION}/${1##*/}"
		[ -d "${DESTINATION}" ] || mkdir -p "${DESTINATION}" || logos_error "Cannot create ${DESTINATION}"
	elif [ -d "${DESTINATION}" ]; then
		# it's existing directory
		TARGET="${DESTINATION}/${1##*/}"
	else
		TARGET="${DESTINATION}"
		# ensure that the directory where the target file will be exists
		[ -d "${DESTINATION%/*}" ] || mkdir -p "${DESTINATION%/*}" || logos_error "Cannot create directory ${DESTINATION%/*}"
	fi
	wget -c "${URI}" -O "${TARGET}"
}
# shellcheck disable=SC2028
gtk_download() {
	# NOTE: here must be a limitation to handle it easily. $2 can be dir if it already exists or if it ends with '/'
	URI="${1}"
	DESTINATION="${2}"
	# extract last field of URI as filename:
	FILENAME="${URI##*/}"

	if [ "${DESTINATION}" != "${DESTINATION%/}" ]; then
		# it has '/' at the end or it is existing directory
		TARGET="${DESTINATION}/${1##*/}"
		[ -d "${DESTINATION}" ] || mkdir -p "${DESTINATION}" || logos_error "Cannot create ${DESTINATION}"
	elif [ -d "${DESTINATION}" ]; then
		# it's existing directory
		TARGET="${DESTINATION}/${1##*/}"
	else
		TARGET="${DESTINATION}"
		# ensure that the directory where the target file will be exists
		[ -d "${DESTINATION%/*}" ] || mkdir -p "${DESTINATION%/*}" || logos_error "Cannot create directory ${DESTINATION%/*}"
	fi

	pipe_progress="$(mktemp)"
	rm -rf "${pipe_progress}"
	mkfifo "${pipe_progress}"

	pipe_wget="$(mktemp)"
	rm -rf "${pipe_wget}"
	mkfifo "${pipe_wget}"

	# zenity GUI feedback
	# NOTE: Abstracting this progress dialog to a function breaks download capabilities due to the pipe.
	zenity --progress --title "Downloading ${FILENAME}..." --text="Downloading: ${FILENAME}\ninto: ${DESTINATION}\n" --percentage=0 --auto-close < "${pipe_progress}" &
	ZENITY_PID="${!}"

	# download the file with wget:
	wget -c "${URI}" -O "${TARGET}" > "${pipe_wget}" 2>&1 &
	WGET_PID="${!}"

	# process the dialog progress bar
	total_size="Starting…"
	percent="0"
	current="Starting…"
	speed="Starting…"
	remain="Starting…"
	while read -r data; do
		if echo "${data}" | grep -q '^Length:' ; then
			result="$(echo "${data}" | grep "^Length:" | sed 's/.*\((.*)\).*/\1/' |  tr -d '()')"
			if [ ${#result} -le 10 ]; then total_size=${result} ; fi
		fi

		if echo "${data}" | grep -q '[0-9]*%' ;then
			result="$(echo "${data}" | grep -o "[0-9]*%" | tr -d '%')"
			if [ ${#result} -le 3 ]; then percent=${result} ; fi

			result="$(echo "${data}" | grep "[0-9]*%" | sed 's/\([0-9BKMG]\+\).*/\1/' )"
			if [ ${#result} -le 10 ]; then current=${result} ; fi

			result="$(echo "${data}" | grep "[0-9]*%" | sed 's/.*\(% [0-9BKMG.]\+\).*/\1/' | tr -d ' %')"
			if [ ${#result} -le 10 ]; then speed=${result} ; fi

			result="$(echo "${data}" | grep -o "[0-9A-Za-z]*$" )"
			if [ ${#result} -le 10 ]; then remain=${result} ; fi
		fi

		if [ -z "$(pgrep -P "${$}" zenity)" ]; then
			WGET_PID_CURRENT="$(pgrep -P "${$}" wget)"
			[ -n "${WGET_PID_CURRENT}" ] && kill -SIGKILL "${WGET_PID_CURRENT}"
		fi

		[ "${percent}" == "100" ] && break
		
		# Update zenity's progress bar
		echo "${percent}"
		echo "#Downloading: ${FILENAME}\ninto: ${DESTINATION}\n\n${current} of ${total_size} \(${percent}%\)\nSpeed : ${speed}/Sec\nEstimated time : ${remain}"
	done < "${pipe_wget}" > "${pipe_progress}"

	wait "${WGET_PID}"
	WGET_RETURN="${?}"

	wait "${ZENITY_PID}"
	ZENITY_RETURN="${?}"

	fuser -TERM -k -w "${pipe_progress}"
	rm -rf "${pipe_progress}"

	fuser -TERM -k -w "${pipe_wget}"
	rm -rf "${pipe_wget}"

	# NOTE: sometimes the process finishes before the wait command, giving the error code 127
	if [ "${ZENITY_RETURN}" == "0" ] || [ "${ZENITY_RETURN}" == "127" ] ; then
		if [ "${WGET_RETURN}" != "0" ] && [ "${WGET_RETURN}" != "127" ] ; then
			logos_error "ERROR: The installation was cancelled because of an error while attempting a download.\n\nAttmpted Downloading: ${URI}\n\nTarget Destination: ${DESTINATION}\n\n File Name: ${FILENAME}\n\n  - Error Code: WGET_RETURN: ${WGET_RETURN}"
		fi
	else
		logos_error "The installation was cancelled!\n * ZENITY_RETURN: ${ZENITY_RETURN}"
	fi
	verbose && echo "${FILENAME} download finished!"
}
logos_download() {
	URI="${1}"
	DESTINATION="${2}"
	if [[ "${DIALOG}" == "whiptail" ]] || [[ "${DIALOG}" == "dialog" ]]; then
		cli_download "${URI}" "${DESTINATION}"
	elif [[ "${DIALOG}" == "zenity" ]]; then
		gtk_download "${URI}" "${DESTINATION}"
	elif [[ "${DIALOG}" == "kdialog" ]]; then
		no-diag-msg "kdialog not implemented."
	else
		no-diag-msg "No dialog tool found."
	fi
}
logos_reuse_download() {
	SOURCEURL="${1}"
	FILE="${2}"
	TARGETDIR="${3}"
	DOWNLOADS="${HOME}/Downloads"
	DIRS=(
		"${INSTALLDIR}"
		"${PRESENT_WORKING_DIRECTORY}"
		"${DOWNLOADS}"
	)
	FOUND=1
	for i in "${DIRS[@]}"; do
		if [ -f "${i}/${FILE}" ]; then
			logos_info "${FILE} exists in ${i}. Using it…"
			cp "${i}/${FILE}" "${TARGETDIR}/" | logos_progress "Copying…" "Copying ${FILE}\ninto ${TARGETDIR}"
			FOUND=0
			break
		fi
	done
	if [[ "${FOUND}" == 1 ]]; then
    	logos_info "${FILE} does not exist. Downloading…"
    	logos_download "${SOURCEURL}" "${DOWNLOADS}/${FILE}"
    	cp "${DOWNLOADS}/${FILE}" "${TARGETDIR}/" | logos_progress "Copying…" "Copying: ${FILE}\ninto: ${TARGETDIR}"
	fi
}
## END DIALOG FUNCTIONS
# wait on all processes that are using the ${1} directory to finish
wait_process_using_dir() {
	VERIFICATION_DIR="${1}"
	VERIFICATION_TIME=7
	VERIFICATION_NUM=3

	verbose && echo "* Starting wait_process_using_dir…"
	i=0 ; while true; do
		i=$((i+1))
		verbose && echo "wait_process_using_dir: loop with i=${i}"

		echo "wait_process_using_dir: sleep ${VERIFICATION_TIME}"
		sleep "${VERIFICATION_TIME}"

		FIST_PID="$(lsof -t "${VERIFICATION_DIR}" | head -n 1)"
		verbose && echo "wait_process_using_dir FIST_PID: ${FIST_PID}"
		if [ -n "${FIST_PID}" ]; then
			i=0
			verbose && echo "wait_process_using_dir: tail --pid=${FIST_PID} -f /dev/null"
			tail --pid="${FIST_PID}" -f /dev/null
			continue
		fi

		[ "${i}" -lt "${VERIFICATION_NUM}" ] || break
	done
	verbose && echo "* End of wait_process_using_dir."
}

make_skel() {
# ${1} - SET_APPIMAGE_FILENAME
	export SET_APPIMAGE_FILENAME="${1}"

	verbose && echo "* Making skel64 inside ${INSTALLDIR}"
	mkdir -p "${INSTALLDIR}"
	mkdir "${APPDIR}" || die "can't make dir: ${APPDIR}"
	mkdir "${APPDIR_BINDIR}" || die "can't make dir: ${APPDIR_BINDIR}"

	# Making the links
	cd "${APPDIR_BINDIR}" || die "ERROR: Can't open dir: ${APPDIR_BINDIR}"
	ln -s "${SET_APPIMAGE_FILENAME}" "${APPDIR_BINDIR}/${APPIMAGE_LINK_SELECTION_NAME}"
	ln -s "${APPIMAGE_LINK_SELECTION_NAME}" wine
	ln -s "${APPIMAGE_LINK_SELECTION_NAME}" wine64
	ln -s "${APPIMAGE_LINK_SELECTION_NAME}" wineserver
	cd - || die "ERROR: Can't go back to preview dir!"

	mkdir "${APPDIR}/wine64_bottle"
	
	verbose && echo "skel64 done!"
}

## BEGIN CHECK DEPENDENCIES FUNCTIONS
check_commands() {
    for cmd in "$@"; do
        if have_dep "${cmd}"; then
            verbose && echo "* command ${cmd} is installed!"
        else
			verbose && echo "* command ${cmd} not installed!"
			MISSING_CMD+=("${cmd}")
        fi
    done
	if [ "${#MISSING_CMD[@]}" -ne 0 ]; then
		logos_error "Your system is missing ${MISSING_CMD[*]}. Please install your distro's ${MISSING_CMD[*]} package(s).\n ${EXTRA_INFO}"
	fi
}
# shellcheck disable=SC2001
check_libs() {
    for lib in "$@"; do
        HAVE_LIB="$(ldconfig -N -v "$(sed 's/:/ /g' <<< "${LD_LIBRARY_PATH}")" 2>/dev/null | grep "${lib}")"
        if [ -n "${HAVE_LIB}" ]; then
            verbose && echo "* ${lib} is installed!"
        else
            logos_error "Your system does not have lib: ${lib}. Please install ${lib} package.\n ${EXTRA_INFO}"
        fi
    done
}

checkDependencies() {
	verbose && echo "Checking system's for dependencies:"
	check_commands mktemp patch lsof wget find sed grep ntlm_auth awk tr bc xmllint curl;
}

checkDependenciesLogos10() {
	verbose && echo "All dependencies found. Continuing…"
}

checkDependenciesLogos9() {
	verbose && echo "Checking dependencies for Logos 9."
	check_commands xwd cabextract;
	verbose && echo "All dependencies found. Continuing…"
}
## END CHECK DEPENDENCIES FUNCTIONS

## BEGIN INSTALL OPTIONS FUNCTIONS
chooseProduct() {
	BACKTITLE="Choose Product Menu"
	TITLE="Choose Product"
	QUESTION_TEXT="Choose which FaithLife product the script should install:"
	if [ -z "${FLPRODUCT}" ]; then
		if [[ "${DIALOG}" == "whiptail" ]] || [[ "${DIALOG}" == "dialog" ]]; then
			productChoice="$($DIALOG --backtitle "${BACKTITLE}" --title "${TITLE}" --radiolist "${QUESTION_TEXT}" 0 0 0 "Logos" "Logos Bible Software." ON "Verbum" "Verbum Bible Software." OFF "Exit" "Exit." OFF 3>&1 1>&2 2>&3 3>&-)"
		elif [[ "${DIALOG}" == "zenity" ]]; then
			productChoice="$(zenity --width="700" --height="310" --title="${TITLE}" --text="${QUESTION_TEXT}" --list --radiolist --column "S" --column "Description" TRUE "Logos Bible Software." FALSE "Verbum Bible Software." FALSE "Exit.")"
			#zenity --width="700" --height="310" --title="${TITLE}" --text="${QUESTION_TEXT}" --list --radiolist --column "S" --column "Description" TRUE "Logos Bible Software." FALSE "Verbum Bible Software." FALSE "Exit."
		elif [[ "${DIALOG}" == "kdialog" ]]; then
			no-diag-msg "kdialog not implemented."
		else
			no-diag-msg "No dialog tool found"
		fi
	else
		productChoice="${FLPRODUCT}"
	fi
	
	case "${productChoice}" in
		"Logos"*)
			verbose && echo "Installing Logos Bible Software"
			export FLPRODUCT="Logos"
			export FLPRODUCTi="logos4" #This is the variable referencing the icon path name in the repo.
			;;
		"Verbum"*)
			verbose && echo "Installing Verbum Bible Software"
			export FLPRODUCT="Verbum"
			export FLPRODUCTi="verbum" #This is the variable referencing the icon path name in the repo.
			export VERBUM_PATH="Verbum/"
			;;
		"Exit"*)
			logos_error "Exiting installation.";;
		*)
			logos_error "Unknown product. Installation canceled!";;
	esac

	if [ -z "${LOGOS_ICON_URL}" ]; then export LOGOS_ICON_URL="https://raw.githubusercontent.com/ferion11/LogosLinuxInstaller/master/img/${FLPRODUCTi}-128-icon.png" ; fi
}

chooseVersion() {
	BACKTITLE="Choose Version Menu"
	TITLE="Choose Product Version"
	QUESTION_TEXT="Which version of ${FLPRODUCT} should the script install?"
	if [ -z "$TARGETVERSION" ]; then
		if [[ "${DIALOG}" == "whiptail" ]] || [[ "${DIALOG}" == "dialog" ]]; then
			versionChoice="$($DIALOG --backtitle "${BACKTITLE}" --title "${TITLE}" --radiolist "${QUESTION_TEXT}" 0 0 0 "${FLPRODUCT} 10" "10" ON "${FLPRODUCT} 9" "9" OFF "Exit." "Exit." OFF 3>&1 1>&2 2>&3 3>&-)"
		elif [[ "${DIALOG}" == "zenity" ]]; then
			versionChoice="$(zenity --width="700" --height="310" --title="${TITLE}" --text="${QUESTION_TEXT}" --list --radiolist --column "S" --column "Description" TRUE "${FLPRODUCT} 10" FALSE "${FLPRODUCT} 9" FALSE "Exit")"
		elif [[ "${DIALOG}" == "kdialog" ]]; then
			no-diag-msg "kdialog not implemented."
		else
			no-diag-msg "No dialog tool found."
		fi
	else
		versionChoice="$TARGETVERSION"
	fi
	case "${versionChoice}" in
		*"10")
			checkDependenciesLogos10;
			export TARGETVERSION="10";
			;;
		*"9")
			checkDependenciesLogos9;
			export TARGETVERSION="9";
			;;
		"Exit.")
			exit
			;;
		*)
			logos_error "Unknown version. Installation canceled!"
	esac

	LOGOS_RELEASE_VERSION=$(curl -s "https://clientservices.logos.com/update/v1/feed/logos${TARGETVERSION}/stable.xml" | xmllint --format - | sed -e 's/ xmlns.*=".*"//g' | sed -e 's@logos:minimum-os-version@minimum-os-version@g' | sed -e 's@logos:version@version@g' | xmllint --xpath "/feed/entry[1]/version/text()" -); export LOGOS_RELEASE_VERSION;
	if [ -z "${LOGOS64_URL}" ]; then export LOGOS64_URL="https://downloads.logoscdn.com/LBS${TARGETVERSION}/${VERBUM_PATH}Installer/${LOGOS_RELEASE_VERSION}/${FLPRODUCT}-x64.msi" ; fi

	if [ "${FLPRODUCT}" = "Logos" ]; then
		LOGOS_VERSION="$(echo "${LOGOS64_URL}" | cut -d/ -f6)"; 
	elif [ "${FLPRODUCT}" = "Verbum" ]; then
		LOGOS_VERSION="$(echo "${LOGOS64_URL}" | cut -d/ -f7)"; 
	else
		logos_error "FLPRODUCT not set in config. Please update your config to specify either 'Logos' or 'Verbum'."
	fi
	export LOGOS_VERSION;
	LOGOS64_MSI="$(basename "${LOGOS64_URL}")"; export LOGOS64_MSI

	if [ -z "${INSTALLDIR}" ]; then
		export INSTALLDIR="${HOME}/${FLPRODUCT}Bible${TARGETVERSION}" ;
	fi
	if [ -z "${APPDIR}" ]; then
		export APPDIR="${INSTALLDIR}/data"
	fi
	if [ -z "${APPDIR_BINDIR}" ]; then
		export APPDIR_BINDIR="${APPDIR}/bin"
	fi
}

wineBinaryVersionCheck() {
	# Does not check for Staging. Will not implement: expecting merging of commits in time.
	TESTBINARY="${1}"

	if [ "${TARGETVERSION}" == "10" ]; then
		WINE_MINIMUM="7.18"
	elif [ "${TARGETVERSION}" == "9" ]; then
		WINE_MINIMUM="7.0"
	else
		logos_error "TARGETVERSION not set."
	fi

	# Check if the binary is executable. If so, check if TESTBINARY's version is ≥ WINE_MINIMUM, or if it is Proton or a link to a Proton binary, else remove.
	if [ -x "${TESTBINARY}" ]; then
		TESTWINEVERSION=$("$TESTBINARY" --version | awk -F' ' '{print $1}' | awk -F'-' '{print $2}' | awk -F'.' '{print $1"."$2}');
		if (( $(echo "$TESTWINEVERSION >= $WINE_MINIMUM" | bc -l) )); then
			if (( $(echo "$TESTWINEVERSION != 8.0" | bc -l) )); then
				return 0;
			fi
		elif [[ ${TESTBINARY} =~ .*"Proton - Experimental".* ]]; then
			return 0;
		# If it is a symlink, check its actual path. If it is Proton, let it pass.
		elif [ -L "${TESTBINARY}" ]; then
			TESTWINE=$(readlink -f "$TESTBINARY")
			if [[ "${TESTWINE}" =~ .*"Proton - Experimental".* ]]; then
				return 0;
			fi
		else
			return 1;
		fi
	fi
}

checkPath() {
	IFS=:
	for dir in $PATH; do
		if [ -x "$dir/$1" ]; then
			echo "$dir/$1"
		fi
	done

}

createWineBinaryList() {
	logos_info "Creating binary list."
	#TODO: Make optarg to add custom path to this array.
	WINEBIN_PATH_ARRAY=( "/usr/local/bin" "$HOME/bin" "$HOME/PlayOnLinux/wine/linux-amd64/*/bin" "$HOME/.steam/steam/steamapps/common/Proton - Experimental/files/bin" "${CUSTOMBINPATH}" )

	# Temporarily modify PATH for additional WINE64 binaries.
	for p in "${WINEBIN_PATH_ARRAY[@]}"; do
		if [[ ":$PATH:" != *":${p}:"* ]] && [ -d "${p}" ]; then
			PATH="$PATH:${p}"
		fi
	done

	# Check each directory in PATH for wine64; add to list
	checkPath wine64 > "${WORKDIR}/winebinaries"

	cp "${WORKDIR}/winebinaries" "${WORKDIR}/winebinaries.bak"

	# Check remaining binary versions
	while read -r i; do
		if wineBinaryVersionCheck "$i"; then
			# Skip
			:
		else
			sed -i "\@$i@d" "${WORKDIR}/winebinaries"
		fi
	done < "${WORKDIR}/winebinaries.bak";
}

getAppImage() {
	logos_reuse_download "${WINE64_APPIMAGE_FULL_URL}" "${WINE64_APPIMAGE_FULL_FILENAME}" "${APPDIR_BINDIR}"
}

chooseInstallMethod() {
	
	if [ -z "$WINEPREFIX" ]; then
		export WINEPREFIX="${APPDIR}/wine64_bottle"
	fi

	if [ -z "$WINE_EXE" ]; then
		createWineBinaryList;
	
		WINEBIN_OPTIONS=()
		
		# Add AppImage to list
		if [[ "${TARGETVERSION}" != "9" ]]; then
			if [[ "${DIALOG}" == "whiptail" ]] || [[ "${DIALOG}" == "dialog" ]]; then
				# NOTE: The missing quotations in this array are intentional and accounted for below.
				WINEBIN_OPTIONS+=("AppImage ${APPDIR_BINDIR}/${WINE64_APPIMAGE_FULL_FILENAME}" "AppImage of Wine64 ${WINE64_APPIMAGE_FULL_VERSION}" ON)
			elif [[ "${DIALOG}" == "zenity" ]]; then
				WINEBIN_OPTIONS+=(TRUE "AppImage" "AppImage of Wine64 ${WINE64_APPIMAGE_FULL_VERSION}" "${APPDIR_BINDIR}/${WINE64_APPIMAGE_FULL_FILENAME}")
			elif [[ "${DIALOG}" == "kdialog" ]]; then
				no-diag-msg "kdialog not implemented."
			else
				no-diag-msg "No dialog tool found."
			fi
		fi
		
		while read -r line; do
			# Set binary code, description, and path based on path
			if [ -L "$line" ]; then
				WINEOPT=$(readlink -f "$line")
			else
				WINEOPT="$line"
			fi
	
			if [[ "$WINEOPT" == *"/usr/bin/"* ]]; then
				WINEOPT_CODE="System"
				WINEOPT_DESCRIPTION="\"Use the system binary (i.e., /usr/bin/wine64). WINE must be 7.18-staging or later. Stable or Devel do not work.\""
				WINEOPT_PATH="${line}"
			elif [[ "$WINEOPT" == *"Proton"* ]]; then
				WINEOPT_CODE="Proton"
				WINEOPT_DESCRIPTION="\"Install using the Steam Proton fork of WINE.\""
				WINEOPT_PATH="${line}"
			elif [[ "$WINEOPT" == *"PlayOnLinux"* ]]; then
				WINEOPT_CODE="PlayOnLinux"
				WINEOPT_DESCRIPTION="\"Install using a PlayOnLinux WINE64 binary.\""
				WINEOPT_PATH="${line}"
			else
				WINEOPT_CODE="Custom"
				WINEOPT_DESCRIPTION="\"Use a WINE64 binary from another directory.\""
				WINEOPT_PATH="${line}"
			fi
	
			# Create wine binary option array
			if [[ "${DIALOG}" == "whiptail" ]] || [[ "${DIALOG}" == "dialog" ]]; then
				# NOTE: The missing quotations in this array are intentional and accounted for below.
				WINEBIN_OPTIONS+=("${WINEOPT_CODE} ${WINEOPT_PATH}" "${WINEOPT_DESCRIPTION}" OFF)
			elif [[ "${DIALOG}" == "zenity" ]]; then
				WINEBIN_OPTIONS+=(FALSE "${WINEOPT_CODE}" "${WINEOPT_DESCRIPTION}" "${WINEOPT_PATH}")
			elif [[ "${DIALOG}" == "kdialog" ]]; then
				no-diag-msg "kdialog not implemented."
			else
				no-diag-msg "No dialog tool found."
			fi
		done < "${WORKDIR}/winebinaries"
	
	
		BACKTITLE="Choose Wine Binary Menu"
		TITLE="Choose Wine Binary"
		QUESTION_TEXT="Which Wine binary and install method should the script use to install ${FLPRODUCT} v${LOGOS_VERSION} in ${INSTALLDIR}?"
		WINEBIN_OPTIONS_LENGTH="${#WINEBIN_OPTIONS[@]}"
		if [[ "${DIALOG}" == "whiptail" ]] || [[ "${DIALOG}" == "dialog" ]]; then
			installationChoice=$( $DIALOG --backtitle "${BACKTITLE}" --title "${TITLE}" --radiolist "${QUESTION_TEXT}" 0 0 "${WINEBIN_OPTIONS_LENGTH}" "${WINEBIN_OPTIONS[@]}" 3>&1 1>&2 2>&3 3>&- )
			read -r -a installArray <<< "${installationChoice}"
			WINEBIN_CODE=$(echo "${installArray[0]}" | awk -F' ' '{print $1}'); export WINEBIN_CODE
			WINE_EXE=$(echo "${installArray[0]}" | awk -F' ' '{print $2}'); export WINE_EXE
		elif [[ "${DIALOG}" == "zenity" ]]; then
			column_names=(--column "Choice" --column "Code" --column "Description" --column "Path")
			installationChoice=$(zenity --width=1024 --height=480 \
				--title="${TITLE}" \
				--text="${QUESTION_TEXT}" \
				--list --radiolist "${column_names[@]}" "${WINEBIN_OPTIONS[@]}" --print-column=2,3,4);
			OIFS=$IFS
			IFS='|' read -r -a installArray <<< "${installationChoice}"
			IFS=$OIFS
			export WINEBIN_CODE=${installArray[0]}
			export WINE_EXE=${installArray[2]}
		elif [[ "${DIALOG}" == "kdialog" ]]; then
			no-diag-msg "kdialog not implemented."
		else
			no-diag-msg "No dialog tool found."
		fi
	fi
	verbose && echo "chooseInstallMethod(): WINEBIN_CODE: ${WINEBIN_CODE}; WINE_EXE: ${WINE_EXE}"
}

checkExistingInstall() {
	# Now that we know what the user wants to install and where, determine whether an install exists and whether to continue.
	if [ -d "${INSTALLDIR}" ]; then
		if find "${INSTALLDIR}" -name Logos.exe -o -name Verbum.exe | grep -qE "(Logos\/Logos.exe|Verbum\/Verbum.exe)"; then
			EXISTING_LOGOS_INSTALL=1; export EXISTING_LOGOS_INSTALL;
			logos_error "An install was found at ${INSTALLDIR}. Please remove/rename it or use another location by setting the INSTALLDIR variable."
		else
			EXISTING_LOGOS_DIRECTORY=1; export EXISTING_LOGOS_DIRECTORY;
			logos_error "A directory exists at ${INSTALLDIR}. Please remove/rename it or use another location by setting the INSTALLDIR variable."
		fi
	else
		verbose && echo "Installing to an empty directory at ${INSTALLDIR}."
	fi
}

beginInstall() {
	if [ "${SKEL}" = "1" ]; then
		verbose && echo "Making a skeleton install of the project only. Exiting after completion."
		make_skel "none.AppImage"
		exit 0;
	fi
	if [ -n "${WINEBIN_CODE}" ]; then	
		case "${WINEBIN_CODE}" in
			"AppImage"*)
				check_libs libfuse;
				verbose && echo "Installing ${FLPRODUCT} Bible ${TARGETVERSION} using ${WINE64_APPIMAGE_FULL_VERSION} AppImage…"
				if [ -z "${REGENERATE}" ]; then
					make_skel "${WINE64_APPIMAGE_FULL_FILENAME}"

					# exporting PATH to internal use if using AppImage, doing backup too:
					export OLD_PATH="${PATH}"
					export PATH="${APPDIR_BINDIR}":"${PATH}"
	
					# Geting the AppImage:
					getAppImage;	
					chmod +x "${APPDIR_BINDIR}/${WINE64_APPIMAGE_FULL_FILENAME}"
					export WINE_EXE="${APPDIR_BINDIR}/wine64"
				fi
				;;
			"System"|"Proton"|"PlayOnLinux"|"Custom")
				verbose && echo "Installing ${FLPRODUCT} Bible ${TARGETVERSION} using a ${WINEBIN_CODE} WINE64 binary…"
				if [ -z "${REGENERATE}" ]; then
					make_skel "none.AppImage"
				fi
				;;
			*)
				logos_error "WINEBIN_CODE error. Installation canceled!"
		esac
	else
		verbose && echo "WINEBIN_CODE is not set in your config file."
	fi

	verbose && echo "Using: $(${WINE_EXE} --version)"

	# Set WINESERVER_EXE based on WINE_EXE.
	if [ -z "${WINESERVER_EXE}" ]; then
		if [ -x "$(dirname "${WINE_EXE}")/wineserver" ]; then
			WINESERVER_EXE="$(echo "$(dirname "${WINE_EXE}")/wineserver" | tr -d '\n')"; export WINESERVER_EXE;
		else
			logos_error "$(dirname "${WINE_EXE}")/wineserver not found. Please either add it or create a symlink to it, and rerun."
		fi
	fi
}
## END INSTALL OPTIONS FUNCTIONS
## BEGIN WINE BOTTLE AND WINETRICKS FUNCTIONS
prepareWineBottle() {
	logos_continue_question "Now the script will create and configure the Wine Bottle at ${WINEPREFIX}. You can cancel the installation of Mono. Do you wish to continue?" "The installation was cancelled!"
	verbose && echo "${WINE_EXE} wineboot"
	if [ -z "${WINEBOOT_GUI}" ]; then
		(DISPLAY="" ${WINE_EXE} wineboot) | logos_progress "Waiting for ${WINE_EXE} wineboot" "Waiting for ${WINE_EXE} wineboot…"
	else
		${WINE_EXE} wineboot
	fi
	light_wineserver_wait
}

wine_reg_install() {
	REG_FILENAME="${1}"
	verbose && echo "${WINE_EXE} regedit.exe ${REG_FILENAME}"
	"${WINE_EXE}" regedit.exe "${WORKDIR}"/"${REG_FILENAME}" | logos_progress "Wine regedit" "Wine is installing ${REG_FILENAME} in ${WINEPREFIX}"

	light_wineserver_wait
	verbose && echo "${WINE_EXE} regedit.exe ${REG_FILENAME} DONE!"
}

downloadWinetricks() {
	logos_reuse_download "${WINETRICKS_URL}" "winetricks" "${APPDIR_BINDIR}"
	chmod 755 "${APPDIR_BINDIR}/winetricks"
}

setWinetricks() {
	# Check if local winetricks version available; else, download it
	if [ -z "${WINETRICKSBIN}" ]; then 
		if [ "$(which winetricks)" ]; then
			# Check if local winetricks version is up-to-date; if so, offer to use it or to download; else, download it
			LOCAL_WINETRICKS_VERSION=$(winetricks --version | awk -F' ' '{print $1}')
			if [ "${LOCAL_WINETRICKS_VERSION}" -ge "20220411" ]; then
				BACKTITLE="Choose Winetricks Menu"
				TITLE="Choose Winetricks"
				QUESTION_TEXT="Should the script use the system's local winetricks or download the latest winetricks from the Internet? The script needs to set some Wine options that ${FLPRODUCT} requires on Linux."
				if [[ "${DIALOG}" == "whiptail" ]] || [[ "${DIALOG}" == "dialog" ]]; then
					winetricksChoice="$($DIALOG --backtitle "${BACKTITLE}" --title "${TITLE}" --radiolist "${QUESTION_TEXT}" 0 0 0 "1" "Use local winetricks." ON "2" "Download winetricks from the Internet." OFF 3>&1 1>&2 2>&3 3>&-)"
				elif [[ "${DIALOG}" == "zenity" ]]; then
					winetricksChoice="$(zenity --width=700 --height=310 \
						--title="${TITLE}" \
						--text="${QUESTION_TEXT}" \
						--list --radiolist --column "S" --column "Description" \
						TRUE "1- Use local winetricks." \
						FALSE "2- Download winetricks from the Internet." )"
				elif [[ "${DIALOG}" == "kdialog" ]]; then
					no-diag-msg "kdialog not implemented."
				else
					no-diag-msg "No dialog tool found."
				fi

				case "${winetricksChoice}" in
					1*) 
						verbose && echo "Setting winetricks to the local binary…"
						WINETRICKSBIN="$(which winetricks)";
						export WINETRICKSBIN;
						;;
					2*) 
						downloadWinetricks;
						WINETRICKSBIN="${APPDIR_BINDIR}/winetricks";
						export WINETRICKSBIN;
						;;
					*)  
						logos_error "Installation canceled!"
					esac
			else
				logos_info "The system's winetricks is too old. Downloading an up-to-date winetricks from the Internet…"
				downloadWinetricks;
				export WINETRICKSBIN="${APPDIR_BINDIR}/winetricks"
			fi
		else
			verbose && echo "Local winetricks not found. Downloading winetricks from the Internet…"
			downloadWinetricks;
			export WINETRICKSBIN="${APPDIR_BINDIR}/winetricks"
		fi
	fi

	verbose && echo "Winetricks is ready to be used."
}

winetricks_install() {
	verbose && echo "winetricks ${*}"
	if [[ "${DIALOG}" == "whiptail" ]] || [[ "${DIALOG}" == "dialog" ]]; then
		"$WINETRICKSBIN" "${@}"
	elif [[ "${DIALOG}" == "zenity" ]]; then
		pipe_winetricks="$(mktemp)"
		rm -rf "${pipe_winetricks}"
		mkfifo "${pipe_winetricks}"

		# zenity GUI feedback
		logos_progress "Winetricks ${*}" "Winetricks installing ${*}" < "${pipe_winetricks}" &
		ZENITY_PID="${!}";

		"$WINETRICKSBIN" "${@}" | tee "${pipe_winetricks}";
		WINETRICKS_STATUS="${?}";

		wait "${ZENITY_PID}";
		ZENITY_RETURN="${?}";

		rm -rf "${pipe_winetricks}";

		# NOTE: sometimes the process finishes before the wait command, giving the error code 127
		if [ "${ZENITY_RETURN}" == "0" ] || [ "${ZENITY_RETURN}" == "127" ] ; then
			if [ "${WINETRICKS_STATUS}" != "0" ] ; then
				${WINESERVER_EXE} -k;
				logos_error "Winetricks Install ERROR: The installation was cancelled because of sub-job failure!\n * winetricks ${*}\n  - WINETRICKS_STATUS: ${WINETRICKS_STATUS}";
			fi
		else
			"${WINESERVER_EXE}" -k;
			logos_error "The installation was cancelled!\n * ZENITY_RETURN: ${ZENITY_RETURN}";
		fi
	elif [[ "${DIALOG}" == "kdialog" ]]; then
		no-diag-msg "kdialog not implemented."
	else
		no-diag-msg "No dialog tool found."
	fi

	verbose && echo "winetricks ${*} DONE!";

	heavy_wineserver_wait;
}

winetricks_dll_install() {
	verbose && echo "winetricks ${*}"
	logos_continue_question "Now the script will install the DLL ${*}. This may take a while. There will not be any GUI feedback for this. Continue?" "The installation was cancelled!"
	"$WINETRICKSBIN" "${@}"
	verbose && echo "winetricks ${*} DONE!";
	heavy_wineserver_wait;
}

getPremadeWineBottle() {
	verbose && echo "Installing pre-made wineBottle 64bits…"
	logos_reuse_download "${WINE64_BOTTLE_TARGZ_URL}" "${WINE64_BOTTLE_TARGZ_NAME}" "${WORKDIR}"
	tar xzf "${WORKDIR}"/"${WINE64_BOTTLE_TARGZ_NAME}" -C "${APPDIR}"/ | logos_progress "Extracting…" "Extracting: ${WINE64_BOTTLE_TARGZ_NAME}\ninto: ${APPDIR}"
}
## END WINE BOTTLE AND WINETRICKS FUNCTIONS
## BEGIN LOGOS INSTALL FUNCTIONS
getLogosExecutable() {
	# This VAR is used to verify the downloaded MSI is latest
	if [ -z "${LOGOS_EXECUTABLE}" ]; then 
		LOGOS_EXECUTABLE="${FLPRODUCT}_v${LOGOS_VERSION}-x64.msi"
	fi

	logos_continue_question "Now the script will check for the MSI installer. Then it will download and install ${FLPRODUCT} Bible at ${WINEPREFIX}. You will need to interact with the installer. Do you wish to continue?" "The installation was cancelled!"

	# Geting and install ${FLPRODUCT} Bible
	# First check current directory to see if the .MSI is present; if not, check user'\''s Downloads/; if not, download it new. Once found, copy it to WORKDIR for future use.
	verbose && echo "Installing ${FLPRODUCT}Bible 64bits…"
	if [ -f "${PRESENT_WORKING_DIRECTORY}/${LOGOS_EXECUTABLE}" ]; then
		verbose && echo "${LOGOS_EXECUTABLE} exists. Using it…"
		cp "${PRESENT_WORKING_DIRECTORY}/${LOGOS_EXECUTABLE}" "${APPDIR}/" | logos_progress "Copying…" "Copying: ${LOGOS_EXECUTABLE}\ninto: ${APPDIR}"
	elif [ -f "${HOME}/Downloads/${LOGOS_EXECUTABLE}" ]; then
		verbose && echo "${LOGOS_EXECUTABLE} exists. Using it…"
		cp "${HOME}/Downloads/${LOGOS_EXECUTABLE}" "${APPDIR}/" | logos_progress "Copying…" "Copying: ${LOGOS_EXECUTABLE}\ninto: ${APPDIR}"
	else
		verbose && echo "${LOGOS_EXECUTABLE} does not exist. Downloading…"
		logos_download "${LOGOS64_URL}" "${HOME}/Downloads/"
		mv "${HOME}/Downloads/${LOGOS64_MSI}" "${HOME}/Downloads/${LOGOS_EXECUTABLE}"
		cp "${HOME}/Downloads/${LOGOS_EXECUTABLE}" "${APPDIR}/" | logos_progress "Copying…" "Copying: ${LOGOS_EXECUTABLE}\ninto: ${APPDIR}"
	fi
}

installMSI() {
	# Execute the .MSI
	verbose && echo "Running: ${WINE_EXE} msiexec /i ${APPDIR}/${LOGOS_EXECUTABLE}"
	"${WINE_EXE}" msiexec /i "${APPDIR}"/"${LOGOS_EXECUTABLE}"
}

installFonts() {
	if [ -z "${WINETRICKS_UNATTENDED}" ]; then
		if [ -z "${SKIP_FONTS}" ]; then
			winetricks_install -q corefonts
			winetricks_install -q tahoma
		fi
		winetricks_install -q settings fontsmooth=rgb
	else
		if [ -z "${SKIP_FONTS}" ]; then
			winetricks_install corefonts
			winetricks_install tahoma
		fi
		winetricks_install settings fontsmooth=rgb
	fi
}

installD3DCompiler() {
	if [ -z "${WINETRICKS_UNATTENDED}" ]; then
		winetricks_dll_install -q d3dcompiler_47;
	else
		winetricks_dll_install d3dcompiler_47;
	fi
}

installLogos9() {	
	getPremadeWineBottle;

	setWinetricks;
	installFonts;
	installD3DCompiler;
	getLogosExecutable;
	installMSI;

	verbose && echo "======= Set ${FLPRODUCT}Bible Indexing to Vista Mode: ======="
	"${WINE_EXE}" reg add "HKCU\\Software\\Wine\\AppDefaults\\${FLPRODUCT}Indexer.exe" /v Version /t REG_SZ /d vista /f
	verbose && echo "======= ${FLPRODUCT}Bible logging set to Vista mode! ======="
}

installLogos10() {
	cat > "${WORKDIR}"/disable-winemenubuilder.reg << EOF
REGEDIT4

[HKEY_CURRENT_USER\Software\Wine\DllOverrides]
"winemenubuilder.exe"=""

EOF

	cat > "${WORKDIR}"/renderer_gdi.reg << EOF
REGEDIT4

[HKEY_CURRENT_USER\Software\Wine\Direct3D]
"DirectDrawRenderer"="gdi"
"renderer"="gdi"

EOF

	wine_reg_install "disable-winemenubuilder.reg";
	wine_reg_install "renderer_gdi.reg";

	setWinetricks;
	installFonts;
	installD3DCompiler;

	if [ -z "${WINETRICKS_UNATTENDED}" ]; then
		winetricks_install -q settings win10
	else
		winetricks_install settings win10
	fi

	getLogosExecutable;
	installMSI;
}
## END LOGOS INSTALL FUNCTIONS

getScriptTemplate() {
	SCRIPT_TEMPLATE="${1}"
	if [ "${SCRIPT_TEMPLATE}" = "Launcher-Template.sh" ]; then
		SCRIPT_TEMPLATE_URL="${LAUNCHER_TEMPLATE_URL}"
	else
		SCRIPT_TEMPLATE_URL="${CONTROL_PANEL_TEMPLATE_URL}"
	fi
	verbose && echo "Downloading the launcher script template…"
	if [ -f "${PRESENT_WORKING_DIRECTORY}/${SCRIPT_TEMPLATE}" ]; then
		verbose && echo "${SCRIPT_TEMPLATE} found. Using it…"
		cp "${PRESENT_WORKING_DIRECTORY}/${SCRIPT_TEMPLATE}" "${WORKDIR}/" | logos_progress "Copying…" "Copying: ${SCRIPT_TEMPLATE} into ${WORKDIR}"
	elif [ -f "${HOME}/Downloads/${SCRIPT_TEMPLATE}" ]; then
		verbose && echo "${SCRIPT_TEMPLATE} found in Downloads. Replacing it…"
		rm -f "${HOME}/Downloads/${SCRIPT_TEMPLATE}"
		logos_download "${SCRIPT_TEMPLATE_URL}" "${HOME}/Downloads/"
		cp "${HOME}/Downloads/${SCRIPT_TEMPLATE}" "${WORKDIR}/" | logos_progress "Copying…" "Copying: ${SCRIPT_TEMPLATE} into ${WORKDIR}"
	else
		logos_download "${SCRIPT_TEMPLATE_URL}" "${HOME}/Downloads/"
		cp "${HOME}/Downloads/${SCRIPT_TEMPLATE}" "${WORKDIR}/" | logos_progress "Copying…" "Copying: ${SCRIPT_TEMPLATE} into ${WORKDIR}"
	fi
}

# See https://stackoverflow.com/a/17921589/1896800
apply_shell_expansion() {
	file="$1"
	data=$(< "$file")
	delimiter="__apply_shell_expansion_delimiter__"
	command="cat <<$delimiter"$'\n'"$data"$'\n'"$delimiter"
	eval "$command"
}

createLauncher() {
	getScriptTemplate "Launcher-Template.sh";
	printf "%s\n" "$(apply_shell_expansion "${WORKDIR}/Launcher-Template.sh")" > "${WORKDIR}"/"${FLPRODUCT}".sh;
	chmod 755 "${WORKDIR}"/"${FLPRODUCT}".sh;
	mv "${WORKDIR}"/"${FLPRODUCT}".sh "${INSTALLDIR}"/
}

createControlPanel() {
	getScriptTemplate "controlPanel-Template.sh";
	printf "%s\n" "$(apply_shell_expansion "${WORKDIR}/controlPanel-Template.sh")" > "${WORKDIR}"/controlPanel.sh;
	chmod 755 "${WORKDIR}"/controlPanel.sh;
	mv "${WORKDIR}"/controlPanel.sh "${INSTALLDIR}"/
}

create_starting_scripts() {
	verbose && echo "Creating starting scripts for ${FLPRODUCT}Bible 64 bits…"
	createLauncher;
	createControlPanel;
}

createConfig() {
	cat > "${HOME}/.config/Logos_on_Linux/Logos_on_Linux.conf" << EOF
# INSTALL OPTIONS
FLPRODUCT="${FLPRODUCT}"
FLPRODUCTi="${FLPRODUCTi}"
TARGETVERSION="${TARGETVERSION}"
INSTALLDIR="${INSTALLDIR}"
APPDIR="${APPDIR}"
APPDIR_BINDIR="${APPDIR_BINDIR}"
WINETRICKSBIN="${WINETRICKSBIN}"
WINEPREFIX="${WINEPREFIX}"
WINEBIN_CODE="${WINEBIN_CODE}"
WINE_EXE="${WINE_EXE}"
WINESERVER_EXE="${WINESERVER_EXE}"
WINE64_APPIMAGE_FULL_URL="${WINE64_APPIMAGE_FULL_URL}"
WINE64_APPIMAGE_FULL_FILENAME="${WINE64_APPIMAGE_FULL_FILENAME}"
APPIMAGE_LINK_SELECTION_NAME="${APPIMAGE_LINK_SELECTION_NAME}"
LOGOS_EXECUTABLE="${LOGOS_EXECUTABLE}"
LOGOS_EXE="${LOGOS_EXE}"
LOGOS_DIR="$(dirname "${LOGOS_EXE}")"

# RUN OPTIONS
LOGS="DISABLED"

# RESTORE OPTIONS
BACKUPDIR=""
EOF
}

postInstall() {
	if [ -f "${LOGOS_EXE}" ]; then
		logos_info "${FLPRODUCT} Bible ${TARGETVERSION} installed!"
		if [ -z "$LOGOS_CONFIG" ] && [ ! -f "${DEFAULT_CONFIG_PATH}" ]; then
			mkdir -p "${HOME}/.config/Logos_on_Linux";
			if [ -d "${HOME/.config/Logos_on_Linux}" ]; then
				createConfig;
				logos_info "A config file was created at ${DEFAULT_CONFIG_PATH}.";
			else
				logos_warn "${HOME}/.config/Logos_on_Linux does not exist. Failed to create config file."
			fi
		elif [ -z "$LOGOS_CONFIG" ] && [ -f "${DEFAULT_CONFIG_PATH}" ]; then
			if logos_acknowledge_question "The script found a config file at ${DEFAULT_CONFIG_PATH}. Should the script overwrite the existing config?" "The existing config file was not overwritten."; then
				if [ -d "${HOME/.config/Logos_on_Linux}" ]; then
					createConfig;
				else
					logos_warn "${HOME}/.config/Logos_on_Linux does not exist. Failed to create config file."
				fi
			fi
		else
			# Script was run with a config file. Skip modifying the config.
			:
		fi

		if logos_acknowledge_question "A launch script has been placed in ${INSTALLDIR} for your use. The script's name is ${FLPRODUCT}.sh.\n\nDo you want to run it now?\n\nNOTE: There may be an error on first execution. You can close the error dialog." "The Script has finished. Exiting…"; then
			"${INSTALLDIR}"/"${FLPRODUCT}".sh
		else verbose && echo "The script has finished. Exiting…";
		fi
	else
		logos_error "Installation failed. ${LOGOS_EXE} not found. Exiting…\n\nThe ${FLPRODUCT} executable was not found. This means something went wrong while installing ${FLPRODUCT}. Please contact the Logos on Linux community for help."
	fi
}

main() {
	{ echo "$LOGOS_SCRIPT_TITLE, $LOGOS_SCRIPT_VERSION by $LOGOS_SCRIPT_AUTHOR.";
	# BEGIN PREPARATION
	verbose && date; checkDependencies; # We verify the user is running a graphical UI and has majority of required dependencies.
	verbose && date; chooseProduct; # We ask user for his Faithlife product's name and set variables.
	verbose && date; chooseVersion; # We ask user for his Faithlife product's version, set variables, and create project skeleton.
	verbose && date; chooseInstallMethod; # We ask user for his desired install method.
	# END PREPARATION
	if [ -z "${REGENERATE}" ]; then
		verbose && date; checkExistingInstall;
		verbose && date; beginInstall;
		verbose && date; prepareWineBottle; # We run wineboot.
		case "${TARGETVERSION}" in
			10*)
				verbose && date; installLogos10; ;; # We run the commands specific to Logos 10.
			9*)
				verbose && date; installLogos9; ;; # We run the commands specific to Logos 9.
			*)
				logos_error "Installation canceled!" ;;
		esac

		verbose && date;
		create_starting_scripts;
		heavy_wineserver_wait;
		clean_all;

		LOGOS_EXE=$(find "${WINEPREFIX}" -name ${FLPRODUCT}.exe | grep "${FLPRODUCT}/${FLPRODUCT}.exe"); export LOGOS_EXE;

		verbose && date; postInstall;
	else
		create_starting_scripts;
		logos_info "The scripts have been regenerated."
	fi
	} | tee -a "${LOGOS_LOG}";
}
# END FUNCTION DECLARATIONS

# BEGIN SCRIPT EXECUTION
if [ -z "${DIALOG}" ]; then
	getDialog;
	if test "${GUI}" == "true"; then
		echo "Running in a GUI. Enabling logging." >> "${LOGOS_LOG}"
		setDebug;
	fi
fi

die-if-running;
die-if-root;

# BEGIN OPTARGS
RESET_OPTARGS=true
for arg in "$@"
do
	if [ -n "$RESET_OPTARGS" ]; then
	  unset RESET_OPTARGS
	  set -- 
	fi
	case "$arg" in # Relate long options to short options
		--help)					set -- "$@" -h ;;
		--version)				set -- "$@" -v ;;
		--verbose)				set -- "$@" -V ;;
		--config)				set -- "$@" -c ;;
		--skip-fonts)			set -- "$@" -F ;;
		--regenerate-scripts)	set -- "$@" -r ;;
		--force-root)			set -- "$@" -f ;;
		--debug)				set -- "$@" -D ;;
        --make-skel)			set -- "$@" -k ;;
		--custom-binary-path)	set -- "$@" -b ;;
		*)						set -- "$@" "$arg" ;;
	esac
done
OPTSTRING=':hvVcDfFrkb:' # Available options

# First loop: set variable options which may affect other options
while getopts "$OPTSTRING" opt; do
	case $opt in
		c)
			NEXTOPT="${!OPTIND}"
			if [[ -n "$NEXTOPT" && "$NEXTOPT" != "-*" ]]; then
				OPTIND=$((OPTIND + 1))
				if [ -f "$NEXTOPT" ]; then
					OPTIND=$(( OPTIND + 1 ))
					echo "${NEXTOPT}"
					LOGOS_CONFIG="${NEXTOPT}"
					export LOGOS_CONFIG;
					set -a
					# shellcheck disable=SC1090
					source "$LOGOS_CONFIG";
					set +a
				else
					logos_info "$LOGOS_SCRIPT_TITLE: -$OPTARG: Invalid config file path." >&2 && usage >&2 && exit;
				fi
			elif [ -f "$HOME/.config/Logos_on_Linux/Logos_on_Linux.conf" ]; then
				LOGOS_CONFIG="$HOME/.config/Logos_on_Linux/Logos_on_Linux.conf"
				export LOGOS_CONFIG
				set -a
				# shellcheck disable=SC1090
				source "$LOGOS_CONFIG";
				set +a
			else
				logos_info "No config file found."
			fi
			;;
		V)  export VERBOSE="true" ;;
		F)  export SKIP_FONTS="1" ;;
		f)  export LOGOS_FORCE_ROOT="1"; ;;
		r)  export REGENERATE="1"; ;;
		D)  export setDebug;
			;;
		k)  export SKEL="1"; ;;
		b)  CUSTOMBINPATH="$2";
			if [ -d "$CUSTOMBINPATH" ]; then
				export CUSTOMBINPATH;
			else
				logos_info "$LOGOS_SCRIPT_TITLE: User supplied path: \"${OPTARG}\". Custom binary path does not exist." >&2 && usage >&2 && exit 
			fi; shift 2 ;;
		\?) logos_info "$LOGOS_SCRIPT_TITLE: -$OPTARG: undefined option." >&2 && usage >&2 && exit ;;
		:)  logos_info "$LOGOS_SCRIPT_TITLE: -$OPTARG: missing argument." >&2 && usage >&2 && exit ;;
	esac
done
OPTIND=1 # Reset the index.

# Second loop: determine user action
while getopts "$OPTSTRING" opt; do
	case $opt in
		h)  usage && exit ;;
		v)  logos_info "$LOGOS_SCRIPT_TITLE, $LOGOS_SCRIPT_VERSION by $LOGOS_SCRIPT_AUTHOR." && exit ;;
		\?) logos_info "$LOGOS_SCRIPT_TITLE: -$OPTARG: undefined option." >&2 && usage >&2 && exit ;;
		:)  logos_info "$LOGOS_SCRIPT_TITLE: -$OPTARG: missing argument." >&2 && usage >&2 && exit ;;
	esac
done
# If no options passed.
if [ "${OPTIND}" -eq '1' ]; then
		:
fi
shift $((OPTIND-1))
# END OPTARGS

main;

exit 0;
# END SCRIPT EXECUTION

