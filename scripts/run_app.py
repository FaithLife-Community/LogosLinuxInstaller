#!/usr/bin/env python3
"""
This script is needed so that PyInstaller can refer to a script that does not
use relative imports.
https://github.com/pyinstaller/pyinstaller/issues/2560
"""
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1]))
import ou_dedetai.main  # noqa: E402
if __name__ == '__main__':
    sys.argv[0] = re.sub(r'(-script\.pyw|\.exe)?$', '', sys.argv[0])
    sys.exit(ou_dedetai.main.main())
