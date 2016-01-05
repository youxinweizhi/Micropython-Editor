##
## Small python text editor based on the
## Very simple VT100 terminal text editor widget
## Copyright (c) 2015 Paul Sokolovsky (initial code)
## Copyright (c) 2015 Robert Hammelrath (additional code)
## Distributed under MIT License
## Changes:
## - Ported the code to PyBoard and Wipy (still runs on Linux or Darwin)
##   It uses VCP_USB on Pyboard and sys.stdin on WiPy, or UART, if selected.
## - changed read keyboard function to comply with char-by-char input
## - added support for TAB, BACKTAB, SAVE, DEL and Backspace joining lines,
##   Find, Replace, Goto Line, UNDO, GET file, Auto-Indent, Set Flags,
##   Copy/Delete & Paste, Indent, Un-Indent
## - Added mouse support for pointing and scrolling (not WiPy)
## - handling tab (0x09) on reading & writing files,
## - Added a status line and single line prompts for
##   Quit, Save, Find, Replace, Flags and Goto
## - moved main into a function with some optional parameters
## - Added multi-file support
##
#ifndef BASIC
#define REPLACE 1
#define BRACKET 1
#define MOUSE 1
#endif

import sys, gc
#ifdef LINUX
if sys.platform in ("linux", "darwin"):
    import os, signal, tty, termios, select
#endif

class VTxx:  ## Terminal related class

#ifdef LINUX
    if sys.platform in ("linux", "darwin"):
        def wr(self,s):
            if isinstance(s, str):
                s = bytes(s, "utf-8")
            os.write(1, s)

        def rd_any(self):
            if sys.implementation.name == "cpython":
                return select.select([self.sdev], [], [], 0)[0] != []
            else:
                return False

        def rd(self):
            while True:
                try: ## WINCH causes interrupt
                    return os.read(self.sdev,1)
                except:
                    if VTxx.winch: ## simulate REDRAW key
                        VTxx.winch = False
                        return b'\x05'

        def init_tty(self, device, baud):
            self.org_termios = termios.tcgetattr(device)
            tty.setraw(device)
            self.sdev = device
            self.winch = False

        def deinit_tty(self):
            termios.tcsetattr(self.sdev, termios.TCSANOW, self.org_termios)

        @staticmethod
        def signal_handler(sig, frame):
            signal.signal(signal.SIGWINCH, signal.SIG_IGN)
            VTxx.winch = True
            return True
#endif
#ifdef PYBOARD
    if sys.platform == "pyboard":
        def wr(self, s):
            ns = 0
            while ns < len(s): # complicated but needed, since USB_VCP.write() has issues
                res = self.serialcomm.write(s[ns:])
                if res != None:
                    ns += res

        def rd_any(self):
            return self.serialcomm.any()

        def rd(self):
            while not self.serialcomm.any():
                pass
            return self.serialcomm.read(1)

        def init_tty(self, device, baud):
            import pyb
            self.sdev = device
            if self.sdev:
                self.serialcomm = pyb.UART(device, baud)
            else:
                self.serialcomm = pyb.USB_VCP()
                self.serialcomm.setinterrupt(-1)

        def deinit_tty(self):
            if not self.sdev:
                self.serialcomm.setinterrupt(3)
#endif
#ifdef WIPY
    if sys.platform == "WiPy":
        def wr(self, s):
            sys.stdout.write(s)

        def rd_any(self):
            return False

        def rd(self):
            while True:
                try:
                    return sys.stdin.read(1).encode()
                except:
                    pass

##        def init_tty(self, device, baud):
##            pass

##        def deinit_tty(self):
##            pass
#endif
    def goto(self, row, col):
        self.wr("\x1b[{};{}H".format(row + 1, col + 1))

    def hilite(self, mode):
        if mode == 1: ## used for the status line
            self.wr(b"\x1b[1;47m")
        elif mode == 2: ## used for the marked area
            self.wr(b"\x1b[43m")
        else:         ## plain text
            self.wr(b"\x1b[0m")

    def clear_to_eol(self):
        self.wr(b"\x1b[0K")

    def cursor(self, onoff):
        self.wr(b"\x1b[?25h" if onoff else b"\x1b[?25l")
#ifdef MOUSE
    def mouse_reporting(self, onoff):
        self.wr('\x1b[?9h' if onoff else '\x1b[?9l') ## enable/disable mouse reporting
#endif
#ifdef SCROLL
    def scroll_region(self, stop):
        self.wr('\x1b[1;{}r'.format(stop) if stop else '\x1b[r') ## set scrolling range
