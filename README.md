[![GitHub All Releases](https://img.shields.io/github/downloads/FaithLife-Community/LogosLinuxInstaller/total.svg)]()
[![Codacy Badge](https://api.codacy.com/project/badge/Grade/f730f74748c348cb9b3ff2fa1654c84b)](https://app.codacy.com/manual/FaithLife-Community/LogosLinuxInstaller?utm_source=github.com&utm_medium=referral&utm_content=FaithLife-Community/LogosLinuxInstaller&utm_campaign=Badge_Grade_Dashboard)
[![Automation testing](https://img.shields.io/badge/Automation-testing-sucess)](https://github.com/FaithLife-Community/LogosLinuxInstallTests) [![Installer LogosBible](https://img.shields.io/badge/Installer-LogosBible-blue)](https://www.logos.com) [![LastRelease](https://img.shields.io/github/v/release/FaithLife-Community/LogosLinuxInstaller)](https://github.com/FaithLife-Community/LogosLinuxInstaller/releases)

# Ou Dedetai

>Remember Jesus Christ, risen from the dead, the offspring of David, as preached in my gospel, for which I am suffering, bound with chains as a criminal. **But the word of God is not bound!**  
ἀλλʼ **ὁ λόγος** τοῦ θεοῦ **οὐ δέδεται**
>
> Second Timothy 2:8–9, ESV

## Manages Logos Bible Software via Wine

This repository contains a Python program for installing and maintaining [FaithLife](https://faithlife.com/)'s [Logos Bible (Verbum) Software](https://www.logos.com/) via [Wine](https://www.winehq.org/).

This program is created and maintained by the FaithLife Community and is licensed under the MIT License.


## oudedetai binary

The main program is a distributable executable binary and contains Python itself and all necessary Python packages.

When running the program, it will attempt to determine your operating system and package manager.
It will then attempt to install all needed system dependencies during the installation of Logos.
When the installation is finished, it will place two shortcuts on your computer: one will launch Logos directly; the other will launch the Control Panel.

To access the GUI version of the program, double-click the executable in your file browser or on your desktop, and then follow the prompts.

The program can also be run from source and should be run from a Python virtual environment.
See below.

## Install Guide (for users)

For an installation guide with pictures and video, see the wiki's [Install Guide](https://github.com/FaithLife-Community/LogosLinuxInstaller/wiki/Install-Guide).

## Installing/running from Source (for developers)

You can clone the repo and install the app from source. To do so, you will need to ensure a few prerequisites:
1. Install build dependencies
2. Clone this repository
3. Build/install Python 3.12 and Tcl/Tk
4. Set up a virtual environment

### Install build dependencies

e.g. for debian-based systems:
```
sudo apt-get install git build-essential gdb lcov pkg-config \
    libbz2-dev libffi-dev libgdbm-dev libgdbm-compat-dev liblzma-dev \
    libncurses5-dev libreadline6-dev libsqlite3-dev libssl-dev \
    lzma lzma-dev python3-tk tk-dev uuid-dev zlib1g-dev
```
*See Python's [Build dependencies](https://devguide.python.org/getting-started/setup-building/index.html#build-dependencies) section for further info.*

### Clone this repository
```
git clone 'https://github.com/FaithLife-Community/LogosLinuxInstaller.git'
```

### Install Python 3.12 and Tcl/Tk
Your system might already include Python 3.12 built with Tcl/Tk. This will verify
the installation:
```
$ python3 --version
Python 3.12.5
$ python3 -m tkinter # should open a basic Tk window
```
If your Python version is < 3.12, then you might want to install 3.12 and tcl/tk
using your system's package manager or compile it from source using the
following guide or the script provided in `scripts/ensure-python.sh`. This is
because the app is built using 3.12 and might have errors if run with other
versions.

**Install & build python 3.12 using the script:**
```
./LogosLinuxInstaller/scripts/ensure-python.sh
```

**Install & build python 3.12 manually:**
```
$ ver=$(wget -qO- https://www.python.org/ftp/python/ | grep -oE '3\.12\.[0-9]+' | sort -u | tail -n1)
$ wget "https://www.python.org/ftp/python/${ver}/Python-${ver}.tar.xz"
$ tar xf Python-${ver}.tar.xz
$ cd Python-${ver}
Python-3.12$ ./configure --prefix=/opt --enable-shared
Python-3.12$ make
Python-3.12$ sudo make install
Python-3.12$ LD_LIBRARY_PATH=/opt/lib /opt/bin/python3.12 --version
Python 3.12.5
$ cd ~
```
Both methods install python into `/opt` to avoid interfering with system python installations.

### Enter the repository folder
```
$ cd LogosLinuxInstaller
LogosLinuxInstaller$
```

### Set up and use a virtual environment
Use the following guide or the provided script at `scripts/ensure-venv.sh` to set
up a virtual environment for running and/or building locally.

**Using the script:**
```
./scripts/ensure-venv.sh
```

**Manual setup:**

```
LogosLinuxInstaller$ LD_LIBRARY_PATH=/opt/lib /opt/bin/python3.12 -m venv env # create a virtual env folder called "env" using python3.12's path
LogosLinuxInstaller$ echo "LD_LIBRARY_PATH=/opt/lib" >> env/bin/activate # tell python where to find libs
LogosLinuxInstaller$ echo "export LD_LIBRARY_PATH" >> env/bin/activate
LogosLinuxInstaller$ source env/bin/activate # activate the env
(env) LogosLinuxInstaller$ python --version # verify python version
Python 3.12.5
(env) LogosLinuxInstaller$ python -m tkinter # verify that tkinter test window opens
(env) LogosLinuxInstaller$ pip install -r requirements.txt # install python packages
(env) LogosLinuxInstaller$ ./main.py --help # run the script
```

### Building using docker

```
$ git clone 'https://github.com/FaithLife-Community/LogosLinuxInstaller.git'
$ cd LogosLinuxInstaller
# docker build -t logosinstaller .
# docker run --rm -v $(pwd):/usr/src/app logosinstaller
```

The built binary will now be in `./dist/oudedetai`.

## Install guide (possibly outdated)

NOTE: You can run **Ou Dedetai** using the Steam Proton Experimental binary, which often has the latest and greatest updates to make Logos run even smoother. The script should be able to find the binary automatically, unless your Steam install is located outside of your HOME directory.

If you want to install your distro's dependencies outside of the script, please see the [System Dependencies wiki page](https://github.com/FaithLife-Community/LogosLinuxInstaller/wiki/System-Dependencies).

