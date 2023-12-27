from tkinter import BooleanVar
from tkinter import font
from tkinter import IntVar
from tkinter import StringVar
from tkinter.ttk import Button
from tkinter.ttk import Checkbutton
from tkinter.ttk import Combobox
from tkinter.ttk import Frame
from tkinter.ttk import Label
from tkinter.ttk import Progressbar
from tkinter.ttk import Separator

import config
from utils import get_system_winetricks

class InstallerGui(Frame):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.italic = font.Font(slant='italic')
        self.config(padding=5)
        self.grid(row=0, column=0, sticky='nwes')

        # Initialize vars from ENV.
        self.flproduct = config.FLPRODUCT
        self.targetversion = config.TARGETVERSION
        self.logos_release_version = config.LOGOS_RELEASE_VERSION
        self.default_config_path = config.DEFAULT_CONFIG_PATH
        self.config_file = config.CONFIG_FILE
        if self.config_file is None:
            self.config_file = 'Default'
        self.winetricksbin = config.WINETRICKSBIN
        if self.winetricksbin is None:
            self.sys_winetricks = get_system_winetricks()
            if self.sys_winetricks is not None and self.sys_winetricks[1] >= 20220411:
                self.winetricksbin = f'System (v{self.sys_winetricks[1]})'
        self.skip_fonts = config.SKIP_FONTS
        if self.skip_fonts is None:
            self.skip_fonts = 0

        # Config File row.
        self.config_label = Label(self, text="Config file: ")
        self.config_filechooser = Button(self,
            text=self.config_file if self.config_file is not None else "Choose file...",
        )

        # Product/Version row.
        self.product_label = Label(self, text="Product & Version: ")
        # product drop-down menu
        self.productvar = StringVar()
        self.product_dropdown = Combobox(self, textvariable=self.productvar)
        self.product_dropdown.state(['readonly'])
        self.product_dropdown['values'] = ('Logos', 'Verbum')
        if self.flproduct in self.product_dropdown['values']:
            self.product_dropdown.set(self.flproduct)
        # version drop-down menu
        self.versionvar = StringVar()
        self.version_dropdown = Combobox(self, width=5, textvariable=self.versionvar)
        self.version_dropdown.state(['readonly'])
        self.version_dropdown['values'] = ('9', '10')
        if self.targetversion in self.version_dropdown['values']:
            self.version_dropdown.set(self.targetversion)

        # Release row.
        self.release_label = Label(self, text="Release: ")
        # release drop-down menu
        self.releasevar = StringVar()
        self.release_dropdown = Combobox(self, textvariable=self.releasevar)
        self.release_dropdown.state(['readonly'])
        self.release_dropdown['values'] = [] if self.logos_release_version is None else [self.logos_release_version]
        # release check button
        self.release_check_button = Button(self, text="Get Release list")
        self.release_check_button.state(['disabled'])

        # Custom binary row.
        self.bin_label = Label(self, text="Wine exe custom folder: ")
        self.bin_filechooser = Button(self, text="Choose folder...")

        # Wine row.
        self.wine_label = Label(self, text="Wine exe: ")
        self.winevar = StringVar()
        self.wine_dropdown = Combobox(self, textvariable=self.winevar, width=45)
        self.wine_dropdown.state(['readonly'])
        self.wine_dropdown['values'] = []
        self.wine_check_button = Button(self, text="Get exe list")
        self.wine_check_button.state(['disabled'])

        # Winetricks row.
        self.tricks_label = Label(self, text="Winetricks: ")
        self.tricksvar = StringVar()
        self.tricks_dropdown = Combobox(self, textvariable=self.tricksvar)
        self.tricks_dropdown.state(['readonly'])
        values = ['Download']
        if self.winetricksbin is not None:
            values.insert(0, self.winetricksbin)
        self.tricks_dropdown['values'] = values
        self.tricksvar.set(self.tricks_dropdown['values'][0])

        # Fonts row.
        self.fonts_label = Label(self, text="Install fonts: ")
        self.fontsvar = BooleanVar(value=1-self.skip_fonts)
        self.fonts_checkbox = Checkbutton(self, variable=self.fontsvar)

        # Cancel/Okay buttons row.
        self.cancel_button = Button(self, text="Cancel")
        self.okay_button = Button(self, text="Install")
        self.okay_button.state(['disabled'])

        # Status area.
        self.messagevar = StringVar()
        # self.messagevar.set("Choose Product and Version")
        self.message_label = Label(self,
            textvariable=self.messagevar,
            font=self.italic,
        )
        self.statusvar = StringVar()
        self.status_label = Label(self, textvariable=self.statusvar)
        self.progressvar = IntVar()
        self.progress = Progressbar(self, variable=self.progressvar)

        # Place widgets.
        self.config_label.grid(
            column=0,
            row=0,
            sticky='w',
            pady=2,
        )
        self.config_filechooser.grid(
            column=1,
            columnspan=4,
            row=0,
            sticky='we',
            pady=2,
        )
        self.product_label.grid(
            column=0,
            row=1,
            sticky='nws',
            pady=2,
        )
        self.product_dropdown.grid(
            column=1,
            row=1,
            sticky='w',
            pady=2,
        )
        self.version_dropdown.grid(
            column=2,
            row=1,
            sticky='w',
            pady=2,
        )
        self.release_label.grid(
            column=0,
            row=2,
            sticky='w',
            pady=2,            
        )
        self.release_dropdown.grid(
            column=1,
            row=2,
            sticky='w',
            pady=2,
        )
        self.release_check_button.grid(
            column=2,
            row=2,
            sticky='w',
            pady=2,
        )
        self.bin_label.grid(
            column=0,
            row=3,
            sticky='nws',
            pady=2,
        )
        self.bin_filechooser.grid(
            column=1,
            row=3,
            sticky='we',
            pady=2,
        )
        self.wine_label.grid(
            column=0,
            row=4,
            sticky='w',
            pady=2,
        )
        self.wine_dropdown.grid(
            column=1,
            row=4,
            columnspan=3,
            sticky='we',
            pady=2,
        )
        self.wine_check_button.grid(
            column=4,
            row=4,
            sticky='e',
            pady=2,
        )
        self.tricks_label.grid(
            column=0,
            row=5,
            sticky='w',
            pady=2,
        )
        self.tricks_dropdown.grid(
            column=1,
            row=5,
            sticky='we',
            pady=2,
        )
        self.fonts_label.grid(
            column=0,
            row=6,
            sticky='nws',
            pady=2,
        )
        self.fonts_checkbox.grid(
            column=1,
            row=6,
            sticky='w',
            pady=2,
        )
        self.cancel_button.grid(
            column=3,
            row=7,
            sticky='e',
            pady=2,
        )
        self.okay_button.grid(
            column=4,
            row=7,
            sticky='e',
            pady=2,
        )
        self.message_label.grid(
            column=0,
            row=7,
            columnspan=3,
            sticky='w',
            pady=2,
        )
        self.status_label.grid(
            column=0,
            row=8,
            columnspan=5,
            sticky='w',
            pady=2,
        )
        self.progress.grid(
            column=0,
            row=9,
            columnspan=5,
            sticky='we',
            pady=2,
        )

