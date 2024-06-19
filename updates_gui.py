from queue import Queue
from threading import Thread
from tkinter import IntVar
from tkinter import Listbox
from tkinter import StringVar
from tkinter import Tk
from tkinter import Toplevel
from tkinter.ttk import Button
from tkinter.ttk import Frame
from tkinter.ttk import Label
from tkinter.ttk import Progressbar

import config
import updates
import utils
from gui_app import Root
from user.utils import b_to_mb


class SelectUpdatesWindow(Toplevel):
    # def __init__(self, new_win, root, **kwargs):
    def __init__(self, root, **kwargs):
        super().__init__(root, **kwargs)
        config.DIALOG = 'tk'
        config.LOGOS_EXE = "~/LogosBible10/data/wine64_bottle/drive_c/users/nate/AppData/Local/Logos/Logos.exe"
        # Set root parameters.
        self.root = root
        self.root.title("Resource Updates")
        self.root.minsize(480, 270)
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(0, weight=1)
        self.frame = Frame(self.root, padding=5)
        self.frame.grid(column=0, row=0, sticky='nwes')
        self.frame.grid_columnconfigure(0, weight=1)
        self.frame.grid_rowconfigure(1, weight=1)
        self.frame.grid(row=0, column=0, sticky='nwes')

        # Initialize variables.
        self.available_updates = None
        self.selected_updates = None
        self.progress_q = Queue()
        self.updates_q = Queue()

        # Create the window.
        self.create_window()

        # Set widget callbacks and event bindings.
        self.updates_listbox.bind(
            "<<ListboxSelect>>",
            self.update_selected_updates
        )

        # Set root widget event bindings.
        self.root.bind("<Return>", self.on_install_released)
        self.root.bind("<Escape>", self.on_cancel_released)
        # self.root.bind("<<UpdateProgress>>", self.update_progress)

    def create_window(self):
        # Create widgets.
        desc = "Available updates (Ctrl+<click> to [de]select):"
        self.description = Label(self.frame, text=desc)
        self.available_updates = self.get_available_updates()
        available_updates = [f"{n.get('title')} [{b_to_mb(n.get('size'))} MB]" for n in self.available_updates]  # noqa: E501
        self.updates_var = StringVar(value=available_updates)
        self.updates_listbox = Listbox(
            self.frame,
            height=10,
            listvariable=self.updates_var,
            selectmode='extended',
        )
        self.updates_listbox.selection_set(0, len(self.available_updates)-1)
        self.selected_updates = self.available_updates  # select all by default
        self.summary_var = StringVar(value=self.get_summary_text())
        self.summary_text = Label(self.frame, textvariable=self.summary_var)
        self.install_button = Button(
            self.frame,
            command=self.on_install_released,
            text="Install"
        )
        self.cancel_button = Button(
            self.frame,
            command=self.on_cancel_released,
            text="Cancel"
        )
        # Place widgets.
        self.description.grid(column=0, row=0, columnspan=5, sticky='we')
        self.updates_listbox.grid(column=0, row=1, columnspan=5, sticky='nwes')
        self.summary_text.grid(column=0, row=2, columnspan=2, sticky='w')
        self.cancel_button.grid(column=3, row=2)
        self.install_button.grid(column=4, row=2)

    def get_available_updates(self):
        return updates.get_available_updates(app=self)

    def update_selected_updates(self, evt=None):
        new_selected = []
        for idx in self.updates_listbox.curselection():
            new_selected.append(self.available_updates[idx])
        self.selected_updates = new_selected
        self.summary_var.set(self.get_summary_text())

    def start_install_updates(self):
        # Disable button; clear list.
        self.install_button.state(['disabled'])
        # Pop up progress window.
        classname = "LogosLinuxResourceUpdates"
        ProgressWindow(self.root, self.selected_updates, class_=classname)
        self.withdraw()
        self.root.withdraw()
        # self.root.icon = config.LOGOS_ICON_URL

    def on_install_released(self, evt=None):
        self.start_install_updates()

    def on_cancel_released(self, evt=None):
        self.root.destroy()
        return 1

    def get_summary_text(self):
        size = b_to_mb(sum([u.get('size') for u in self.selected_updates]))
        return f"Total download: {size} MB"


class ProgressWindow(Toplevel):
    def __init__(self, root, selected_updates, **kwargs):
        super().__init__(root, **kwargs)
        self.root = root
        self.minsize(500, 10)
        self.title("Update Progress")
        self.resizable = False
        self.selected_updates = selected_updates
        self.grid_columnconfigure(0, weight=1)
        self.get_q = Queue()
        self.get_evt = "<<DownloadFile>>"
        self.check_q = Queue()
        self.check_evt = "<<CheckFile>>"
        self.status_q = Queue()
        self.status_evt = "<<UpdateStatus>>"
        self.status_var = StringVar()
        self.frame = Frame(self, padding=5)
        self.frame.grid_columnconfigure(0, weight=1)
        self.frame.grid(column=0, row=0, sticky='nwes')
        self.status = Label(
            self.frame,
            textvariable=self.status_var,
            padding=5,
        )
        self.progress_var = IntVar()
        self.progress = Progressbar(
            self.frame,
            variable=self.progress_var,
        )
        self.cancel = Button(
            self.frame,
            text="Cancel",
            command=self.on_cancel_released,
            padding=5,
        )
        # self.label.grid(column=0, row=0, columnspan=5, sticky='we')
        self.status.grid(column=0, row=0, columnspan=5, sticky='we')
        self.progress.grid(column=0, row=1, columnspan=5, sticky='we')
        self.cancel.grid(column=4, row=2, sticky="e")
        self.bind("<Escape>", self.on_cancel_released)
        self.root.bind(self.get_evt, self.update_progress_bar)
        self.root.bind(self.status_evt, self.update_status)

        self.install_thread = Thread(
            target=updates.install_selected_updates,
            args=(self.selected_updates,),
            kwargs={'app': self},
            daemon=True,
        )
        self.install_thread.start()

    def update_progress_bar(self, evt=None):
        d = self.get_q.get()
        self.progress_var.set(int(d))

    def update_status(self, evt=None):
        self.status_var.set(self.status_q.get())

    def stop_indeterminate_progress(self):
        pass

    def on_cancel_released(self, evt=None):
        self.root.destroy()
        return 1


def resource_updates_app():
    utils.set_debug()
    classname = "LogosLinuxResourceUpdates"
    # root = Root(className=classname)
    root = Tk(className=classname)
    SelectUpdatesWindow(root, class_=classname)
    root.mainloop()
