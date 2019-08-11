__copyright__ = "Copyright (C) 2019 Andreas Kloeckner"

__license__ = """
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""

__doc__ = """
Iterating over pages
--------------------

.. autoclass:: PageIterator

Converting Pages to Text Snippets
---------------------------------

The purpose of this bit of functionality is to take a
:class:`pdfminer.layout.LTPage` and produce a list of
:class:`TextLine` instances, i.e. little snippets of text
annotated with position and font information.

.. autoclass:: TextLine
.. autoclass:: gather_text

Find Information in Text Snippets
---------------------------------

.. function:: find_row_table(headers, lines)

    :arg headers: a list of `TextLine` instances, each of which represents a
        table header
    :arg lines: a list of :class:`TextLine` instances
    :returns: A list of dictionaries containing JSON-style data gathered from
        the rows of data contained in *lines*, annotated with keys from
        *headers*. The keys in the dictionaries are text lines, the values
        are :class:`TextLine` instances.

.. function:: find_col_table(headers, lines)

    Like :func:`find_row_table` but for tables where "rows" are vertical.
"""

import re
from functools import partial

from pdfminer.converter import PDFPageAggregator
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.pdfpage import PDFPage
from pdfminer.layout import (
        LAParams,
        LTContainer,
        LTTextBoxHorizontal, LTTextLineHorizontal, LTChar, LTAnno,
        LTRect, LTLine)


# {{{ pdf page iterator

class PageIterator:
    def __init__(self, document, laparams=None):
        if laparams is None:
            laparams = LAParams()

        self._page_iterator = iter(PDFPage.create_pages(document))
        self._page = next(self._page_iterator)

        rsrcmgr = PDFResourceManager()
        self.device = PDFPageAggregator(rsrcmgr, laparams=laparams)

        self.interpreter = PDFPageInterpreter(rsrcmgr, self.device)

        self._lines = None
        self.i_page = 1
        self.is_at_end = False

    def advance(self):
        try:
            self._page = next(self._page_iterator)
        except StopIteration:
            self.is_at_end = True

        self._lines = None
        self.i_page += 1

    @property
    def lines(self):
        if self._lines is None:
            self.interpreter.process_page(self._page)
            self._lines = gather_text(self.device.get_result())

        return self._lines

# }}}


# {{{ pdf text gathering

class TextLine:
    """
    .. attribute:: text
    .. attribute:: fontname
    .. attribute:: x0

        Minimum X coordinate of bounding box

    .. attribute:: y0

        Minimum Y coordinate of bounding box

    .. attribute:: x1

        Maximum X coordinate of bounding box

    .. attribute:: y1

        Maximum Y coordinate of bounding box
    """

    def __init__(self, text, fontname, bbox):
        self.text = text
        self.fontname = fontname
        (self.x0, self.y0, self.x1, self.y1) = bbox

    def __str__(self):
        result = self.text
        if "Bold" in self.fontname:
            result = f"*{result}*"
        return result

    def __repr__(self):
        return f"TL({repr(str(self))})"

    def copy(self, text=None):
        return type(self)(
                text=(text if text is not None else self.text),
                fontname=self.fontname,
                bbox=(self.x0, self.y0, self.x1, self.y1))


def gather_text(item, lines=None):
    """
    :arg item: :class:`pdfminer.layout.LTItem`, often a
        :class:`pdfminer.layout.LTPage`
    :arg lines: a list to which gathered :class:`TextLine` instances are added
    :returns: a list of :class:`TextLine` instances
    """
    if lines is None:
        lines = []

    if isinstance(item, LTTextBoxHorizontal):
        for line in item:
            assert isinstance(line, LTTextLineHorizontal)

            line_contents = []
            fontname = None
            for line_item in line:
                if isinstance(line_item, LTAnno):
                    # Assert that nothing useful is here.
                    assert not line_item._text.strip(), line_item._text

                elif isinstance(line_item, LTChar):
                    line_contents.append(line_item._text)

                    if fontname is None:
                        fontname = line_item.fontname
                    elif fontname != line_item.fontname:
                        from warnings import warn
                        warn(
                                "Font name changed mid-line, "
                                f"from '{fontname}' "
                                f"to '{line_item.fontname}'. "
                                "Using initial font name for line.")

                else:
                    raise ValueError(
                            f"unexpected item on line: {type(line_item)}")

            lines.append(TextLine(
                text="".join(line_contents),
                fontname=fontname,
                bbox=line.bbox))

    elif isinstance(item, LTContainer):
        for subitem in item:
            gather_text(subitem, lines)

    elif isinstance(item, (LTRect, LTLine)):
        pass

    else:
        raise ValueError(
            f"unexpected item type: {type(item)}")

    return lines

# }}}


# {{{ pdf info slurping

class GroupNotFound(Exception):
    pass


def overlap(a_min, a_max, b_min, b_max):
    assert b_min <= b_max

    begin_overlap = max(a_min, b_min)
    end_overlap = min(a_max, b_max)

    return max(0, end_overlap - begin_overlap)


def find_lines_with(regex, lines):
    """
    :arg regex: a regular expression or a string that can be compiled to one
    :returns: a list of tuples ``(text_line, match_object)` for found matches
    """
    if isinstance(regex, str):
        regex = re.compile(regex)
    result = []
    for l in lines:
        match = regex.search(l.text)
        if match is not None:
            result.append((l, match))
    return result


def get_attr_lookup(lines, attr_name):
    """
    :arg lines: a list of :class:`TextLine` instances
    :arg attr_name: A string, e.g. ``"y0"``, an attribute
        of :class:`TextLine`
    :returns: A dictionary of strings mapping values of
        the given attribute to lists of :class:`TextLine`
        sharing that attribute.

    This function can be used to identify lines of text or
    rows in a table. Note that it relies on *exactly* matching
    coordinates.
    """
    result = {}
    for l in lines:
        result.setdefault(getattr(l, attr_name), []).append(l)
    return result


def find_attr_group_matching(regexes, attr_name, lines):
    """ Find a group of :class:`TextLine` instances containing
    matches of *regexes*. Can be used to find table headers
    with known content.

    :arg regexes: A list of regular expressions, or strings
         that can be compiled to them.
    :arg attr_name: A string, e.g. ``"y0"``, an attribute
        of :class:`TextLine`
    :arg lines: a list of :class:`TextLine` instances
    :returns: Finds the attribute value (e.g. ``"y0"``)
        shared by the :class:`TextLine` instances
        containing matches of *regexes*.
    """

    regexes = [
            re.compile(regex) if isinstance(regex, str) else regex
            for regex in regexes]

    attr_lookup = get_attr_lookup(lines, attr_name)
    result = [
            attr_value
            for attr_value, row_lines in attr_lookup.items()
            if all(
                any(
                    regex.search(l.text) is not None
                    for l in row_lines)
                for regex in regexes)]

    if len(result) < 1:
        raise GroupNotFound()
    if len(result) > 1:
        raise RuntimeError("more than one group found matching")

    attr_value, = result
    return attr_value


def merge_overlapping_rows(rows, row_min_attr_name, row_max_attr_name):
    def get_row_extent(row):
        return (
            min(getattr(line, row_min_attr_name) for line in row.values()),
            max(getattr(line, row_max_attr_name) for line in row.values()))

    if not rows:
        return rows

    new_rows = []

    row = rows[0]
    i_row = 1

    while i_row < len(rows):
        # row is valid and still needs to be added to new_rows
        next_row = rows[i_row]

        row_min, row_max = get_row_extent(row)
        next_row_min, next_row_max = get_row_extent(next_row)

        if overlap(row_min, row_max, next_row_min, next_row_max):
            row.update(next_row)
            i_row += 1

        else:
            new_rows.append(row)
            i_row += 1
            row = next_row

    new_rows.append(row)

    return new_rows


def find_table(
        headers, lines, row_min_attr_name, row_max_attr_name,
        col_min_attr_name, col_max_attr_name,
        reverse_sort, heading_bias="centered"):
    headers = sorted(headers, key=lambda l: getattr(l, col_min_attr_name))
    row_lookup = get_attr_lookup(lines, row_min_attr_name)

    rows = []
    for row_lookup_key in sorted(row_lookup, reverse=reverse_sort):
        row_lines = row_lookup[row_lookup_key]
        row = {}
        rows.append(row)
        for l in row_lines:
            lmin = getattr(l, col_min_attr_name)
            lmax = getattr(l, col_max_attr_name)
            assert lmin <= lmax

            lctr = (lmin+lmax)*0.5

            overlaps_and_headers = [
                    (overlap(
                        getattr(h, col_min_attr_name),
                        getattr(h, col_max_attr_name),
                        lmin, lmax), h)
                    for h in headers
                    ]
            possible_headers = [
                    (ovl, h) for ovl, h in overlaps_and_headers
                    if ovl]

            if len(possible_headers) == 0:
                # no overlap at all, typically a very short entry

                if heading_bias == "centered":
                    # fall back to minimum center distance
                    _, h = min(
                            (abs(
                                0.5*(
                                    getattr(h, col_min_attr_name)
                                    + getattr(h, col_max_attr_name))
                                - lctr), h)
                            for h in headers)
                    key = h.text

                elif heading_bias == "min":
                    # Use next-nearest left overlapping header

                    _, h = max(
                            (getattr(h, col_min_attr_name), h)
                            for h in headers
                            if getattr(h, col_min_attr_name) <= lmin)
                    key = h.text

                else:
                    raise ValueError("unrecognized heading bias")

            elif len(possible_headers) == 1:
                (_, h), = possible_headers
                key = h.text

            elif len(possible_headers) > 1:
                # Use left/topmost overlapping header

                _, h = min(
                        (getattr(h, col_min_attr_name), h)
                        for ovl, h in possible_headers)
                key = h.text

            if key in row:
                raise ValueError(f"duplicate assignment of key '{key}'")
            else:
                row[key] = l

    return rows


find_row_table = partial(
        find_table,
        row_min_attr_name="y0",
        row_max_attr_name="y1",
        col_min_attr_name="x0",
        col_max_attr_name="x1",
        reverse_sort=True)

find_col_table = partial(
        find_table,
        row_min_attr_name="x0",
        row_max_attr_name="x1",
        col_min_attr_name="y0",
        col_max_attr_name="y1",
        reverse_sort=False)

# }}}


def print_pdf_outline(item, level=0):
    indent = "    "*level

    if isinstance(item, LTContainer):
        print(f"{indent}{type(item)}")
        for subitem in item:
            print_pdf_outline(subitem, level=level+1)

    else:
        print(f"{indent}{type(item)}")


# vim: foldmethod=marker