#endif
    def get_screen_size(self):
        self.wr('\x1b[999;999H\x1b[6n')
        pos = b''
        char = self.rd() ## expect ESC[yyy;xxxR
        while char != b'R':
            pos += char
            char = self.rd()
        return [int(i, 10) for i in pos[2:].split(b';')]

scr = VTxx()  ## set class instance for tty

#ifdef DEFINES
#define KEY_NONE        0
#define KEY_UP          0x0b
#define KEY_DOWN        0x0d
#define KEY_LEFT        0x1f
#define KEY_RIGHT       0x1e
#define KEY_HOME        0x10
#define KEY_END         0x03
#define KEY_PGUP        0xfff1
#define KEY_PGDN        0xfff3
#define KEY_QUIT        0x11
#define KEY_ENTER       0x0a
#define KEY_BACKSPACE   0x08
#define KEY_WRITE       0x13
#define KEY_TAB         0x09
#define KEY_BACKTAB     0x15
#define KEY_FIND        0x06
#define KEY_GOTO        0x07
#define KEY_FIRST       0x14
#define KEY_LAST        0x02
#define KEY_FIND_AGAIN  0x0e
#define KEY_YANK        0x18
#define KEY_ZAP         0x16
#define KEY_TOGGLE      0x01
#define KEY_REPLC       0x12
#define KEY_DUP         0x04
#define KEY_MOUSE       0x1b
#define KEY_SCRLUP      0x1c
#define KEY_SCRLDN      0x1d
#define KEY_REDRAW      0x05
#define KEY_UNDO        0x1a
#define KEY_GET         0x0f
#define KEY_MARK        0x0c
#define KEY_DELETE      0x7f
#define KEY_NEXT        0x17
#define KEY_MATCH       0xfffd
#define KEY_INDENT      0xfffe
#define KEY_UNDENT      0xffff
#else
KEY_NONE      = 0
KEY_UP        = 0x0b
KEY_DOWN      = 0x0d
KEY_LEFT      = 0x1f
KEY_RIGHT     = 0x1e
KEY_HOME      = 0x10
KEY_END       = 0x03
KEY_PGUP      = 0xfff1
KEY_PGDN      = 0xfff2
KEY_QUIT      = 0x11
KEY_ENTER     = 0x0a
KEY_BACKSPACE = 0x08
KEY_DELETE    = 0x7f
KEY_WRITE     = 0x13
KEY_TAB       = 0x09
KEY_BACKTAB   = 0x15
KEY_FIND      = 0x06
KEY_GOTO      = 0x07
KEY_MOUSE     = 0x1b
KEY_SCRLUP    = 0x1c
KEY_SCRLDN    = 0x1d
KEY_FIND_AGAIN= 0x0e
KEY_REDRAW    = 0x05
KEY_UNDO      = 0x1a
KEY_YANK      = 0x18
KEY_ZAP       = 0x16
KEY_DUP       = 0x04
KEY_FIRST     = 0x14
KEY_LAST      = 0x02
KEY_REPLC     = 0x12
KEY_TOGGLE    = 0x01
KEY_GET       = 0x0f
KEY_MARK      = 0x0c
KEY_NEXT      = 0x17
KEY_MATCH     = 0xfffd
KEY_INDENT    = 0xfffe
KEY_UNDENT    = 0xffff
#endif

