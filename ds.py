#!/usr/bin/env python

import argparse
import csv
import re
import os, sys

from time import sleep

import curses

from curtsies.window import FullscreenWindow as Window
from curtsies.events import PasteEvent
from curtsies import Input, fmtstr, fsarray
from curtsies.fmtfuncs import *

class InteractiveSearch:
    def __init__(self, bookmarks, *arg):
        self.bg = lambda x: on_dark(on_gray(x))
        self.cmdline = lambda x: bold(yellow(self.bg(x)))
        self.line_buffer = []
        self.selected_line = 0

        self.bookmarks = sorted(bookmarks)
        self.main_loop(bookmarks)
        print(self.cd_cmd)

    def main_loop(self, bookmarks):
        with Window(out_stream=sys.stderr, hide_cursor=True) as window:
            clean_display = fsarray([self.bg(' ')*window.width for _ in range(window.height)])
            display = fsarray(clean_display)
            self.__update_screen(display)
            window.render_to_terminal(display)

            done = False;
            while not done:
                with Input(keynames='curtsies') as _:
                    for e in Input():
                        display = fsarray(clean_display)
                        done = self.__process_key(e)
                        self.__update_screen(display)
                        window.render_to_terminal(display)
                        if done:
                            break

    def __update_screen(self, display):
        self.__display_bookmarks(display)
        self.__display_line_buffer(display)

    def __display_line_buffer(self, display):
        input_line = ''.join(self.line_buffer)
        display[display.height-1, :len(input_line)] = [self.cmdline(''.join(input_line))]
        return display

    def __display_bookmarks(self, display):
        self.filtered_bookmarks = filter_shortcuts(self.bookmarks, ''.join(self.line_buffer))
        filter_regex = match_to_regex(''.join(self.line_buffer))
        self.num_bookmarks = len(self.filtered_bookmarks)

        for i, bookmark in enumerate(self.filtered_bookmarks):

            selected = (i == self.selected_line)
            self.__display_bookmark(display, display.height - self.num_bookmarks - 1 + i, 0, bookmark, filter_regex, selected)

    def __display_bookmark(self, display, y, x, bookmark, regex, selected):
        """Takes a bookmark and a regex object and displays it
           in curses window, highlighting matched parts"""
        # tab padding between nickname and directory name
        padding = 16 - len(bookmark[0])
        highlight = lambda x: dark(gray(on_red(x)))

        if selected:
            symbol = '> '
        else:
            symbol = '  '

        bookmark_line = self.bg('{}[{}]{}{}'.format(symbol, bookmark[0], ' '*padding, bookmark[1]))

        # highlight matched parts
        match_result = regex.match(bookmark[0])
        if match_result and match_result.lastindex:
            for i in range(1, match_result.lastindex + 1):
                start = match_result.start(i) + x + 3
                end = start + len(match_result.group(i))
                bookmark_line = bookmark_line.splice(highlight(match_result.group(i)), start, end)

        match_result = regex.match(bookmark[1])
        if match_result and match_result.lastindex:
            for i in range(1, match_result.lastindex + 1):
                start = match_result.start(i) + x + 4 + 16
                end = start + len(match_result.group(i))
                bookmark_line = bookmark_line.splice(highlight(match_result.group(i)), start, end)

        display[y, :len(bookmark_line)] = [bookmark_line]

    def __process_key(self, event):
        KEY_ENTER = ['<Ctrl-j>', '<PADENTER>']
        KEY_ESCAPE = '<ESC>'
        KEY_BACKSPACE = '<BACKSPACE>'
        KEY_UP = ['<UP>', '<Ctrl-UP>']
        KEY_DOWN = ['<DOWN>','<Ctrl-DOWN>']
        KEY_TAB = '<TAB>'

        done = False

        if type(event) == PasteEvent:
            event = event.events[0]

        if event in KEY_ENTER:
            try:
                dirname = self.filtered_bookmarks[self.selected_line][1]
                self.cd_cmd = bash_cd_cmd.format(dirname)
            except:
                self.cd_cmd = bash_null_cmd

            done = True
        elif event == KEY_ESCAPE:
            self.cd_cmd = bash_null_cmd
            done = True
        elif event == KEY_BACKSPACE:
            self.selected_line = 0
            if len(self.line_buffer) > 0:
                del self.line_buffer[-1]
        elif event in KEY_UP:
            if self.selected_line > 0:
                self.selected_line -= 1
        elif event in KEY_DOWN:
            if self.selected_line < self.num_bookmarks - 1:
                self.selected_line += 1
        elif event == KEY_TAB:
            if self.selected_line < self.num_bookmarks - 1:
                self.selected_line += 1
            else:
                self.selected_line = 0
        else:
            allowed, ch = self.char_allowed(event)
            if allowed:
                self.line_buffer.append(ch)
                self.selected_line = 0

        return done

    @staticmethod
    def char_allowed(event):
        allowed = False
        ch = 0

        if(len(event) == 1):
            ch = ord(event)

            if ch >= 65 and ch<= 90:
                # uppercase letters
                allowed = True
            elif ch >= 97 and ch <= 122:
                # lowercase letters
                allowed = True
            elif ch >= 48 and ch <= 57:
                # digits
                allowed = True
            elif ch == 45 or ch == 95:
                # dash or underscore
                allowed = True
        else:
            if event == '<SPACE>':
                ch = 32
                allowed = True

        return allowed, chr(ch)


