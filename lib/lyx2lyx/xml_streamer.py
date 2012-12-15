
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

    def __init__(self, outcb, doctype=None, dtd=None, entities=[]):
        '''
        The first argument is an output function/closure.  The second
        argument is the doctype of the output XML, while the third is
        the DTD for the output XML.  The fourth argument is a list of
        entity tuples.
        '''
        self.entities = entities
        self.doctype = doctype
        self.dtd = dtd
        self.outcb = outcb
        self.in_tag = False
        self.in_pi = False
        self.stack = []
        self.depth = 0
        self.el_count = 0
        outcb('<?xml version="1.0" encoding="UTF-8"?>\n')
        if doctype and dtd:
            outcb('<!DOCTYPE %s SYSTEM "%s" [\n' % (doctype, dtd))
            for entity in entities:
                if len(entity) > 2 and entity[1] == 'PUBLIC' and entity[2][0:4] == 'file:':
                    outcb('<!ENTITY %s SYSTEM "%s">' % (entity[0], entity[2][7:]))
                elif len(entity) > 2 and entity[1] == 'SYSTEM':
                    outcb('<!ENTITY %s SYSTEM "%s">' % (entity[0], entity[2]))
                elif len(entity) > 2 and entity[1] == 'PUBLIC':
                    outcb('<!ENTITY %s PUBLIC "" "%s">' % (entity[0], entity[2]))
                else:
                    assert len(entity) == 2
                    outcb('<!ENTITY %s "%s">' % entity)
            outcb('\n]>')

    def finish(self):
        '''
        Call when done writing the XML.
        '''
        assert self.depth == 0 and self.el_count > 0
        self.outcb(None)

    def start_pi(self, pi):
        '''
        Start a processing instruction.
        '''
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
        assert self.in_pi
        self.outcb('?>')
        self.in_pi = False

    def start_elt(self, el):
        '''
        Start an element.
        '''
        # Can only have one root element
        assert self.depth > 0 or self.el_count == 0
        if self.in_tag:
            self.outcb('>')
        self.in_tag = False
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
        assert self.depth > 0
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
        if self.in_tag:
            self.outcb('>')
        self.in_tag = False
        self.outcb('\n<!-- ')
        self.outcb(text)
        self.outcb(' -->\n')

    def attr(self, attr, val):
        '''
        Add an attribute to the currently open element or processing
        instruction.
        '''
        assert self.in_tag or self.in_pi
        self.outcb(attr)
        self.outcb('="')
        self.outcb(val)
        self.outcb('" ')

    def text(self, text):
        '''
        Add a text node.
        '''
        assert self.depth > 0
        if (self.in_tag):
            self.outcb('>')
        self.in_tag = False


def test_xml_streamer():
    def outcb(text):
        if text == None:
            sys.stdout.write('\n\n\nAll done!\n')
        else:
            sys.stdout.write(text)
    xml = XmlStreamer(outcb, 'lyx', 'lyx21.dtd')
    xml.comment('a comment!')
    xml.start_pi('aPI')
    xml.attr('do_something', 'yes')
    xml.end_pi()
    xml.start_elt('lyx')
    xml.attr('foo', 'bar')
    xml.attr('bar', '5')
    xml.start_elt('header')
    xml.end_elt('header')
    xml.start_elt('body')
    xml.start_elt('layout')
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

test_xml_streamer()