class Editor:

    KEYMAP = { ## Gets lengthy
    b"\x1b[A" : KEY_UP,
    b"\x1b[B" : KEY_DOWN,
    b"\x1b[D" : KEY_LEFT,
    b"\x1b[C" : KEY_RIGHT,
    b"\x1b[H" : KEY_HOME, ## in Linux Terminal
    b"\x1bOH" : KEY_HOME, ## Picocom, Minicom
    b"\x1b[1~": KEY_HOME, ## Putty
    b"\x1b[F" : KEY_END,  ## Linux Terminal
    b"\x1bOF" : KEY_END,  ## Picocom, Minicom
    b"\x1b[4~": KEY_END,  ## Putty
    b"\x1b[5~": KEY_PGUP,
    b"\x1b[6~": KEY_PGDN,
    b"\x03"   : KEY_QUIT, ## Ctrl-C
    b"\r"     : KEY_ENTER,
    b"\x7f"   : KEY_BACKSPACE, ## Ctrl-? (127)
    b"\x1b[3~": KEY_DELETE,
    b"\x1b[Z" : KEY_BACKTAB, ## Shift Tab
#ifndef BASIC
## keys of BASIC functions mapped onto themselves
    b"\x11"   : KEY_QUIT, ## Ctrl-Q
    b"\n"     : KEY_ENTER,
    b"\x08"   : KEY_BACKSPACE,
    b"\x13"   : KEY_WRITE,  ## Ctrl-S
    b"\x06"   : KEY_FIND, ## Ctrl-F
    b"\x0e"   : KEY_FIND_AGAIN, ## Ctrl-N
    b"\x07"   : KEY_GOTO, ##  Ctrl-G
    b"\x05"   : KEY_REDRAW, ## Ctrl-E
    b"\x1a"   : KEY_UNDO, ## Ctrl-Z
    b"\x09"   : KEY_TAB,
    b"\x15"   : KEY_BACKTAB, ## Ctrl-U
    b"\x12"   : KEY_REPLC, ## Ctrl-R
    b"\x18"   : KEY_YANK, ## Ctrl-X
    b"\x16"   : KEY_ZAP, ## Ctrl-V
    b"\x04"   : KEY_DUP, ## Ctrl-D
    b"\x0c"   : KEY_MARK, ## Ctrl-L
    b"\x14"   : KEY_FIRST, ## Ctrl-T
    b"\x02"   : KEY_LAST,  ## Ctrl-B
    b"\x01"   : KEY_TOGGLE, ## Ctrl-A
    b"\x17"   : KEY_NEXT, ## Ctrl-W
## other keys
    b"\x0f"   : KEY_GET, ## Ctrl-O
    b"\x1b[M" : KEY_MOUSE,
    b"\x1b[1;5H": KEY_FIRST,
    b"\x1b[1;5F": KEY_LAST,
    b"\x1b[3;5~": KEY_YANK, ## Ctrl-Del
#endif
#ifdef BRACKET
    b"\x0b"   : KEY_MATCH,## Ctrl-K
#endif
    }
## symbols that may be shared between instances of Editor
    yank_buffer = []
    find_pattern = ""
#ifdef REPLACE
    replc_pattern = ""
#endif

    def __init__(self, tab_size, undo_limit):
        self.top_line = self.cur_line = self.row = self.col = self.margin = 0
        self.tab_size = tab_size
        self.changed = ""
        self.message = self.fname = ""
        self.content = [""]
        self.undo = []
        self.undo_limit = max(undo_limit, 0)
        self.undo_zero = 0
        self.case = "n"
        self.autoindent = "y"
        self.mark = None
        self.height, self.width = scr.get_screen_size()
        self.height -= 1

#ifndef BASIC
        self.write_tabs = "n"
#endif
#ifdef SCROLL
    def scroll_up(self, scrolling):
        Editor.scrbuf[scrolling:] = Editor.scrbuf[:-scrolling]
        Editor.scrbuf[:scrolling] = [''] * scrolling
        scr.goto(0, 0)
        scr.wr("\x1bM" * scrolling)

    def scroll_down(self, scrolling):
        Editor.scrbuf[:-scrolling] = Editor.scrbuf[scrolling:]
        Editor.scrbuf[-scrolling:] = [''] * scrolling
        scr.goto(self.height - 1, 0)
        scr.wr("\x1bD " * scrolling)
#endif
    def redraw(self, flag):
        scr.cursor(False)
        Editor.scrbuf = [(False,"\x00")] * self.height ## force delete
        self.row = min(self.height - 1, self.row)
#ifdef SCROLL
        scr.scroll_region(self.height)
#endif
#ifdef LINUX
        if sys.platform in ("linux", "darwin") and sys.implementation.name == "cpython":
            signal.signal(signal.SIGWINCH, scr.signal_handler)
#endif
        if sys.implementation.name == "micropython":
            gc.collect()
            if flag:
                self.message = "{} Bytes Memory available".format(gc.mem_free())

    def get_input(self):  ## read from interface/keyboard one byte each and match against function keys
        while True:
            in_buffer = scr.rd()
            if in_buffer == b'\x1b': ## starting with ESC, must be fct
                while True:
                    in_buffer += scr.rd()
                    c = chr(in_buffer[-1])
                    if c == '~' or (c.isalpha() and c != 'O'):
                        break
            if in_buffer in self.KEYMAP:
                c = self.KEYMAP[in_buffer]
                if c != KEY_MOUSE:
                    return c
#ifdef MOUSE
                else: ## special for mice
                    self.mouse_fct = ord((scr.rd())) ## read 3 more chars
                    self.mouse_x = ord(scr.rd()) - 33
                    self.mouse_y = ord(scr.rd()) - 33
                    if self.mouse_fct == 0x61:
                        return KEY_SCRLDN
                    elif self.mouse_fct == 0x60:
                        return KEY_SCRLUP
                    else:
                        return KEY_MOUSE ## do nothing but set the cursor
#endif
            elif len(in_buffer) == 1: ## but only if a single char
                return in_buffer[0]

    def display_window(self): ## Update window and status line
