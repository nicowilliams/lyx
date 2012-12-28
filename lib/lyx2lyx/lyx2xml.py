# This file is part of lyx2lyx

''' 
This file has code for straightforward conversion of LyX format to XML.
'''

from parser_tools import find_end_of, find_tokens, check_token, get_containing_layout
from xml.sax.saxutils import escape
from xml_streamer import XmlStreamer
import re
import sys

brackets = { '\index':'\\end_index', '\\begin_':'\\end_' }

namespaced = { 'layout':'layout', 'inset':'inset', 'inset Flex':'flex' }

mixed_tags = { 'emph':'default', 'shape':'default',
               'series':'default', 'color':'inherit',
               'lang':'english', 'family':'default',
               'size':'default', 'bar':'default',
               'uwave':'default', 'uuline':'default',
               'strikeout':'default', 'noun':'default' }

def _read_lyx(f):
    f = open(f, 'r')
    lines = f.readlines()
    f.close()
    return lines

def _chomp(line):
    " Remove end of line char(s)."
    if line[-1] != '\n':
        return line
    if line[-2:-1] == '\r':
        return line[:-2]
    return line[:-1]

# Returns an indication of what kind of stuff follows a \\begin_XYZ.
# For some insets (e.g., CommandInset, Tabular) there's commands that
# follow and which must be handled as attributes even though they don't
# start with a backslash.  For Tabular we must call _lyxml2xml().
def _cmd_type(tag, thing):
    if tag != 'inset':
        return None
    if thing.startswith('CommandInset') or \
       thing.startswith('Float') or \
       thing.startswith('listings'):
        return 'inset'
    if thing == 'Tabular':
        return 'XML'
    return None

# Given \begin_foo return ('foo', '\begin_foo', '\end_foo', []).
# Given \index return ('index', '\index', '\end_index', []).
# Given \begin_inset Formula stuff return ('index', '\index',
# '\end_index', ['Formula', 'stuff']) (but don't further split stuff on
# ' ').
def _beginner(line):
    if line[0] != '\\':
        return None
    # First handle things like '\index'
    tok = _chomp(line)
    toks1 = tok.split(' ', 2)
    tok = toks1[0]
    if tok in brackets:
        return (tok[1:], tok, brackets[tok], toks1[1:])
    # Now handle more regular things (\begin_XYZ)
    toks2 = tok.split('_', 1)
    toks2[0] += '_'
    if toks2[0] in brackets:
        return (toks2[1], tok, brackets[toks2[0]] + toks2[1], toks1[1:])
    return None

# Given a thing begin returns (element_name, start_token, end_token,
# command_type, rest).
# 
# XXX Make it return (namespaced_element_name, start_token, end_token,
# command_type, rest), so
#  '\begin_inset Flex foo' ->
#    ('flex:foo', '\begin_inset', '\end_inset', None, None),
# while
#  '\begin_inset Formula stuff' ->
#    ('inset:Formula', '\begin_inset', '\end_inset', None, 'stuff'),
# and so on.
def _parse_begin(line):
    (thing, start_tok, end_tok, rest) = _beginner(line)
    if len(rest) > 0 and thing in namespaced:
        key2 = thing + ' ' + rest[0]
        if key2 in namespaced:
            el = namespaced[key2] + ':' + rest[0]
        else:
            el = namespaced[thing] + ':' + rest[0]
    else:
        el = thing
    if len(rest) == 0:
        return (el, start_tok, end_tok, None, rest)
    return (el, start_tok, end_tok, _cmd_type(thing, rest[0]), rest)

def _parse_attr(line):
    line = _chomp(line)
    if line.startswith('\\'):
        line = line[1:]
    if line == '':
        return (None, None)
    sp = line.find(' ')
    if sp == -1:
        return (line, 'true')
    a = line[0:sp]
    if a in mixed_tags:
        return (None, None)
    v = line[sp + 1:]
    if v[0] == '"':
        v = v[1:]
    if v[-1] == '"':
        v = v[0:-1]
    return (a, v)

