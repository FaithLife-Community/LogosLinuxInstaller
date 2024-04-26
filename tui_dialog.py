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


#FIXME: Not working. See tui_screen.py#262.
def update_progress_bar(app, percent, text='', update_text=False):
    d = Dialog()
    d.gauge_update(percent, text, update_text)


def stop_progress_bar(app):
    d = Dialog()
    d.gauge_stop()


def tasklist_progress_bar(app, text, percent, elements, height=None, width=None, title=None, backtitle=None, colors=None):
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

    if elements is None:
        elements = {}

    elements_list = [(k, v) for k, v in elements.items()]
    try:
        d.mixedgauge(text=text, percent=percent, elements=elements_list, **options)
    except Exception as e:
        logging.debug(f"Error in mixedgauge: {e}")
        raise


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


def buildlist(app, text, items=[], height=None, width=None, list_height=None, title=None, backtitle=None, colors=None):
    # items is an interable of (tag, item, status)
    dialog = Dialog(dialog="dialog")

    code, tags = dialog.buildlist(text, height, width, list_height, items, title, backtitle, colors)

    if code == dialog.OK:
        return code, tags
    elif code == dialog.CANCEL:
        return None


def checklist(app, text, items=[], height=None, width=None, list_height=None, title=None, backtitle=None, colors=None):
    # items is an iterable of (tag, item, status)
    dialog = Dialog(dialog="dialog")

    code, tags = dialog.checklist(text, items, height, width, list_height, title, backtitle, colors)

    if code == dialog.OK:
        return code, tags
    elif code == dialog.Cancel:
        return None
