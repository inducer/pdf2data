#! /bin/bash

# A script to merge the ongoing stream of statements into one main database while keeping
# backups.

set -e

NEW_STMT="$1"

if test "$NEW_STMT" = ""; then
  echo "usage: $0 statement.pdf"
  exit 1
fi

STMT_DIR="$(dirname $NEW_STMT)"
if [ "$STMT_DIR" != "source-data" ]; then
  echo "### WARNING ###"
  echo "It seems that $NEW_STMT has not been moved to the source-data folder."
  echo "Hit Enter to continue anyway, or ^C to abort."
  echo "### WARNING ###"
  read ENTER
fi
STMT_BASE="$(basename $NEW_STMT)"
STMT_BASE="${STMT_BASE%.pdf}"
STMT_BASE="${STMT_BASE%.pdf}"

if ls *-journal 1> /dev/null 2>&1; then
  echo "Database has live rollback journal, aborting."
  exit 1
fi

TIMESTAMP="$(date +%Y-%m-%d-%H%M-%S)"

if ! which read-uiuc-fin-statement 1> /dev/null 2>&1; then
  echo "statement reader binary not found"
  exit 1
fi

cp "statements.sqlite3" "backup/statements-$TIMESTAMP-before-$STMT_BASE.sqlite3"

read-uiuc-fin-statement "$NEW_STMT"