## Force cur_line and col to be in the reasonable bounds
        self.cur_line = min(self.total_lines - 1, max(self.cur_line, 0))
        self.col = max(0, min(self.col, len(self.content[self.cur_line])))
## Check if Column is out of view, and align margin if needed
        if self.col >= self.width + self.margin:
            self.margin = self.col - self.width + (self.width >> 2)
        elif self.col < self.margin:
            self.margin = max(self.col - (self.width >> 2), 0)
## if cur_line is out of view, align top_line to the given row
        if not (self.top_line <= self.cur_line < self.top_line + self.height): # Visible?
            self.top_line = max(self.cur_line - self.row, 0)
## in any case, align row to top_line and cur_line
        self.row = self.cur_line - self.top_line
## update_screen
        scr.cursor(False)
        i = self.top_line
        for c in range(self.height):
            if i == self.total_lines: ## at empty bottom screen part
                if Editor.scrbuf[c] != (False,''):
                    scr.goto(c, 0)
                    scr.clear_to_eol()
                    Editor.scrbuf[c] = (False,'')
            else:
                l = (self.mark != None and (
                    (self.mark <= i <= self.cur_line) or (self.cur_line <= i <= self.mark)),
                     self.content[i][self.margin:self.margin + self.width])
                if l != Editor.scrbuf[c]: ## line changed, print it
                    scr.goto(c, 0)
                    if l[0]: scr.hilite(2)
                    scr.wr(l[1])
                    if len(l[1]) < self.width:
                        scr.clear_to_eol()
                    if l[0]: scr.hilite(0)
                    Editor.scrbuf[c] = l
                i += 1
## display Status-Line
        scr.goto(self.height, 0)
        scr.hilite(1)
        scr.wr("{}{} Row: {}/{} Col: {}  {}".format(
            self.changed, self.fname, self.cur_line + 1, self.total_lines,
            self.col + 1, self.message[:self.width - 25 - len(self.fname)]))
        scr.clear_to_eol() ## once moved up for mate/xfce4-terminal issue with scroll region
        scr.hilite(0)
        scr.goto(self.row, self.col - self.margin)
        scr.cursor(True)

    def spaces(self, line, pos = None): ## count spaces
        return (len(line) - len(line.lstrip(" ")) if pos == None else ## at line start
                len(line[:pos]) - len(line[:pos].rstrip(" ")))

    def line_range(self):
        return ((self.mark, self.cur_line + 1) if self.mark < self.cur_line else
                (self.cur_line, self.mark + 1))


    def line_edit(self, prompt, default):  ## simple one: only 4 fcts
        scr.goto(self.height, 0)
        scr.hilite(1)
        scr.wr(prompt)
        scr.wr(default)
        scr.clear_to_eol()
        res = default
        while True:
            key = self.get_input()  ## Get Char of Fct.
            if key in (KEY_ENTER, KEY_TAB): ## Finis
                scr.hilite(0)
                return res
            elif key == KEY_QUIT: ## Abort
                scr.hilite(0)
                return None
            elif key == KEY_BACKSPACE: ## Backspace
                if (len(res) > 0):
                    res = res[:len(res)-1]
                    scr.wr('\b \b')
            elif key == KEY_DELETE: ## Delete prev. Entry
                scr.wr('\b \b' * len(res))
                res = ''
            elif 0x20 <= key < 0xfff0: ## character to be added
                if len(prompt) + len(res) < self.width - 2:
                    res += chr(key)
                    scr.wr(chr(key))

    def find_in_file(self, pattern, pos, end):
        Editor.find_pattern = pattern # remember it
        if self.case != "y":
            pattern = pattern.lower()
        spos = pos
        for line in range(self.cur_line, end):
            if self.case != "y":
                match = self.content[line][spos:].lower().find(pattern)
#ifndef BASIC
            else:
                match = self.content[line][spos:].find(pattern)
#endif
            if match >= 0:
                break
            spos = 0
        else:
            self.message = "No match: " + pattern
            return 0
        self.col = match + spos
        self.cur_line = line
        return len(pattern)

    def undo_add(self, lnum, text, key, span = 1):
        self.changed = '*'
        if self.undo_limit > 0 and (
           len(self.undo) == 0 or key == KEY_NONE or self.undo[-1][3] != key or self.undo[-1][0] != lnum):
            if len(self.undo) >= self.undo_limit: ## drop oldest undo, if full
                del self.undo[0]
                self.undo_zero -= 1
            self.undo.append((lnum, span, text, key, self.col))

    def delete_lines(self, yank): ## copy marked lines (opt) and delete them
        lrange = self.line_range()
        if yank:
            Editor.yank_buffer = self.content[lrange[0]:lrange[1]]
        self.undo_add(lrange[0], self.content[lrange[0]:lrange[1]], KEY_NONE, 0) ## undo inserts
        del self.content[lrange[0]:lrange[1]]
        if self.content == []: ## if all was wiped
            self.content = [""]
        self.total_lines = len(self.content)
        self.cur_line = lrange[0]
        self.mark = None ## unset line mark

    def handle_edit_keys(self, key): ## keys which change content
        l = self.content[self.cur_line]
        if key == KEY_DOWN:
