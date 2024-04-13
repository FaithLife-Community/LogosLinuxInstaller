[![GitHub All Releases](https://img.shields.io/github/downloads/FaithLife-Community/LogosLinuxInstaller/total.svg)]()
[![Codacy Badge](https://api.codacy.com/project/badge/Grade/f730f74748c348cb9b3ff2fa1654c84b)](https://app.codacy.com/manual/FaithLife-Community/LogosLinuxInstaller?utm_source=github.com&utm_medium=referral&utm_content=FaithLife-Community/LogosLinuxInstaller&utm_campaign=Badge_Grade_Dashboard)
[![Automation testing](https://img.shields.io/badge/Automation-testing-sucess)](https://github.com/FaithLife-Community/LogosLinuxInstallTests) [![Installer LogosBible](https://img.shields.io/badge/Installer-LogosBible-blue)](https://www.logos.com) [![LastRelease](https://img.shields.io/github/v/release/FaithLife-Community/LogosLinuxInstaller)](https://github.com/FaithLife-Community/LogosLinuxInstaller/releases)

# Install Logos Bible Software on Linux

This repository contains a Python program for installing and maintaining FaithLife's Logos Bible (Verbum) Software on Linux.

This program is created and maintained by the FaithLife Community and is licensed under the MIT License.

## Logos Linux Installer

The main program is a distributable executable and contains Python itself and all necessary Python packages.

When running the program, it will attempt to determine your operating system and package manager.
It will then attempt to install all needed system dependencies during the install of Logos.
When the install is finished, it will place two shortcuts on your computer: one will launch Logos directly; the other will launch the Control Panel.

To access the GUI version of the program, double click the executable in your file browser or on your desktop, and then follow the prompts.

The program can also be run from source and should be run from a Python virtual environment.
See below.

By default the program installs Logos, but you can pass the `-C|--control-panel` optarg to access the Control Panel, which allows you to install Logos or do various maintenance functions on your install.
In time, you should be able to use the program to restore a backup.

```
Usage: ./LogosLinuxInstaller.sh
Installs ${FLPRODUCT} Bible Software with Wine on Linux.

Options:
    -h   --help                 Prints this help message and exit.
    -v   --version              Prints version information and exit.
    -V   --verbose              Enable extra CLI verbosity.
    -D   --debug                Makes Wine print out additional info.
    -C   --control-panel        Open the Control Panel app.
    -c   --config               Use the Logos on Linux config file when
                                setting environment variables. Defaults to:
                                \$HOME/.config/Logos_on_Linux/Logos_on_Linux.conf
                                Optionally can accept a config file provided by
                                the user.
    -b   --custom-binary-path   Set a custom path to search for wine binaries
                                during the install.
    -F   --skip-fonts           Skips installing corefonts and tahoma.
    -s   --shortcut			    Create or update the Logos shortcut, located in
                                HOME/.local/share/applications.
    -d   --dirlink              Create a symlink to the Windows Logos directory
                                in your Logos on Linux install dir.
                                The symlink's name will be 'installation_dir'.
    -e   --edit-config          Edit the Logos on Linux config file.
    -i   --indexing             Run the Logos indexer in the
                                background.
    --remove-all-index          Removes all index and library catalog files.
    --remove-library-catalog    Removes all library catalog files.
    -l   --logs                 Turn Logos logs on or off.
    -L   --delete-install-log   Delete the installation log file.
    -R   --check-resources      Check Logos's resource usage while running.
    -b   --backup               Saves Logos data to the config's
                                backup location.
    -r   --restore              Restores Logos data from the config's
                                backup location.
    -f   --force-root           Sets LOGOS_FORCE_ROOT to true, which permits
                                the root user to run the script.
    -P   --passive              Install Logos non-interactively .
    -k   --make-skel            Make a skeleton install only.
```

## Installation

This section is a WIP.

You can either run the program from the CLI for a CLI-only install, or you can double click the icon in your file browser or on your desktop for a GUI install. Then, follow the prompts.

## Installing/running from Source

You can clone the repo and install the app from source. To do so, you will need to ensure a few prerequisites:
1. Install Python 3.12 and Tcl/Tk
1. Clone this repository
1. Set up a virtual environment

### Install Python 3.12 and Tcl/Tk
Your system might already include Python 3.12 built with Tcl/Tk. This will verify
the installation:
```
$ python3 --version
Python 3.12.1
$ python3 -m tkinter # should open a basic Tk window
```
If your Python version is < 3.12, then you might want to install 3.12 and tcl/tk using
your system's package manager or compile it from source using the following guide 
or the script provided in `scripts/ensure-python.sh`. This is because the app is
built using 3.12 and might have errors if run with other versions.
```
# install build dependencies; e.g. for debian-based systems:
$ apt install build-essential tcl-dev tk-dev libreadline-dev
# install & build python 3.12
$ wget 'https://www.python.org/ftp/python/3.12.1/Python-3.12.1.tar.xz'
$ tar xf Python-3.12.1.tar.xz
$ cd Python-3.12.1
Python-3.12.1$ ./configure --prefix=/opt --enable-shared
Python-3.12.1$ make
Python-3.12.1$ sudo make install
Python-3.12.1$ LD_LIBRARY_PATH=/opt/lib /opt/bin/python3.12 --version
Python 3.12.1
```
The script `scripts/ensure-python.sh` is not yet fully tested. Feedback is welcome!
Both methods install python into /opt to avoid interfering with system python installations.

### Clone this repository
```
$ git clone 'https://github.com/FaithLife-Community/LogosLinuxInstaller.git'
$ cd LogosLinuxInstaller
LogosLinuxInstaller$
```

### Set up and use a virtual environment
Use the following guide or the provided script at `scripts/ensure-venv.sh` to set
up a virtual environment for running and/or building locally.
```
LogosLinuxInstaller$ LD_LIBRARY_PATH=/opt/lib /opt/bin/python3.12 -m venv env # create a virtual env folder called "env" using python3.12's path
LogosLinuxInstaller$ echo "LD_LIBRARY_PATH=/opt/lib" >> env/bin/activate # tell python where to find libs
LogosLinuxInstaller$ echo "export LD_LIBRARY_PATH" >> env/bin/activate
LogosLinuxInstaller$ source env/bin/activate # activate the env
(env) LogosLinuxInstaller$ python --version # verify python version
Python 3.12.1
(env) LogosLinuxInstaller$ python -m tkinter # verify that tkinter test window opens
(env) LogosLinuxInstaller$ pip install -r requirements.txt # install python packages
(env) LogosLinuxInstaller$ ./LogosLinuxInstaller.py --help # run the script
```

## Install Guide

For an install guide with pictures and video, see the wiki's [Install Guide](https://github.com/FaithLife-Community/LogosLinuxInstaller/wiki/Install-Guide).

NOTE: You can run Logos on Linux using the Steam Proton Experimental binary, which often has the latest and greatest updates to make Logos run even smoother. The script should be able to find the binary automatically, unless your Steam install is located outside of your HOME directory.

If you want to install your distro's dependencies outside of the script, please see the following.

NOTE: The following section is WIP.

## Debian and Ubuntu

### Install Dependencies

```
sudo apt install coreutils patch lsof wget findutils sed grep gawk winbind cabextract x11-apps bc binutils
```

If using wine from a repo, you must install wine staging. Run:

```
sudo dpkg --add-architecture i386
sudo mkdir -pm755 /etc/apt/keyrings
sudo wget -O /etc/apt/keyrings/winehq-archive.key https://dl.winehq.org/wine-builds/winehq.key
CODENAME=$(lsb_release -a | grep Codename | awk '{print $2}')
sudo wget -NP /etc/apt/sources.list.d/ https://dl.winehq.org/wine-builds/ubuntu/dists/"${CODENAME}"/winehq-"${CODENAME}".sources
sudo apt update
sudo apt install --install-recommends winehq-staging
```

See https://wiki.winehq.org/Ubuntu for help.

If using the AppImage, run:

```
sudo apt install fuse3
```

## Arch

### Install Dependencies

```
sudo pacman -S patch lsof wget sed grep gawk cabextract samba bc
```

If using wine from a repo, run:

```
sudo pacman -S wine
```

### Manjaro

#### Install Dependencies

```
sudo pamac install patch lsof wget sed grep gawk cabextract samba bc 
```

If using wine from a repo, run:

```
sudo pamac install wine
```

You may need to install pamac if you are not using Manjaro GNOME:

```
sudo pacman -S pamac-cli
```

### Steamdeck

The steam deck has a locked down filesystem. There are some missing dependencies which cause irregular crashes in Logos. These can be installed following this sequence:

1. Enter Desktop Mode
2. Use `passwd` to create a password for the deck user, unless you already did this.
3. Disable read-only mode: `sudo steamos-readonly disable`
4. Initialize pacman keyring: `sudo pacman-key --init`
5. Populate pacman keyring with the default Arch Linux keys: `sudo pacman-key --populate archlinux`
6. Get package lists: `sudo pacman -Fy`
7. Fix locale issues `sudo pacman -Syu glibc`
8. then `sudo locale-gen` 
9. Install dependencies: `sudo pacman -S samba winbind cabextract appmenu-gtk-module patch bc lib32-libjpeg-turbo`

Packages you install may be overwritten by the next Steam OS update, but you can easily reinstall them if that happens.

After these steps you can go ahead and run the your install script.

## RPM

### Install Dependencies

```
sudo dnf install patch mod_auth_ntlm_winbind samba-winbind cabextract bc samba-winbind-clients
```

If using wine from a repo, run:

```
sudo dnf install winehq-staging
```

If using the AppImage, run:

```
sudo dnf install fuse3
```

### CentOS

### Install Dependencies

```
sudo yum install patch mod_auth_ntlm_winbind samba-winbind cabextract bc 
```

If using wine from a repo, run:

```
sudo yum install winehq-staging
```

If using the AppImage, run:

```
sudo yum install fuse3
```

## OpenSuse

TODO

```
sudo zypper install …
```

## Alpine

TODO

```
sudo apk add …
```

## BSD

TODO. 

```
doas pkg install …
```

## ChromeOS

TODO.
