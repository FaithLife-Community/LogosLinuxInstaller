#!/usr/bin/env python3
"""
This script is needed so that PyInstaller can refer to a script that does not
use relative imports.
https://github.com/pyinstaller/pyinstaller/issues/2560
"""
import re
import sys
import ou_dedetai.main
if __name__ == '__main__':
    sys.argv[0] = re.sub(r'(-script\.pyw|\.exe)?$', '', sys.argv[0])
    sys.exit(ou_dedetai.main.main())
