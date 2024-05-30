import curses
from dialog import Dialog
import logging

import installer


def text(app, text, height=None, width=None, title=None, backtitle=None, colors=True):
    d = Dialog()
    options = {'colors': colors}
    if height is not None:
        options['height'] = height
    if width is not None:
        options['width'] = width
    if title is not None:
        options['title'] = title
    if backtitle is not None:
        options['backtitle'] = backtitle
    d.infobox(text, **options)


def progress_bar(app, text, percent, height=None, width=None, title=None, backtitle=None, colors=True):
    d = Dialog()
    options = {'colors': colors}
    if height is not None:
        options['height'] = height
    if width is not None:
        options['width'] = width
    if title is not None:
        options['title'] = title
    if backtitle is not None:
        options['backtitle'] = backtitle

    d.gauge_start(text=text, percent=percent, **options)


def update_progress_bar(app, percent, text='', update_text=False):
    d = Dialog()
    d.gauge_update(percent, text, update_text)


def stop_progress_bar(app):
    d = Dialog()
    d.gauge_stop()


def confirm(app, question_text, height=None, width=None):
    dialog = Dialog()
    check = dialog.yesno(question_text, height, width)
    return check


def directory_picker(app, path_dir):
    str_dir = str(path_dir)

    try:
        dialog = Dialog()
        curses.curs_set(1)
        _, path = dialog.dselect(str_dir)
        curses.curs_set(0)
    except Exception as e:
        logging.error("An error occurred:", e)
        curses.endwin()

    return path

def menu(app, question_text, options, height=None, width=None, menu_height=8):
    tag_to_description = {tag: description for tag, description in options}
    dialog = Dialog(dialog="dialog")

    menu_options = [(tag, description) for i, (tag, description) in enumerate(options)]
    code, tag = dialog.menu(question_text, height, width, menu_height, choices=menu_options)
    selected_description = tag_to_description.get(tag)

    if code == dialog.OK:
        return code, tag, selected_description
    elif code == dialog.CANCEL:
        return None