#ifdef SCROLL
            if self.cur_line < self.total_lines - 1:
#endif
                self.cur_line += 1
#ifdef SCROLL
                if self.cur_line == self.top_line + self.height:
                    self.scroll_down(1)
#endif
        elif key == KEY_UP:
#ifdef SCROLL
            if self.cur_line > 0:
#endif
                self.cur_line -= 1
#ifdef SCROLL
                if self.cur_line < self.top_line:
                    self.scroll_up(1)
#endif
        elif key == KEY_LEFT:
#ifndef BASIC
            if self.col == 0 and self.cur_line > 0:
                self.cur_line -= 1
                self.col = len(self.content[self.cur_line])
#ifdef SCROLL
                if self.cur_line < self.top_line:
                    self.scroll_up(1)
#endif
            else:
#endif
                self.col -= 1
        elif key == KEY_RIGHT:
#ifndef BASIC
            if self.col >= len(l) and self.cur_line < self.total_lines - 1:
                self.col = 0
                self.cur_line += 1
#ifdef SCROLL
                if self.cur_line == self.top_line + self.height:
                    self.scroll_down(1)
#endif
            else:
#endif
                self.col += 1
        elif key == KEY_DELETE:
            if self.mark != None:
                self.delete_lines(False)
            elif self.col < len(l):
                self.undo_add(self.cur_line, [l], KEY_DELETE)
                self.content[self.cur_line] = l[:self.col] + l[self.col + 1:]
            elif (self.cur_line + 1) < self.total_lines: ## test for last line
                self.undo_add(self.cur_line, [l, self.content[self.cur_line + 1]], KEY_NONE)
                self.content[self.cur_line] = l + self.content.pop(self.cur_line + 1)
                self.total_lines -= 1
        elif key == KEY_BACKSPACE:
            if self.mark != None:
                self.delete_lines(False)
            elif self.col > 0:
                self.undo_add(self.cur_line, [l], KEY_BACKSPACE)
                self.content[self.cur_line] = l[:self.col - 1] + l[self.col:]
                self.col -= 1
#ifndef BASIC
            elif self.cur_line > 0: # at the start of a line, but not the first
                self.undo_add(self.cur_line - 1, [self.content[self.cur_line - 1], l], KEY_NONE)
                self.col = len(self.content[self.cur_line - 1])
                self.content[self.cur_line - 1] += self.content.pop(self.cur_line)
                self.cur_line -= 1
                self.total_lines -= 1
#endif
        elif 0x20 <= key < 0xfff0: ## character to be added
            self.mark = None
            self.undo_add(self.cur_line, [l], 0x20 if key == 0x20 else 0x41)
            self.content[self.cur_line] = l[:self.col] + chr(key) + l[self.col:]
            self.col += 1
        elif key == KEY_HOME:
            self.col = self.spaces(l) if self.col == 0 else 0
        elif key == KEY_END:
            self.col = len(l)
        elif key == KEY_PGUP:
            self.cur_line -= self.height
        elif key == KEY_PGDN:
            self.cur_line += self.height
        elif key == KEY_FIND:
            pat = self.line_edit("Find: ", Editor.find_pattern)
            if pat:
                self.find_in_file(pat, self.col, self.total_lines)
                self.row = self.height >> 1
        elif key == KEY_FIND_AGAIN:
            if Editor.find_pattern:
                self.find_in_file(Editor.find_pattern, self.col + 1, self.total_lines)
                self.row = self.height >> 1
        elif key == KEY_GOTO: ## goto line
            line = self.line_edit("Goto Line: ", "")
            if line:
                self.cur_line = int(line) - 1
                self.row = self.height >> 1
        elif key == KEY_TOGGLE: ## Toggle Autoindent/Statusline/Search case
            self.autoindent = 'y' if self.autoindent != 'y' else 'n' ## toggle