class ControlGui(Frame):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.config(padding=5)
        self.grid(row=0, column=0, sticky='nwes')

        # Initialize vars from ENV.
        self.installdir = config.INSTALLDIR
        self.flproduct = config.FLPRODUCT
        self.targetversion = config.TARGETVERSION
        self.logos_release_version = config.LOGOS_RELEASE_VERSION
        self.logs = config.LOGS
        self.config_file = config.CONFIG_FILE

        # INSTALLDIR file_chooser
        self.installdir_label = Label(self, text="Installation folder: ")
        self.installdir_filechooser = Button(self, text="Choose folder...")
        # Run app button
        self.run_label = Label(self, text=f"Run app")
        self.run_button = Button(self, text="Run")
        # Check resources button
        self.check_label = Label(self, text="Check resources")
        self.check_button = Button(self, text="Check")
        # Remove indexes button
        self.indexes_label = Label(self, text="Remove indexes")
        self.indexes_button = Button(self, text="Remove")
        # App logging toggle
        self.loggingstatevar = StringVar(value='Enable')
        self.logging_label = Label(self, text="Toggle app logging")
        self.logging_button = Button(self, textvariable=self.loggingstatevar)
        # Edit config button
        self.config_label = Label(self, text="Edit config file")
        self.config_button = Button(self, text="Edit ...")
        # Reinstall deps button
        self.deps_label = Label(self, text="Reinstall dependencies")
        self.deps_button = Button(self, text="Reinstall")
        # Separator
        self.separator = Separator(self, orient='horizontal')
        # Status message label
        self.messagevar = StringVar()
        self.message_label = Label(self, textvariable=self.messagevar)
        # Progress bar
        # self.progressvar = IntVar(value=0)
        self.progress = Progressbar(self, mode='indeterminate', orient='horizontal')
        self.progress.state(['disabled'])

        # Place widgets.
        self.installdir_label.grid(
            column=0,
            row=0,
            sticky='w',
            padx=2,
            pady=2,
        )
        self.installdir_filechooser.grid(
            column=1,
            row=0,
            sticky='we',
            pady=2,
        )
        self.run_label.grid(
            column=0,
            row=1,
            sticky='w',
            padx=2,
            pady=2,
        )
        self.run_button.grid(
            column=1,
            row=1,
            sticky='w',
            pady=2,
        )
        self.check_label.grid(
            column=0,
            row=2,
            sticky='w',
            padx=2,
            pady=2,
        )
        self.check_button.grid(
            column=1,
            row=2,
            sticky='w',
            pady=2,
        )
        self.indexes_label.grid(
            column=0,
            row=3,
            sticky='w',
            padx=2,
            pady=2,
        )
        self.indexes_button.grid(
            column=1,
            row=3,
            sticky='w',
            pady=2,
        )
        self.logging_label.grid(
            column=0,
            row=4,
            sticky='w',
            padx=2,
            pady=2,
        )
        self.logging_button.grid(
            column=1,
            row=4,
            sticky='w',
            pady=2,
        )
        self.config_label.grid(
            column=0,
            row=5,
            sticky='w',
            padx=2,
            pady=2,
        )
        self.config_button.grid(
            column=1,
            row=5,
            sticky='w',
            pady=2,
        )
        self.deps_label.grid(
            column=0,
            row=6,
            sticky='w',
            padx=2,
            pady=2,
        )
        self.deps_button.grid(
            column=1,
            row=6,
            sticky='w',
            pady=2,
        )
        self.separator.grid(
            column=0,
            row=7,
            columnspan=2,
            sticky='we',
            pady=2,
        )
        self.message_label.grid(
            column=0,
            row=8,
            columnspan=2,
            sticky='we',
            pady=2
        )
        self.progress.grid(
            column=0,
            row=9,
            columnspan=2,
            sticky='we',
            pady=2
        )
