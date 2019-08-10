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
Data handling
-------------

This module contains tools for quickly inserting JSON-ish list-of-dicts data
into a DB-API v2-compliant database. Mildly specific to :mod:`sqlite3`, but
likely easily generalized.

.. autofunction:: set_up_table
.. autofunction:: row_to_db
"""


import sqlite3


# {{{ sqlite utilities

def set_up_table(db, table_name, col_names_and_types):
    rowspecs = ", ".join(
            f"{name} {type}" for name, type in col_names_and_types)
    try:
        db.execute(
            f"create table {table_name} (id integer primary key, {rowspecs})")
    except sqlite3.OperationalError as e:
        if "already exists" in str(e):
            return
        else:
            raise


def key_to_col_name(key, col_name_mapping):
    return col_name_mapping.get(key, key.lower().replace(" ", "_"))


def row_to_db(
        db_cursor, table_name, row, *,
        col_name_mapping=None, value_converters=None,
        upsert_unique_cols=None):

    if col_name_mapping is None:
        col_name_mapping = {}

    if value_converters is None:
        value_converters = {}

    col_names = []
    values = []
    for key, value in row.items():
        col_names.append(key_to_col_name(key, col_name_mapping))
        if key in value_converters:
            value = value_converters[key](value)
        values.append(value)

    if upsert_unique_cols:
        for col in upsert_unique_cols:
            assert col in col_names

        where_clause = " and ".join(
                f"{col_name}=?"
                for col_name in col_names
                if col_name in upsert_unique_cols)

        upsert_values = [
                value for col_name, value in zip(col_names, values)
                if col_name in upsert_unique_cols]

        other_rows = list(db_cursor.execute(
                f"select id from {table_name} where {where_clause} limit 2",
                upsert_values))

        if len(other_rows) == 1:
            return other_rows[0][0]
        elif len(other_rows) > 1:
            raise ValueError(f"non-unique row in table {table_name}")
        else:
            # fall through to insertion below
            pass

    placeholders = ", ".join("?" for col in col_names)
    col_names = ", ".join(col_names)

    db_cursor.execute(
            f"insert into {table_name} ({col_names}) values ({placeholders})",
            values)

    return db_cursor.lastrowid

# }}}

# vim: foldmethod=marker