#ifndef BASIC
            pat = self.line_edit("Case Sensitive Search {}, Autoindent {}, Tab Size {}, Write Tabs {}: ".format(self.case, self.autoindent, self.tab_size, self.write_tabs), "")
            try:
                res =  [i.strip().lower() for i in pat.split(",")]
                if res[0]: self.case       = 'y' if res[0][0] == 'y' else 'n'
                if res[1]: self.autoindent = 'y' if res[1][0] == 'y' else 'n'
                if res[2]: self.tab_size = int(res[2])
                if res[3]: self.write_tabs = 'y' if res[3][0] == 'y' else 'n'
            except:
                pass
        elif key == KEY_FIRST: ## first line
            self.cur_line = 0
        elif key == KEY_LAST: ## last line
            self.cur_line = self.total_lines - 1
            self.row = self.height - 1 ## will be fixed if required
#endif
#ifdef MOUSE
        elif key == KEY_MOUSE: ## Set Cursor
            if self.mouse_y < self.height:
                self.col = self.mouse_x + self.margin
                self.cur_line = self.mouse_y + self.top_line
                if self.mouse_fct in (0x22, 0x30): ## Right/Ctrl button on Mouse
                    self.mark = self.cur_line if self.mark == None else None
        elif key == KEY_SCRLUP: ##
            if self.top_line > 0:
                self.top_line = max(self.top_line - 3, 0)
                self.cur_line = min(self.cur_line, self.top_line + self.height - 1)
#ifdef SCROLL
                self.scroll_up(3)
#endif
        elif key == KEY_SCRLDN: ##
            if self.top_line + self.height < self.total_lines:
                self.top_line = min(self.top_line + 3, self.total_lines - 1)
                self.cur_line = max(self.cur_line, self.top_line)
#ifdef SCROLL
                self.scroll_down(3)
#endif
#endif
#ifdef BRACKET
        elif key == KEY_MATCH:
            if self.col < len(l): ## ony within text
                opening = "([{<"
                closing = ")]}>"
                level = 0
                pos = self.col
                srch = l[pos]
                i = opening.find(srch)
                if i >= 0: ## at opening bracket, look forward
                    pos += 1
                    match = closing[i]
                    for i in range(self.cur_line, self.total_lines):
                        for c in range(pos, len(self.content[i])):
                            if self.content[i][c] == match:
                                if level == 0: ## match found
                                    self.cur_line, self.col  = i, c
                                    return True  ## return here instead of ml-breaking
                                else:
                                    level -= 1
                            elif self.content[i][c] == srch:
                                level += 1
                        pos = 0 ## next line starts at 0
                else:
                    i = closing.find(srch)
                    if i >= 0: ## at closing bracket, look back
                        pos -= 1
                        match = opening[i]
                        for i in range(self.cur_line, -1, -1):
                            for c in range(pos, -1, -1):
                                if self.content[i][c] == match:
                                    if level == 0: ## match found
                                        self.cur_line, self.col  = i, c
                                        return True ## return here instead of ml-breaking
                                    else:
                                        level -= 1
                                elif self.content[i][c] == srch:
                                    level += 1
                            if i > 0: ## prev line, if any, starts at the end
                                pos = len(self.content[i - 1]) - 1
#endif
        elif key == KEY_MARK:
            self.mark = self.cur_line if self.mark == None else None
        elif key == KEY_ENTER:
            self.mark = None
            self.undo_add(self.cur_line, [l], KEY_NONE, 2)
            self.content[self.cur_line] = l[:self.col]
            ni = 0
            if self.autoindent == "y": ## Autoindent
                ni = min(self.spaces(l), self.col)  ## query indentation
#ifndef BASIC
                r = l.partition("\x23")[0].rstrip() ## \x23 == #
                if r and r[-1] == ':' and self.col >= len(r): ## look for : as the last non-space before comment
                    ni += self.tab_size
#endif
            self.cur_line += 1
            self.content[self.cur_line:self.cur_line] = [' ' * ni + l[self.col:]]
            self.total_lines += 1
            self.col = ni
        elif key == KEY_TAB:
            if self.mark != None:
                lrange = self.line_range()
                self.undo_add(lrange[0], self.content[lrange[0]:lrange[1]], KEY_INDENT, lrange[1] - lrange[0]) ## undo replaces
                for i in range(lrange[0],lrange[1]):
                    if len(self.content[i]) > 0:
                        self.content[i] = ' ' * (self.tab_size - self.spaces(self.content[i]) % self.tab_size) + self.content[i]
            else:
                ni = self.tab_size - self.col % self.tab_size ## determine spaces to add
                self.undo_add(self.cur_line, [l], KEY_TAB)
                self.content[self.cur_line] = l[:self.col] + ' ' * ni + l[self.col:]
                self.col += ni
        elif key == KEY_BACKTAB:
            if self.mark != None:
                lrange = self.line_range()
                self.undo_add(lrange[0], self.content[lrange[0]:lrange[1]], KEY_UNDENT, lrange[1] - lrange[0]) ## undo replaces
                for i in range(lrange[0],lrange[1]):
                    ns = self.spaces(self.content[i])
                    if ns > 0:
                        self.content[i] = self.content[i][(ns - 1) % self.tab_size + 1:]
            else:
                ni = min((self.col - 1) % self.tab_size + 1, self.spaces(l, self.col)) ## determine spaces to drop
                if ni > 0:
                    self.undo_add(self.cur_line, [l], KEY_BACKTAB)
                    self.content[self.cur_line] = l[:self.col - ni] + l[self.col:]
                    self.col -= ni
