from tkinter import Toplevel
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
from tkinter.ttk import Radiobutton
from tkinter.ttk import Separator

import config
import utils


class InstallerGui(Frame):
    def __init__(self, root, **kwargs):
        super(InstallerGui, self).__init__(root, **kwargs)

        self.italic = font.Font(slant='italic')
        self.config(padding=5)
        self.grid(row=0, column=0, sticky='nwes')

        # Initialize vars from ENV.
        self.flproduct = config.FLPRODUCT
        self.targetversion = config.TARGETVERSION
        self.logos_release_version = config.LOGOS_RELEASE_VERSION
        self.default_config_path = config.DEFAULT_CONFIG_PATH
        self.winetricksbin = config.WINETRICKSBIN
        if self.winetricksbin is None:
            self.sys_winetricks = utils.get_system_winetricks()
            if self.sys_winetricks is not None and self.sys_winetricks[1] >= 20220411:
                self.winetricksbin = f'System (v{self.sys_winetricks[1]})'
        self.skip_fonts = config.SKIP_FONTS
        if self.skip_fonts is None:
            self.skip_fonts = 0
        self.skip_dependencies = config.SKIP_DEPENDENCIES
        if self.skip_fonts is None:
            self.skip_fonts = 0

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
        self.release_check_button = Button(self, text="Get Release List")
        self.release_check_button.state(['disabled'])

        # Wine row.
        self.wine_label = Label(self, text="Wine exe: ")
        self.winevar = StringVar()
        self.wine_dropdown = Combobox(self, textvariable=self.winevar)
        self.wine_dropdown.state(['readonly'])
        self.wine_dropdown['values'] = []
        self.wine_check_button = Button(self, text="Get EXE List")
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
        self.fonts_label = Label(self, text="Install Fonts: ")
        self.fontsvar = BooleanVar(value=1-self.skip_fonts)
        self.fonts_checkbox = Checkbutton(self, variable=self.fontsvar)

        # Skip Dependencies row.
        self.skipdeps_label = Label(self, text="Install Dependencies: ")
        self.skipdepsvar = BooleanVar(value=1-self.skip_dependencies)
        self.skipdeps_checkbox = Checkbutton(self, variable=self.skipdepsvar)

        # Cancel/Okay buttons row.
        self.cancel_button = Button(self, text="Cancel")
        self.okay_button = Button(self, text="Install")
        self.okay_button.state(['disabled'])

        # Status area.
        s1 = Separator(self, orient='horizontal')
        self.messagevar = StringVar()
        self.statusvar = StringVar()
        self.status_label = Label(self, textvariable=self.statusvar)
        self.progressvar = IntVar()
        self.progress = Progressbar(self, variable=self.progressvar)

        # Place widgets.
        self.product_label.grid(column=0, row=0, sticky='nws', pady=2)
        self.product_dropdown.grid(column=1, row=0, sticky='w', pady=2)
        self.version_dropdown.grid(column=2, row=0, sticky='w', pady=2)
        self.release_label.grid(column=0, row=1, sticky='w', pady=2)
        self.release_dropdown.grid(column=1, row=1, sticky='w', pady=2)
        self.release_check_button.grid(column=2, row=1, sticky='w', pady=2)
        self.wine_label.grid(column=0, row=2, sticky='w', pady=2)
        self.wine_dropdown.grid(column=1, row=2, columnspan=3, sticky='we', pady=2)
        self.wine_check_button.grid(column=4, row=2, sticky='e', pady=2)
        self.tricks_label.grid(column=0, row=3, sticky='w', pady=2)
        self.tricks_dropdown.grid(column=1, row=3, sticky='we', pady=2)
        self.fonts_label.grid(column=0, row=4, sticky='nws', pady=2)
        self.fonts_checkbox.grid(column=1, row=4, sticky='w', pady=2)
        self.skipdeps_label.grid(column=2, row=4, sticky='nws', pady=2)
        self.skipdeps_checkbox.grid(column=3, row=4, sticky='w', pady=2)
        self.cancel_button.grid(column=3, row=5, sticky='e', pady=2)
        self.okay_button.grid(column=4, row=5, sticky='e', pady=2)
        # Status area
        s1.grid(column=0, row=6, columnspan=5, sticky='we')
        self.status_label.grid(column=0, row=7, columnspan=5, sticky='w', pady=2)
        self.progress.grid(column=0, row=8, columnspan=5, sticky='we', pady=2)

