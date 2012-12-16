# This file is part of lyx2lyx

''' 
This file has code for straightforward conversion of LyX format to XML.
'''

from parser_tools import find_end_of
from xml_streamer import XmlStreamer
import re
import sys

def _chomp(line):
    " Remove end of line char(s)."
    if line[-1] != '\n':
        return line
    if line[-2:-1] == '\r':
        return line[:-2]
    return line[:-1]

def _cmd_type(tag, rest):
    if tag != 'inset':
        return None
    if rest.startswith('CommandInset'):
        return 'inset'
    if rest == 'Tabular':
        return 'XML'
    return None

def _parse_begin(line):
    assert line.startswith('\\begin_') or line.startswith('\\index ')
    line = _chomp(line)
    if line.startswith('\\index '):
        return ('index', '\\index', '\end_index', None, line[line.find(' ') + 1:])
    sp = line.find(' ')
    if sp >= 0:
        tag = line[len('\\begin_'):sp]
        start_tok = line[0:sp]
        rest = line[sp + 1:]
    else:
        tag = line[len('\\begin_'):]
        start_tok = line
        rest = None
    return (tag, start_tok, '\end_' + tag, _cmd_type(tag, rest), rest)

def _parse_attr(line):
    line = _chomp(line)
    if line.startswith('\\'):
        line = line[1:]
    sp = line.find(' ')
    if sp == -1:
        return (line, 'true')
    return (line[0:sp], line[sp + 1:])

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

def _lyxml2xml(lines, xout, start, end):
    i = start
    while i < end:
        if lines[i].startswith('</'):
            xout.end_elt(lines[i][2:-1])
        elif lines[i].startswith('<'):
            (tag, attrs, start_tok, end_tok) = _parse_xml_tag(lines[i])
            e = find_end_of(lines, i, start_tok, end_tok)
            xout.start_elt(tag)
            xout.attr('embedded_xml', 'true')
            for a in attrs:
                xout.attr(a[0], a[1])
            i = _lyxml2xml(lines, xout, i + 1, e)
        else:
            i = _lyx2xml(lines, xout, i, end)
    return i

def _handle_interspersed_attrs(lines, xout, start, end):
    i = start
    depth = 0
    while i < end:
        if lines[i].startswith('\\begin_') or lines[i].startswith('\\index '):
            depth += 1
        elif lines[i].startswith('\\end_'):
            depth -= 1
        elif depth == 0 and lines[i].startswith('\\'):
            (a, v) = _parse_attr(lines[i])
            print('\n\nlines[%d] = %s\n' % (i, lines[i]))
            xout.attr(a, v)
        i += 1

def _lyx2xml(lines, xout, start=0, end=-1, cmd_type=None):
    i = start
    if end < 0:
        end = len(lines)
    prev_i = -1
    while i < end:
        print('\n\nParsing line %d: %s\n' % (i, lines[i]))
        assert i > prev_i
        prev_i = i
        if len(lines[i]) == 0:
            i += 1
        elif lines[i][0] == '#':
            # LyX source comment
            #xout.comment(lines[i][1:])
            i += 1
        elif lines[i].startswith('\\begin_') or lines[i].startswith('\\index '):
            (el, start_tok, end_tok, cmd_type, rest) = _parse_begin(lines[i])
            xout.start_elt(el)
            print('\n\nlines[%d] = %s\n' % (i, lines[i]))
            if rest:
                xout.attr('name', rest)
            e = find_end_of(lines, i, start_tok, end_tok)
            print('\n\nfind_end_of(%d, %s, %s) = %d\n' % (i, start_tok, end_tok, e))
            # XXX Here we need to find any attributes that might be
            # interspersed with child nodes so we can suck them in
            # first.  What a PITA.
            _handle_interspersed_attrs(lines, xout, i + 1, e - 1)
            i = _lyx2xml(lines, xout, i + 1, e - 1, cmd_type)
            print('\n\n_lyx2xml(...) = %d, looking for %d\n' % (i, e))
            if i == e + 1:
                i += 1
            else:
                print('\n\n_lyx2xml() returned %d, e = %d\n' % (i, e))
        elif lines[i].startswith('\\end_'):
            xout.end_elt(el)
            cmd_type = None
            i += 1
        elif len(lines[i]) == 0 or lines[i] == ' ':
            # Ignore empty lines
            i += 1
        elif cmd_type == 'inset':
            # Parse "\begin_inset CommandInset ..." attributes
            print('\n\nlines[%d] = %s\n' % (i, lines[i]))
            while i < end and lines[i] != '' and lines[i] != ' ':
                (a, v) = _parse_attr(lines[i])
                xout.attr(a, v)
                i += 1
            # then suck in content
            cmd_type = None
        elif cmd_type == 'XML':
            # Parse embedded XML contents
            i = _lyxml2xml(lines, xout, i, end)
            cmd_type = None
        elif lines[i][0] == '\\' and not lines[i].startswith('\\begin_') and not lines[i].startswith('\\end_'):
            if not xout.in_tag:
                i += 1
                continue
            (a, v) = _parse_attr(lines[i])
            print('\n\nlines[%d] = %s\n' % (i, lines[i]))
            xout.attr(a, v)
            cmd_type = None
            i += 1
        else:
            xout.text(lines[i])
            cmd_type = None
            i += 1
    return i

def read_lyx(f):
    f = open(f, 'r')
    lines = f.readlines()
    f.close()
    #for i in range(len(lines)):
    #    lines[i] = _chomp(lines[i])
    return lines

def lyx2xml(lines, outcb):
    xout = XmlStreamer(outcb, 'lyx') # pass in name of DTD
    xout.start_elt('lyx')
    sys.stdout.write('\n\n')
    _lyx2xml(lines, xout)
    xout.end_elt('lyx')
    xout.finish()
    return True

def outcb(text):
    sys.stdout.write(text)

lyx2xml(read_lyx('/tmp/test.lyx'), outcb)