def _parse_xml_tag(line):
    line = _chomp(line)
    assert line.startswith('<') and not line.startswith('</')
    end = line.rfind('>')
    if line[end - 1] == '/':
        end -= 1
    tag_end = line.find(' ')
    if tag_end < 0:
        tag_end = end
    tag = line[1:tag_end]
    start_tok = line[0:tag_end]
    end_tok = '</' + tag
    attrs = []
    s = line[tag_end + 1:end]
    while len(s) > 0:
        s = s.strip()
        if s.find('=') == -1:
            break
        end = s.index('=')
        attr = s[0:end]
        quote = s[end + 1]
        s = s[end + 2]
        # XXX We should look for an unquoted double quote
        end = s.find(quote)
        val = s[0:end]
        attrs.append((attr, val))
        s = s[end + 1:]
    return (tag, attrs, start_tok, end_tok)

def _key(line):
    if len(line) > 0 and line[0] == '\\' and line.find(' ') > -1:
        if line.find(' ') > -1:
            return line[1:line.find(' ')]
        else:
            return _chomp(line[1:])
    return None

class LyX2XML(object):
    debug = False

    def _debugcb(self, level, text):
        if level <= self.debug_level:
            self.app_debugcb(text)

    def _null_debugcb(self, level, text): pass

    def _outcb(self, text):
        sys.stdout.write(text)

    def __init__(self, lyx, outcb=None, debugcb=None, debug_level=0):
        self.app_debugcb = debugcb
        self.debug_level = debug_level
        if debugcb:
            self.dbg = self._debugcb
        else:
            self.dbg = self._null_debugcb
        self.stack = []
        self.i = 0
        if type(lyx) == list:
            self.lines = lyx
        elif type(lyx) == str:
            self.lines = _read_lyx(lyx)
        else:
            assert lyx.readlines
            self.lines = lyx.readlines()
        self.xout = XmlStreamer(outcb or LyX2XML._outcb, 'lyx') # No DTD...
        self.xout.start_elt('lyx')
        self.xout.attr('xmlns:layout', 'urn:cryptonector.com:lyx-layout')
        self.xout.attr('xmlns:inset', 'urn:cryptonector.com:lyx-inset')
        self.xout.attr('xmlns:flex', 'urn:cryptonector.com:lyx-flex')
        sys.stdout.write('\n\n')
        # Fix the lack of XML-ish nesting of things like \series, \emph,
        # \family, \color, \shape, and \lang
        self._fix_text_styling()
        # Uncomment to save a copy of the .lyx with fixed styling, for
        # debugging purposes:
        #f = open('/tmp/f', 'w+')
        #for i in range(len(self.lines)):
        #    f.write(self.lines[i])
        #    if self.lines[i][-1] != '\n':
        #        f.write('\n')
        #f.close()
        if self.debug_level >= 3:
            self.dbg(3, 'Fixed lines:\n')
            for i in range(len(self.lines)):
                self.dbg(3, '%d %s' % (i + 1, self.lines[i]))
        self._lyx2xml()
        self.xout.end_elt('lyx')
        self.xout.finish()
        return None

    # Returns one past the new location of self.lines[i], after possibly
    # inserting lines to close and re-open tags as implied by
    # self.lines[i], to make it possible to emit proper XML.
    def _close_and_reopen_styling(self, i, tag, new_style):
        lines = self.lines
        stack = self.stack
        found = False
        # XXX Could use an __in__ operator overloading for this code (or
        # could use lists' in operator with a list comprehension to make
        # a list with just the first element of each tuple in stack):
        for k in range(len(stack) - 1, -1, -1):
            if stack[k][0] == tag:
                found = True
                break
        if not found:
            # We're just opening a tag that's not already in the stack.
            # Not much to do in this case.
            assert new_style != mixed_tags[tag]
            self.dbg(2, 'adding (\\%s, %s) to the stack (%s) at %d' % (tag, new_style, repr(stack), i))
            stack.append((tag, new_style))
            return i + 1
        # OK, we have work to do: close all intervening tags, close this
        # one, re-open all those tags and this one.
        self.dbg(2, 'fixing ordering for \\%s at line %d, stack = %s' % (tag, i, repr(stack)))
        m = -1
        for k in range(len(stack) - 1, -1, -1):
            # Close tags
            m = k
            # If this element in the stack is not the one we'll
            # terminate at (tag) or if it is but we're opening a new
            # style:
            if stack[k][0] != tag or new_style != mixed_tags[tag]:
                # Close the tag stack[k][0]
                self.dbg(2, 'fixing ordering for \\%s by closing %s %s to re-open it' % (tag, stack[k][0], stack[k][1]))
                lines.insert(i, '\\' + stack[k][0] + ' ' + mixed_tags[stack[k][0]])
                i += 1 # keep i pointing at the line triggering all this
                if stack[k][0] == tag:
                    stack[k] = (tag, new_style)
                    m += 1
                    break
            else:
                assert stack[k][0] == tag and new_style == mixed_tags[tag]
                # This line closes a tag, so just remove the
                # corresponding entry in the stack (any others before
                # this one will have been closed above).
                del(stack[k])
                break
        # Now re-open those intervening tags that we closed; we do this
        # *after* the line triggering all this, since that's the one
        # opening a tag.
        i += 1
        k = m
        while k > -1 and k < len(stack):
            lines.insert(i, '\\' + stack[k][0] + ' ' + stack[k][1])
            k += 1
            i += 1
        self.dbg(5, 'foo at %d: %s' % (i, lines[i]))
        return i


    def _fix_text_styling(self):
        lines = self.lines
        self.stack = []
        stack = self.stack
        fixes = []
        # First we'll rename the \color in the header, if any.
        i = find_tokens(lines, ('\\color', '\\end_header'), 0)
        if i != -1 and \
           check_token(lines[i], '\\color') and \
           not get_containing_layout(lines, i):
            lines[i] = '\\color_in_header ' + lines[i].split()[1]
        # Now let's get on with the rest
        i = 0
        while i < len(lines):
            line = lines[i]
            self.dbg(4, 'looking at line %d: %s' % (i, line))
            # XXX We really should simplify all this startswith()
            # nonsense.
            if not line.startswith('\\') or line.find(' ') == -1:
                self.dbg(5, '1 i++ at %d' % (i,))
                i += 1
                continue
            # XXX And this parsing nonsense needs refactoring too
            line = _chomp(line[1:])
            a = line[0:line.find(' ')]
            if not a in mixed_tags:
                self.dbg(5, '2 i++ at %d' % (i,))
                i += 1
                continue
            v = line[line.find(' ') + 1:]
            # We're opening a new whatever it is.  But we need to handle
            # the possibility that we're changing the whatever it is!
            # How to handle this?  We could convert:
            #  \lang french foo \lang spanish bar \lang english foobar
            # to
            #  <lang a="french">foo<lang a="spanish">bar</lang></lang>
            # or to
            #  <lang a="french">foo</lang><lang a="spanish">bar</lang>
            # The former might be easier: just close all tags up to the
            # farthest one in the stack for the tag being closed, then
            # re-open any others that were found along the way.  But the
            # latter is more sensible, so that's what we do.
            # Invariant: we never have more than one style tag in the
            # stack (XXX assert this in code).
            self.dbg(4, 'seen \\%s at line %d' % (line, i))
            i = self._close_and_reopen_styling(i, a, v)
            self.dbg(5, '3 i++ at %d' % (i,))

    def _lyxml2xml(self, start, end):
        lines = self.lines
        xout = self.xout
        i = start
        while i < end:
            self.dbg(3, 'Parsing line %d: %s' % (i, lines[i]))
            if lines[i].startswith('</'):
                xout.end_elt(lines[i][2:-2])
                i += 1
            elif lines[i].startswith('<'):
                (tag, attrs, start_tok, end_tok) = _parse_xml_tag(lines[i])
                # There don't seem to be tags with no child nodes in .lyx,
                # but let's handle them just in case.
                if lines[i][-2] != '/':
                    e = find_end_of(lines, i, start_tok, end_tok)
                    self.dbg(3, 'find_end_of(%d, %s, %s) = %d' % (i, start_tok, end_tok, e))
                    # lyxtabular's <column> and <features> don't get closed!
                    # What a mess.
                    if e == -1:
                        e = None
                else:
                    e = None
                xout.start_elt(tag)
                xout.attr('embedded_xml', 'true')
                for a in attrs:
                    xout.attr(a[0], a[1])
                if e:
                    i = self._lyxml2xml(i + 1, e)
                    self.dbg(3, '_lyx2xml(...) = %d, looking for %d' % (i, e))
                    if i + 1 == e:
                        i += 1
                    else:
                        self.dbg(3, '_lyx2xml() returned %d, e = %d' % (i, e))
                else:
                    xout.end_elt(tag)
                    i += 1
            else:
                i = self._lyx2xml(i, end)
        return i

    def _handle_interspersed_attrs(self, start, end):
        lines = self.lines
        xout = self.xout
        i = start
        depth = 0
        while i < end:
            if lines[i].startswith('\\begin_') or lines[i].startswith('\\index '):
                depth += 1
            elif lines[i].startswith('\\end_'):
                depth -= 1
            elif depth == 0 and lines[i].startswith('\\'):
                (a, v) = _parse_attr(lines[i])
                if a and v:
                    xout.attr(a, v)
                    if a == 'language':
                        # Set the default language; needed for the style
                        # tag fix code.
                        mixed_tags['lang'] = v
                        self.dbg(2, 'Default language is %s' % (v,))
            i += 1

    def _lyx2xml(self, start=0, end=-1, cmd_type=None):
        lines = self.lines
        xout = self.xout
        i = start
        if end < 0:
            end = len(lines)
        prev_i = -1
        while i < end:
            self.dbg(3, 'Parsing line %d: %s' % (i, lines[i]))
            assert i > prev_i
            prev_i = i
            if len(lines[i]) == 0 or lines[i] == ' ':
                # Ignore empty lines
                i += 1
                cmd_type = None
            elif lines[i][0] == '#':
                # LyX source comment
                #xout.comment(lines[i][1:])
                i += 1
                cmd_type = None
            elif _beginner(lines[i]):
                (el, start_tok, end_tok, cmd_type, rest) = _parse_begin(lines[i])
                xout.start_elt(el)
                if el == 'inset' and not cmd_type and (i + 1) < end and lines[i + 1].startswith('status '):
                    i += 1 # skip status open|collapsed line
                    status = lines[i][lines[i].find(' ') + 1:]
                else:
                    status = None
                self.dbg(4, 'lines[%d] = %s' % (i, lines[i]))
                e = find_end_of(lines, i, start_tok, end_tok)
                assert e != -1
                self.dbg(4, 'find_end_of(%d, %s, %s) = %d' % (i, start_tok, end_tok, e))
                # XXX Here we need to find any attributes that might be
                # interspersed with child nodes so we can suck them in
                # first.  What a PITA.
                self._handle_interspersed_attrs(i + 1, e - 1)
                if status:
                    xout.attr('status', status)
                if len(rest) == 2 and el != 'inset:Formula':
                    xout.attr(rest[0], escape(rest[1]))
                i = self._lyx2xml(i + 1, e, cmd_type)
                self.dbg(4, '_lyx2xml(...) = %d, looking for %s at %d; end = %d' % (i, end_tok, e, end))
                if i + 1 == e:
                    i += 1
                else:
                    self.dbg(4, '_lyx2xml() returned %d, e = %d; end = %d' % (i, e, end))
                assert lines[i].startswith('\\end_')
                if len(rest) == 2 and el == 'inset:Formula':
                    xout.text(' ')
                    xout.text(escape(rest[1]))
                xout.end_elt(el)
                cmd_type = None
                i += 1
            elif cmd_type == 'inset':
                # Parse "\begin_inset CommandInset ..." attributes
                self.dbg(4, 'lines[%d] = %s' % (i, lines[i]))
                while i < end and lines[i] != '' and lines[i] != ' ':
                    (a, v) = _parse_attr(lines[i])
                    if not a or not v:
                        break
                    xout.attr(a, v)
                    i += 1
                # then suck in content
                cmd_type = None
            elif cmd_type == 'XML':
                # Parse embedded XML contents
                i = self._lyxml2xml(i, end)
                cmd_type = None
            elif lines[i][0] == '\\' and \
               not lines[i].startswith('\\begin_') and \
               not lines[i].startswith('\\end_') and \
               not _key(lines[i]) in mixed_tags:
                # An attribute, which we've handled above with the call to
                # _handle_interspersed_attrs().
                i += 1
            else:
                line = lines[i]
                if xout.stack[-1] == 'layout':
                    line = _chomp(line)
                key = _key(line)
                if key in mixed_tags:
                    val = _chomp(lines[i][lines[i].find(' ') + 1:])
                    if val == mixed_tags[key]:
                        xout.end_elt(key)
                    else:
                        xout.start_elt(key)
                        xout.attr('type', val)
                else:
                    xout.text(escape(line))
                cmd_type = None
                i += 1
        return i

