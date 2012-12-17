
import sys

class XmlStreamer(object):
    '''
    This is an XML stream writing class.  Callers use the methods of
    this class to start elements, add attributes, add text nodes, add
    comments, etcetera.  Because this is a streaming interface it's not
    possible to add attributes to an element after adding text nodes.

    The output callback must accept None as an indicator of EOF.

    Use it as follows:
        def outcb(text):
            sys.stdout.write(text)
        xml = XmlStreamer(outcb)
        xml.start_el('root_element')
        xml.attr('foo', 'bar')
        xml.end_el()
        xml.finish()
    '''

    def __init__(self, outcb, doctype=None, dtd=None):
        '''
        The first argument is an output function/closure.  The second
        argument is the doctype of the output XML, while the third is
        the DTD for the output XML.  If a DTD is given then a doctype
        must also be given.
        '''
        assert doctype or not dtd
        self.doctype = doctype
        self.dtd = dtd
        self.outcb = outcb
        self.in_tag = False
        self.in_pi = False
        self.stack = []
        self.depth = 0
        self.el_count = 0
        self.comments = []
        self.outcb('<?xml version="1.0" encoding="UTF-8"?>\n')
        self.in_doctype = False
        if doctype:
            self.outcb('<!DOCTYPE %s ' % (doctype,))
            self.in_doctype = True
        if dtd:
            self.outcb('SYSTEM "%s" ' % (dtd,))
        self.outcb('[\n')

    def _close_doctype(self):
        if self.in_doctype:
            self.outcb('\n]>')
            self.in_doctype = False

    def _comments(self):
        assert not self.in_tag
        if len(self.comments) == 0:
            return
        for c in self.comments:
            self.comment(c)
        self.comments = []

    def public_entity(self, entity, val):
        '''
        Add a PUBLIC entity.
        '''
        assert self.in_doctype
        self.outcb('<!ENTITY %s PUBLIC "" "%s">\n' % (entity, val))

    def system_entity(self, entity, val):
        '''
        Add a SYSTEM entity.
        '''
        assert self.in_doctype
        self.outcb('<!ENTITY %s SYSTEM "%s">\n' % (entity, val))

    def entity(self, entity, val):
        '''
        Add an internal entity.
        '''
        assert self.in_doctype
        self.outcb('<!ENTITY %s "%s">\n' % (entity, val))

    def finish(self):
        '''
        Call when done writing the XML.
        '''
        assert self.depth == 0 and self.el_count > 0
        self._close_doctype()
        self.outcb(None)

    def start_pi(self, pi):
        '''
        Start a processing instruction.
        '''
        self._close_doctype()
        self._comments()
        assert not self.in_tag
        assert not self.in_pi
        assert len(self.stack) == 0
        self.outcb('<?')
        self.outcb(pi)
        self.outcb(' ')
        self.in_pi = True

    def end_pi(self):
        '''
        End a processing instruction.
        '''
        self._close_doctype()
        assert self.in_pi
        self.outcb('?>')
        self.in_pi = False

    def start_elt(self, el):
        '''
        Start an element.
        '''
        self._close_doctype()
        # Can only have one root element
        assert self.depth > 0 or self.el_count == 0
        if self.in_tag:
            self.outcb('>')
        self.in_tag = False
        self._comments()
        self.outcb('<')
        self.outcb(el)
        self.outcb(' ')
        self.stack.append(el)
        self.in_tag = True
        self.depth += 1
        self.el_count += 1

    def end_elt(self, el=None):
        '''
        Close an element.
        '''
        self._close_doctype()
        assert self.depth > 0
        if el and self.stack[-1] != el:
            print('\n\nWTF: el == %s, expecting %s at depth %d\n' % (el, self.stack[-1], self.depth))
            print(self.stack)
        assert not el or self.stack[-1] == el
        if not self.in_tag:
            self.outcb('</')
            self.outcb(el)
            self.outcb('>')
            self.outcb('\n')
        else:
            self.outcb('/>')
        self.in_tag = False
        self.stack.pop()
        self.depth -= 1

    def comment(self, text):
        '''
        Add an XML comment.
        '''
        # We delay addition of comments so we can allow self.comment()
        # to be called before we finish with attributes.  We don't do
        # this for text nodes though, or any other nodes for that
        # matter!
        if self.in_tag or self.in_pi:
            self.comments.append(text)
            return
        self._close_doctype()
        self.outcb('\n<!-- ')
        self.outcb(text)
        self.outcb(' -->\n')

    def attr(self, attr, val):
        '''
        Add an attribute to the currently open element or processing
        instruction.
        '''
        self._close_doctype()
        assert self.in_tag or self.in_pi
        self.outcb(attr)
        self.outcb('="')
        self.outcb(val)
        self.outcb('" ')

    def text(self, text):
        '''
        Add a text node.
        '''
        assert not self.in_doctype
        assert self.depth > 0
        if (self.in_tag):
            self.outcb('>')
        self.in_tag = False
        self._comments()
        self.outcb(text)


def test_xml_streamer():
    def outcb(text):
        if text == None:
            sys.stdout.write('\n\n\nAll done!\n')
        else:
            sys.stdout.write(text)
    xml = XmlStreamer(outcb, 'lyx', 'lyx21.dtd')
    xml.entity('nbsp', 'FOOOOO')
    xml.comment('a comment!')
    xml.start_pi('aPI')
    xml.comment('another comment!')
    xml.attr('do_something', 'yes')
    xml.end_pi()
    xml.start_elt('lyx')
    xml.attr('foo', 'bar')
    xml.attr('bar', '5')
    xml.start_elt('header')
    xml.end_elt('header')
    xml.start_elt('body')
    xml.start_elt('layout')
    xml.comment('comment #3!')
    xml.attr('name', 'Standard')
    xml.text('A paragraph!')
    xml.end_elt('layout')
    xml.start_elt('layout')
    xml.attr('name', 'Standard')
    xml.text('Another paragraph!')
    xml.end_elt('layout')
    xml.comment('An empty paragraph follows')
    xml.start_elt('layout')
    xml.attr('name', 'Standard')
    xml.end_elt('layout')
    xml.comment('An empty element follows')
    xml.start_elt('emptyElement')
    xml.end_elt()
    xml.end_elt('body')
    xml.end_elt('lyx')
    xml.finish()

# test_xml_streamer()