bookmark_path = os.path.join(os.environ['HOME'],".dir-short.bookmarks")
delimiter = ':'
bash_null_cmd = ':'
bash_cd_cmd = 'cd "{}";'

def bash_print(string):
    bash_print_cmd = 'printf "{}\\n";'
    print(bash_print_cmd.format(string))

def find(bookmarks, match):
    try:
        dirname = filter_shortcuts(bookmarks, match)[0][1]
        print(bash_cd_cmd.format(dirname))
    except:
        print(bash_null_cmd)

def save(bookmarks, bookmark):
    cwd = os.getcwd()
    bash_print("saved [" + bookmark + "] " + cwd)
    bookmark_directory(bookmarks, cwd, bookmark)

def parse_args():
    parser = argparse.ArgumentParser(
            description='Small utility for quickly navigating between directories')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('-l','--list', action='store_true',
            help='list bookmarked directories')
    group.add_argument('-s','--save', nargs='?', metavar='nickname',
            help='bookmark current directory with optional nickname')
    group.add_argument('filter', nargs='?',
            help='string that saved directories will be matched against')
    args = parser.parse_args()

    if args.save:
        operation = save
        argument = args.save
    elif args.filter:
        operation = find
        argument = args.filter
    elif args.list:
        operation = print_shortcuts
        argument = None
    else:
        # here goes interactive operation
        operation = InteractiveSearch
        argument = None

    return operation, argument

def load_shortcuts():
    bookmarks = set()

    try:
        with open(bookmark_path,'r') as bookmark_file:
            bookmark_reader = csv.reader(bookmark_file, delimiter=delimiter)
            for bookmark in bookmark_reader:
                bookmarks.add((bookmark[0],bookmark[1]))
    except FileNotFoundError:
        pass

    return bookmarks

def save_shortcuts(bookmarks):
    with open(bookmark_path,'w',newline='') as bookmark_file:
        bookmark_writer = csv.writer(bookmark_file, delimiter=delimiter, quoting=csv.QUOTE_MINIMAL)
        for bookmark in bookmarks:
            bookmark_writer.writerow(bookmark)

def bookmark_directory(bookmarks, directory, nickname=''):
    """Adds 'directory' to bookmark list with optional 'nickname'"""
    bookmark = (nickname,directory)
    bookmarks.add(bookmark)
    save_shortcuts(bookmarks)

def match_to_regex(match):
    """Convert matcher string into a regex. It matches any group of
       characters in place of whitespace"""
    match_groups = [r'({})'.format(x) for x in match.split()]
    match_string = r'.*'.join(match_groups)
    return re.compile(r'^.*{}.*$'.format(match_string))

def filter_shortcuts(shortcuts, match):
    """Filter shortcuts that match the supplied string. Every space
       in the string matches any group of one or more characters i.e.
       'tmp py' matches '/home/user/tmp/python/projects'"""
    regex = match_to_regex(match)
    filtered_shortcuts = [x for x in shortcuts if regex.match(x[0]) or regex.match(x[1])]
    return filtered_shortcuts

def print_shortcuts(shortcuts, none=None):
    for shortcut in sorted(shortcuts):
        if len(shortcut[0]) < 8:
            tabs = 2
        else:
            tabs = 1

        bash_print('{}{}{}'.format(shortcut[0], '\\t'*tabs, shortcut[1]))

if __name__ == '__main__':
    operation, argument = parse_args()

    bookmarks = load_shortcuts()

    operation(bookmarks, argument)