#ifdef REPLACE
        elif key == KEY_REPLC:
            count = 0
            pat = self.line_edit("Replace: ", Editor.find_pattern)
            if pat:
                rpat = self.line_edit("With: ", Editor.replc_pattern)
                if rpat != None: ## start with setting up loop parameters
                    Editor.replc_pattern = rpat
                    q = ''
                    cur_line = self.cur_line ## remember line
                    if self.mark != None: ## Replace in Marked area
                        (self.cur_line, end_line) = self.line_range()
                        self.col = 0
                    else: ## replace from cur_line to end
                        end_line = self.total_lines
                    self.message = "Replace (yes/No/all/quit) ? "
                    while True: ## and go
                        ni = self.find_in_file(pat, self.col, end_line)
                        if ni: ## Pattern found
                            if q != 'a':
                                self.display_window()
                                key = self.get_input()  ## Get Char of Fct.
                                q = chr(key).lower()
                            if q == 'q' or key == KEY_QUIT:
                                break
                            elif q in ('a','y'):
                                self.undo_add(self.cur_line, [self.content[self.cur_line]], KEY_NONE)
                                self.content[self.cur_line] = self.content[self.cur_line][:self.col] + rpat + self.content[self.cur_line][self.col + ni:]
                                self.col += len(rpat)
                                count += 1
                            else: ## everything else is no
                                self.col += 1
                        else: ## not found, quit
                            break
                    self.cur_line = cur_line ## restore cur_line
                    self.message = "'{}' replaced {} times".format(pat, count)
#endif
        elif key == KEY_YANK:  # delete line or line(s) into buffer
            if self.mark != None:
                self.delete_lines(True)
        elif key == KEY_DUP:  # copy line(s) into buffer
            if self.mark != None:
                lrange = self.line_range()
                Editor.yank_buffer = self.content[lrange[0]:lrange[1]]
                self.mark = None
        elif key == KEY_ZAP: ## insert buffer
            if Editor.yank_buffer:
                if self.mark != None:
                    self.delete_lines(False)
                self.undo_add(self.cur_line, None, KEY_NONE, -len(Editor.yank_buffer))
                self.content[self.cur_line:self.cur_line] = Editor.yank_buffer # insert lines
                self.total_lines += len(Editor.yank_buffer)
        elif key == KEY_WRITE:
            fname = self.line_edit("Save File: ", self.fname)
            if fname:
                self.put_file(fname)
                self.changed = '' ## clear change flag
                self.undo_zero = len(self.undo) ## remember state
                if not self.fname: self.fname = fname ## remember (new) name
        elif key == KEY_UNDO:
            if len(self.undo) > 0:
                action = self.undo.pop(-1) ## get action from stack
                if action[3] != KEY_INDENT:
                    self.cur_line = action[0]
                    self.col = action[4]
                if action[1] >= 0: ## insert or replace line
                    if action[0] < self.total_lines:
                        self.content[action[0]:action[0] + action[1]] = action[2] # insert lines
                    else:
                        self.content += action[2]
                else: ## delete lines
                    del self.content[action[0]:action[0] - action[1]]
                self.total_lines = len(self.content) ## brute force
                if len(self.undo) == self.undo_zero:
                    self.changed = ''
                self.mark = None
        elif key == KEY_REDRAW:
            (self.height, self.width) = scr.get_screen_size()
            self.height -= 1
            self.redraw(True)

    def edit_loop(self): ## main editing loop
        if not self.content: ## ensure content
            self.content = [""]
        self.total_lines = len(self.content)
        self.redraw(self.message == "")

        while True:
            try:
                if not scr.rd_any(): ## skip update if a char is waiting
                    self.display_window()  ## Update & display window
                key = self.get_input()  ## Get Char of Fct-key code
                self.message = '' ## clear message

                if key == KEY_QUIT:
                    if self.changed != '':
                        res = self.line_edit("Content changed! Quit without saving (y/N)? ", "N")
                        if not res or res[0].upper() != 'Y':
                            continue
#ifdef SCROLL
                    scr.scroll_region(0)
