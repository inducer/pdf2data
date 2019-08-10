#! /usr/bin/env python3

from pdfminer.pdfparser import PDFParser
from pdfminer.pdfdocument import PDFDocument
from pdfminer.layout import LAParams

from pdf2data.pdf import (
        PageIterator, find_attr_group_matching, find_row_table,
        merge_overlapping_rows)


# schools.pdf data set from
# https://github.com/tabulapdf/tabula-java/blob/9960775528f6ff09dcb41830ea48eb89a73f3b49/src/test/resources/technology/tabula/schools.pdf

def main():
    with open("schools.pdf", "rb") as pdf_fileobj:

        document = PDFDocument(PDFParser(pdf_fileobj))
        page_it = PageIterator(document, LAParams(char_margin=0.2))

        while not page_it.is_at_end:
            # identify top of table
            top_y0 = find_attr_group_matching(
                    ["Last Name", "First Name"], "y0", page_it.lines)

            # extract text snippets making up table body
            table_lines = [l for l in page_it.lines if l.y0 < top_y0]

            # extract header text snippets
            headers = [l for l in page_it.lines if abs(l.y0 - top_y0) < 5]

            # extract table
            rows = find_row_table(headers, table_lines)
            rows = merge_overlapping_rows(rows, "y0", "y1")

            for row in rows:
                print(row)

            page_it.advance()


if __name__ == "__main__":
    main()
