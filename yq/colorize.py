#!/usr/bin/env python
'''colourize data as :program:`jq` does
'''

# stdlib
import curses
import functools
import itertools
import os

# dependencies
try:
    import pygments, pygments.formatters, pygments.lexers
except ImportError:
    pygments = None


def styling_available(stream, force=False):
    '''check if `stream` support styling, initializing it if required

    Check if `stream` does support styling implicitely (ie.: it's a terminal)
    or explicitely (if `force` is True), calling :func:`curses.setupterm`
    if possible.

    Idea from Erik Rose `Blessings <https://github.com/erikrose/blessings>`.

    :param file stream:
    :param bool force:
    :rtype: bool
    '''
    answer = False
    if pygments is None:
        return answer

    try:
        stream_descriptor = stream.fileno()
    except Exception:
        return answer

    is_a_tty = os.isatty(stream_descriptor)

    if is_a_tty or force:
        try:
            curses.setupterm(
                os.environ.get('TERM', 'dumb') or 'dumb',
                stream_descriptor,
            )
            answer = is_a_tty or force
        except curses.error:
            pass

    return answer


class HighlightWriter:
    '''wraps an highlighter around a file object
    '''
    def __init__(self, src, highlighter):
        '''
        :param file src: the file object
        '''
        self.__src = src
        self.__buf = []
        self.__hig = highlighter
        self.__nil = None

    def __getattr__(self, name):
        return getattr(self.__src, name)

    def flush(self):
        if self.__buf:
            self.writelines('')
        self.__src.flush()

    def __enter__(self):
        return self

    def __exit__(self, *args, **kwargs):
        self.flush()

    def close(self):
        self.flush()
        return self.__src.close()

    def write(self, text):
        self.__buf.append(text)
        if text and text[-1] in {'\n', '\r'}:
            return self.writelines('')

    def writelines(self, sequence_of_strings):
        try:
            if self.__nil is None:
                if self.__buf:
                    self.__nil = type(self.__buf[0])()
                    empty = self.__nil
                else:
                    empty = type(sequence_of_strings)()
            else:
                empty = self.__nil

            data = empty.join(itertools.chain(self.__buf, sequence_of_strings))

            return self.__src.writelines(
                self.__hig(data)
            )

        finally:
            del self.__buf[:]


def wraps(stream, dialect='text'):
    '''wraps :func:`pygments.highlight` around an io stream,
    when possible

    :param file stream: output stream
    :param str dialect: :mod:`pygments` dialect
                        (see http://pygments.org/docs/lexers/)
    :rtype: file
    '''
    if pygments is None:
        return stream

    formatter_name = 'terminal'

    try:
        colours = curses.tigetnum('colours')
        if colours == 256:
            formatter_name += '256'
        elif colours > 256:
            formatter_name += '16m'
        lexer = pygments.lexers.get_lexer_by_name(dialect)
        formatter = pygments.formatters.get_formatter_by_name(formatter_name)

    except pygments.util.ClassNotFound:
        return stream

    highlighter = functools.partial(
        pygments.highlight,
        lexer=lexer,
        formatter=formatter,
    )

    return HighlightWriter(stream, highlighter)