#endif
                    scr.goto(self.height, 0)
                    scr.clear_to_eol()
                    return key, ""
                elif key == KEY_NEXT:
                    return (key, "")
                elif key == KEY_GET:
                    return (key, self.line_edit("Open file: ", ""))
                else: self.handle_edit_keys(key)
            except Exception as err:
                self.message = "{!r}".format(err)

## packtabs: replace sequence of space by tab
#ifndef BASIC
    def packtabs(self, s):
        from _io import StringIO
        sb = StringIO()
        for i in range(0, len(s), 8):
            c = s[i:i + 8]
            cr = c.rstrip(" ")
            if c != cr: ## Spaces at the end of a section
                sb.write(cr + "\t") ## replace by tab
            else:
                sb.write(c)
        return sb.getvalue()
#endif
## Read file into content
    def get_file(self, fname):
        self.fname = fname
        try:
#ifdef LINUX
            if sys.implementation.name == "cpython":
                with open(fname, errors="ignore") as f:
                    self.content = f.readlines()
            else:
#endif
                with open(fname) as f:
                    self.content = f.readlines()
        except Exception as err:
            self.content, self.message = [""], "{!r}".format(err)
        else:
            for i in range(len(self.content)):  ## strip and convert
                self.content[i] = expandtabs(self.content[i].rstrip('\r\n\t '))

## write file
    def put_file(self, fname):
        import os
        with open("tmpfile.pye", "w") as f:
            for l in self.content:
#ifndef BASIC
                if self.write_tabs == 'y':
                    f.write(self.packtabs(l) + '\n')
                else:
#endif
                    f.write(l + '\n')
        try:    os.unlink(fname)
        except: pass
        os.rename("tmpfile.pye", fname)

## expandtabs: hopefully sometimes replaced by the built-in function
def expandtabs(s):
    from _io import StringIO
    if '\t' in s:
        sb = StringIO()
        pos = 0
        for c in s:
            if c == '\t': ## tab is seen
                sb.write(" " * (8 - pos % 8)) ## replace by space
                pos += 8 - pos % 8
            else:
                sb.write(c)
                pos += 1
        return sb.getvalue()
    else:
        return s

def pye(*content, tab_size = 4, undo = 50, device = 0, baud = 115200):
#if defined(PYBOARD) || defined(LINUX)
    scr.init_tty(device, baud)
#endif
#ifdef MOUSE
    scr.mouse_reporting(True) ## enable mouse reporting
#endif
## prepare content
    gc.collect() ## all (memory) is mine
    if content:
        slot = []
        index = 0
        for f in content:
            slot.append(Editor(tab_size, undo))
            if type(f) == str and f: ## String = non-empty Filename
                slot[index].get_file(f)
            elif type(f) == list and len(f) > 0 and type(f[0]) == str:
                slot[index].content = f ## non-empty list of strings -> edit
            index += 1
    else:
        slot = [Editor(tab_size, undo)]
    index = 0
## edit
    while True:
        key,f = slot[index].edit_loop()
        if key == KEY_QUIT:
            if len(slot) == 1: ## the last man standing is kept
                break
            del slot[index]
            index %= len(slot)
        elif key == KEY_GET:
            slot.append(Editor(tab_size, undo))
            index = len(slot) - 1
            if f:
                slot[index].get_file(f)
        elif key == KEY_NEXT:
            index = (index + 1) % len(slot)
## All windows closed, clean up
    slot[0].undo, Editor.yank_buffer = [],[]
#ifdef MOUSE
    scr.mouse_reporting(False) ## disable mouse reporting
#endif
#if defined(PYBOARD) || defined(LINUX)
    scr.deinit_tty()
#endif
## close
    return slot[0].content if (slot[0].fname == "") else slot[0].fname

#ifdef LINUX
if __name__ == "__main__":
    if sys.platform in ("linux", "darwin"):
        import stat
        fd_tty = 0
        if len(sys.argv) > 1:
            name = sys.argv[1:]
            pye(*name, undo = 500, device=fd_tty)
        else:
            name = ""
            if sys.implementation.name == "cpython":
                mode = os.fstat(0).st_mode
                if stat.S_ISFIFO(mode) or stat.S_ISREG(mode):
                    name = sys.stdin.readlines()
                    os.close(0) ## close and repopen /dev/tty
                    fd_tty = os.open("/dev/tty", os.O_RDONLY) ## memorized, if new fd
                    for i in range(len(name)):  ## strip and convert
                        name[i] = expandtabs(name[i].rstrip('\r\n\t '))
            pye(name, undo = 500, device=fd_tty)
    else:
        print ("\nSorry, this OS is not supported (yet)")
#endif