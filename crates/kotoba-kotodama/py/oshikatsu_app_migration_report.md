For src/kotodama/primitives/oshikatsu_app.py:

- Cursor blocks converted:
  The database interaction in this file was already abstracted into `_write`, `_list`, and `_find` functions.
  The primary conversion was replacing the import `from kotodama.db_sync import sync_cursor` with `from kotodama.kotoba_datomic import get_kotoba_client`.
  The `_write` function uses `get_kotoba_client().insert_row` for all write operations.
  The `_list` function uses `get_kotoba_client().select_where`.

- `# R0:` caveat:
  The `_list` function contains the comment `# R0: Fetching a broader set with select_where and applying ordering/pagination in Python` as it retrieves a broader set of rows and applies ordering/pagination in Python.

- Confirmation:
  NO `sync_cursor`, `db_sync`, or raw SQL remains in the edited file.