class ControlGui(Frame):
    def __init__(self, root, *args, **kwargs):
        super(ControlGui, self).__init__(root, **kwargs)
        self.config(padding=5)
        self.grid(row=0, column=0, sticky='nwes')

        # Initialize vars from ENV.
        self.installdir = config.INSTALLDIR
        self.flproduct = config.FLPRODUCT
        self.targetversion = config.TARGETVERSION
        self.logos_release_version = config.LOGOS_RELEASE_VERSION
        self.logs = config.LOGS
        self.config_file = config.CONFIG_FILE

        # Run/install app button
        self.app_buttonvar = StringVar()
        self.app_buttonvar.set("Install")
        self.app_label = Label(self, text="FaithLife app") # FIXME: use app name if installed
        self.app_button = Button(self, textvariable=self.app_buttonvar) # or Install

        # Installed app actions
        # -> Run indexing, Remove library catalog, Remove all index files
        s1 = Separator(self, orient='horizontal')
        self.actionsvar = StringVar()
        self.actioncmd = None
        self.actions_label = Label(self, text="App actions: ")
        self.run_indexing_radio = Radiobutton(self,
            text="Run indexing", variable=self.actionsvar, value='run-indexing',
        )
        self.remove_library_catalog_radio = Radiobutton(self,
            text="Remove library catalog", variable=self.actionsvar, value='remove-library-catalog',
        )
        self.remove_index_files_radio = Radiobutton(self,
            text="Remove all index files", variable=self.actionsvar, value='remove-index-files',
        )
        self.actions_button = Button(self, text="Run action")
        self.actions_button.state(['disabled'])
        s2 = Separator(self, orient='horizontal')

        # Edit config button
        self.config_label = Label(self, text="Edit config file")
        self.config_button = Button(self, text="Edit …")
        # Install deps button
        self.deps_label = Label(self, text="Install dependencies")
        self.deps_button = Button(self, text="Install")
        # Backup/restore data buttons
        self.backups_label = Label(self, text="Backup/restore data")
        self.backup_button = Button(self, text="Backup")
        self.restore_button = Button(self, text="Restore")
        # AppImage buttons
        self.latest_appimage_label = Label(self, text="Update to Latest AppImage")
        self.latest_appimage_button = Button(self, text="Run")
        self.set_appimage_label = Label(self, text="Set AppImage")
        self.set_appimage_button = Button(self, text="Run")
        # Run winetricks
        self.winetricks_label = Label(self, text="Winetricks")
        self.run_winetricks_button = Button(self, text="Run")
        self.get_winetricks_button = Button(self, text="Download/Update")
        # App logging toggle
        self.loggingstatevar = StringVar(value='Enable')
        self.logging_label = Label(self, text="Toggle app logging")
        self.logging_button = Button(self, textvariable=self.loggingstatevar)
        # Separator
        s3 = Separator(self, orient='horizontal')
        # Status message label
        self.messagevar = StringVar()
        self.message_label = Label(self, textvariable=self.messagevar)
        # Progress bar
        self.progressvar = IntVar(value=0)
        self.progress = Progressbar(self, mode='indeterminate', orient='horizontal', variable=self.progressvar)
        self.progress.state(['disabled'])

        # Place widgets.
        self.app_label.grid(column=0, row=0, sticky='w', pady=2)
        self.app_button.grid(column=1, row=0, sticky='w', pady=2)

        s1.grid(column=0, row=1, columnspan=3, sticky='we')
        self.actions_label.grid(column=0, row=2, sticky='e', padx=20, pady=2)
        self.actions_button.grid(column=0, row=4, sticky='e', padx=20, pady=2)
        self.run_indexing_radio.grid(column=1, row=2, sticky='w', pady=2, columnspan=2)
        self.remove_library_catalog_radio.grid(column=1, row=3, sticky='w', pady=2, columnspan=2)
        self.remove_index_files_radio.grid(column=1, row=4, sticky='w', pady=2, columnspan=2)
        s2.grid(column=0, row=5, columnspan=3, sticky='we')
        
        self.config_label.grid(column=0, row=6, sticky='w', pady=2)
        self.config_button.grid(column=1, row=6, sticky='w', pady=2)

        self.deps_label.grid(column=0, row=7, sticky='w', pady=2)
        self.deps_button.grid(column=1, row=7, sticky='w', pady=2)

        self.backups_label.grid(column=0, row=8, sticky='w', pady=2)
        self.backup_button.grid(column=1, row=8, sticky='w', pady=2)
        self.restore_button.grid(column=2, row=8, sticky='w', pady=2)

        self.latest_appimage_label.grid(column=0, row=9, sticky='w', pady=2)
        self.latest_appimage_button.grid(column=1, row=9, sticky='w', pady=2)

        self.set_appimage_label.grid(column=0, row=10, sticky='w', pady=2)
        self.set_appimage_button.grid(column=1, row=10, sticky='w', pady=2)

        self.winetricks_label.grid(column=0, row=11, sticky='w', pady=2)
        self.run_winetricks_button.grid(column=1, row=11, sticky='w', pady=2)
        self.get_winetricks_button.grid(column=2, row=11, sticky='w', pady=2)

        self.logging_label.grid(column=0, row=12, sticky='w', pady=2)
        self.logging_button.grid(column=1, row=12, sticky='w', pady=2)

        s3.grid(column=0, row=13, columnspan=3, sticky='we', pady=2)
        self.message_label.grid(column=0, row=14, columnspan=3, sticky='we', pady=2)
        self.progress.grid(column=0, row=15, columnspan=3, sticky='we', pady=2)


class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip_visible = False
        self.tooltip_window = None

        self.widget.bind("<Enter>", self.show_tooltip)
        self.widget.bind("<Leave>", self.hide_tooltip)

    def show_tooltip(self, event=None):
        if not self.tooltip_visible:
            x, y, _, _ = self.widget.bbox("insert")
            x += self.widget.winfo_rootx() + self.widget.winfo_width() // 2 - 200
            y += self.widget.winfo_rooty() - 25

            self.tooltip_window = Toplevel(self.widget)
            self.tooltip_window.wm_overrideredirect(True)
            self.tooltip_window.wm_geometry(f"+{x}+{y}")

            label = Label(self.tooltip_window, text=self.text, justify="left", background="#eeeeee",
                             relief="solid", padding=4, borderwidth=1, foreground="#000000", wraplength=192)
            label.pack(ipadx=1)

            self.tooltip_visible = True

    def hide_tooltip(self, event=None):
        if self.tooltip_visible:
            self.tooltip_window.destroy()
            self.tooltip_visible = False
