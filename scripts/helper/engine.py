"""Shared disposable query engine: in-memory DuckDB over invocation-local rows.

Every input becomes a connection-local view. Nothing is written to disk: the
temporary directory, external file access and extension loading are disabled
before the query runs, and the connection is closed before results are returned.
Callers keep inputs in memory only; no databases, spill files or JSON exports.
"""
import json
import math
import re
import threading
from dataclasses import dataclass, field

IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
SIZE = re.compile(r"^\d+(?:\.\d+)?(?:B|KB|MB|GB|TB)?$", re.IGNORECASE)
REFERENCES = ("ref", "call_ref", "result_ref")
MAX_COLUMNS = 200
DEFAULT_MEMORY = "512MB"
DEFAULT_SECONDS = 10.0
# SQLite heap ceiling. Process-wide and can only be lowered, so every query context sets the same value.
SQLITE_HEAP = 512 * 1024 * 1024
# Output cap when --limit is omitted, so the query's own LIMIT governs.
DEFAULT_ROW_CAP = 1000
INSTALL = ("DuckDB and PyArrow are required for SQL queries; install the pinned "
           "dependencies in requirements.txt (see references/reader.md)")


class EngineError(ValueError):
    """A query that cannot be answered within the disposable engine's bounds."""


@dataclass
class Input:
    """One named view: rows plus the coverage and schema supplied by its producer."""
    name: str | None
    rows: list
    upstream: dict = field(default_factory=dict)
    columns: list | None = None
    types: dict = field(default_factory=dict)
    grain: str | None = None


TYPE_ALIASES = {"BIGINT": "int", "INTEGER": "int", "INT": "int", "SMALLINT": "int",
                "DOUBLE": "float", "REAL": "float", "FLOAT": "float",
                "VARCHAR": "str", "TEXT": "str", "STRING": "str", "JSON": "str",
                "BOOLEAN": "bool", "BOOL": "bool"}


def _dependency(name):
    try:
        return __import__(name)
    except ImportError:
        raise EngineError(f"{name}: {INSTALL}") from None


def columns(records, hint=None):
    """Union of declared and observed keys, in stable order; reject non-object rows.

    A hint keeps a known schema when a selection is empty, so a query over zero
    matched rows still binds its columns instead of failing.
    """
    if not isinstance(records, list) or any(not isinstance(row, dict) for row in records):
        raise EngineError("Every input row must be an object")
    names = {key for row in records for key in row if isinstance(key, str)}
    if hint is not None:
        if not isinstance(hint, (list, tuple)) or any(not isinstance(key, str) for key in hint):
            raise EngineError("Declared columns must be field names")
        names.update(hint)
    names = sorted(names)
    if "_row" in names:
        raise EngineError("_row is reserved for the invocation-local ordinal")
    if len(names) > MAX_COLUMNS:
        raise EngineError(f"Maximum {MAX_COLUMNS} columns per input")
    return names


def infer_type(values):
    """Public column inference shared by declared schemas and summaries."""
    return _kind(values)


def _kind(values):
    """One Arrow-friendly column type; mixed types widen instead of failing.

    Numbers widen to float, anything with text or structured values becomes a
    string, and objects/arrays are encoded as bounded JSON strings.
    """
    kinds = set()
    for value in values:
        if value is None:
            continue
        if isinstance(value, bool):
            kinds.add("bool")
        elif isinstance(value, int):
            kinds.add("int")
        elif isinstance(value, float):
            kinds.add("float")
        elif isinstance(value, str):
            kinds.add("str")
        else:
            kinds.add("other")
    if not kinds:
        return "str"
    if kinds <= {"bool"}:
        return "bool"
    if kinds <= {"bool", "int"}:
        return "int" if all(-(2 ** 63) <= v < 2 ** 63 for v in values if isinstance(v, int)) else "str"
    if kinds <= {"bool", "int", "float"}:
        return "float"
    return "str"


def _text(value):
    if isinstance(value, str):
        return value
    if isinstance(value, (bytes, bytearray, memoryview)):
        return bytes(value).hex()
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _scalar(value, kind):
    if value is None:
        return None
    if kind == "bool":
        return bool(value)
    if kind == "int":
        return int(value)
    if kind == "float":
        return float(value)
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=True, default=_text, separators=(",", ":"))
    if isinstance(value, bool):
        return "true" if value else "false"
    return _text(value)


def _table(pa, records, names, types=None):
    """Arrow table with an explicit schema, so empty selections keep their columns."""
    types = types or {}
    arrays = [pa.array(range(len(records)), type=pa.int64())]
    fields = [pa.field("_row", pa.int64())]
    for name in names:
        values = [row.get(name) for row in records]
        declared = types.get(name)
        if declared is not None:
            kind = TYPE_ALIASES.get(str(declared).upper())
            if kind is None:
                raise EngineError(f"Unknown --type {declared!r}; use BIGINT, DOUBLE, VARCHAR, BOOLEAN, or JSON")
        else:
            kind = _kind(values)
        arrow_type = {"bool": pa.bool_(), "int": pa.int64(), "float": pa.float64()}.get(kind, pa.string())
        arrays.append(pa.array([_scalar(value, kind) for value in values], type=arrow_type))
        fields.append(pa.field(name, arrow_type))
    return pa.Table.from_arrays(arrays, schema=pa.schema(fields))


def _configure(connection, memory):
    """Disable every disk path before any input is registered."""
    settings = (
        f"SET memory_limit='{memory}'",
        "SET threads=1",
        "SET temp_directory=''",           # must precede external-access lockdown
        "SET max_temp_directory_size='0B'",
        "SET enable_external_access='false'",
        "SET autoinstall_known_extensions=false",
        "SET autoload_known_extensions=false",
        "SET disabled_filesystems='LocalFileSystem'",
        "SET enable_progress_bar=false",
        "SET lock_configuration=true",
    )
    for statement in settings:
        connection.execute(statement)


def _message(error):
    text = str(error).strip().splitlines()
    return (text[0] if text else type(error).__name__)[:500]


def _jsonable(value):
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else str(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        return {"encoding": "hex", "value": bytes(value).hex()}
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def evaluate(inputs, sql=None, limit=None, seconds=DEFAULT_SECONDS, memory=DEFAULT_MEMORY,
             params=None, grain=None):
    """Query named views and return a bounded envelope.

    inputs: Input objects, or legacy (name, rows, upstream[, columns[, types]]).
    Positional aliases are t0, t1, ...; `rows` aliases the first view. With
    sql=None only input summaries are returned, so describing needs no engine.
    params bind named query parameters; grain labels one input row. limit=None
    caps output at DEFAULT_ROW_CAP so a SQL LIMIT below it is never overridden.
    """
    if limit is None:
        limit = DEFAULT_ROW_CAP
    if not isinstance(limit, int) or limit <= 0:
        raise EngineError("--limit must be positive")
    if not isinstance(seconds, (int, float)) or seconds <= 0:
        raise EngineError("--query-seconds must be positive")
    if not SIZE.fullmatch(str(memory)):
        raise EngineError("--memory-limit takes a size such as 256MB")
    normalized = []
    for item in inputs:
        if isinstance(item, Input):
            normalized.append(item)
            continue
        name, records, upstream, *declared = item
        columns_hint = declared[0] if declared else None
        types = declared[1] if len(declared) > 1 else {}
        normalized.append(Input(name, records, upstream, columns_hint, types))
    summaries, seen, prepared = [], set(), []
    for index, item in enumerate(normalized):
        name, records, upstream, declared = item.name, item.rows, item.upstream, (item.columns, item.types)
        name, alias = name or f"t{index}", f"t{index}"
        if not IDENTIFIER.fullmatch(name):
            raise EngineError(f"View name must be an identifier: {name!r}")
        if name == "rows" and index:
            raise EngineError("rows is reserved for the first view")
        for label in {name, alias}:
            if label in seen:
                raise EngineError(f"Duplicate view name: {label}")
            seen.add(label)
        hint = list(dict.fromkeys(list(declared[0] or []) + list((declared[1] or {}).keys())))
        names = columns(records, hint or None)
        summary = {"view": name, "rows": len(records), "columns": names, "upstream": upstream,
                   "types": {column: (declared[1] or {}).get(column) or infer_type([row.get(column) for row in records])
                             for column in names},
                   "grain": item.grain or grain}
        if name != f"t{index}":
            summary["alias"] = f"t{index}"
        summaries.append(summary)
        prepared.append((name, f"t{index}", records, names, declared[1] or {}))
    if sql is None:
        return {"scope": {"inputs": summaries, "grain": grain}, "results": []}
    if params is not None:
        if not isinstance(params, dict) or any(not isinstance(k, str) or not IDENTIFIER.fullmatch(k) for k in params):
            raise EngineError("--param names must be identifiers")

    duckdb = _dependency("duckdb")
    pa = _dependency("pyarrow")
    try:
        statements = duckdb.extract_statements(sql)
    except duckdb.Error as error:
        raise EngineError(_message(error)) from None
    if len(statements) != 1 or statements[0].type != duckdb.StatementType.SELECT:
        raise EngineError("Supply one read-only SELECT or WITH query; use CTEs instead of extra statements")

    fetched = []
    connection, timer = None, None
    try:
        connection = duckdb.connect(":memory:")
        _configure(connection, memory)
        for name, alias, rows, names, types in prepared:
            table = _table(pa, rows, names, types)
            connection.register(name, table)
            if alias != name:
                connection.register(alias, table)
        if prepared and prepared[0][0] != "rows":
            connection.execute(f'CREATE VIEW "rows" AS SELECT * FROM "{prepared[0][0]}"')
        # A deadline replaces step counting; interrupt() ends a runaway query.
        def interrupt():
            try:
                connection.interrupt()
            except Exception:  # the query may have finished as the deadline fired
                pass

        timer = threading.Timer(seconds, interrupt)
        timer.daemon = True
        timer.start()
        cursor = connection.execute(sql, params) if params else connection.execute(sql)
        if cursor.description is None:
            raise EngineError("Supply a read-only SELECT query")
        names = [column[0] for column in cursor.description]
        if len(set(names)) != len(names):
            raise EngineError("Duplicate output columns: alias join columns explicitly")
        fetched = cursor.fetchmany(limit + 1)
        total = len(fetched)
        if total > limit:
            # Count the rest under the same deadline so a capped page states the full size.
            while chunk := cursor.fetchmany(10000):
                total += len(chunk)
    except duckdb.InterruptException:
        raise EngineError(f"Query exceeded {seconds:g}s; narrow the scan or raise --query-seconds") from None
    except duckdb.Error as error:
        raise EngineError(_message(error)) from None
    except MemoryError:
        raise EngineError("Query exceeded available memory; lower --limit or add filters") from None
    finally:
        if timer is not None:
            timer.cancel()
        if connection is not None:
            connection.close()

    rows = []
    for record in fetched[:limit]:
        row = {}
        for key, value in zip(names, record):
            value = _jsonable(value)
            if key in REFERENCES and isinstance(value, str):
                try:
                    parsed = json.loads(value)
                except ValueError:
                    parsed = None
                if isinstance(parsed, (dict, list)):
                    value = parsed
            row[key] = value
        rows.append(row)
    result = {"scope": {"engine": f"duckdb {duckdb.__version__}", "inputs": summaries,
                        "counting_scope": "supplied rows only", "query": sql, "grain": grain,
                        "param_names": sorted(params) if params else []},
              "results": rows, "omissions": {"more_query_rows": total > limit},
              "next": ["For an aggregate, select the contributing refs with the same predicates; "
                       "upstream omissions still apply."]}
    if total > limit:
        result["status"] = "partial"
        result["omissions"].update(query_rows_total=total, query_rows_returned=len(rows))
        result["next"].insert(0, f"Query returned {len(rows)} of {total} rows; rerun with --limit {total} "
                                 "or narrow the query.")
    dropped = sum(summary["upstream"].get("rows_omitted", 0) for summary in summaries)
    truncated = sum(summary["upstream"].get("text_truncated_events", 0) for summary in summaries)
    if truncated:
        result["status"] = "partial"
        result["omissions"]["text_truncated_events"] = truncated
        result["next"].insert(0, "Input text was budget-omitted; full-text predicates may be incomplete.")
    incomplete = [summary for summary in summaries if summary["upstream"].get("complete") is False]
    if incomplete:
        result["status"] = "partial"
        result["omissions"]["incomplete_inputs"] = [summary["view"] for summary in incomplete]
        reasons = {summary["view"]: summary["upstream"]["incomplete_reasons"] for summary in incomplete
                   if summary["upstream"].get("incomplete_reasons")}
        if reasons:
            result["omissions"]["incomplete_reasons"] = reasons
        result["next"].insert(0, "Inputs report a scan, discovery, query or output limit, or a source error "
                                 "(see omissions.incomplete_reasons and scope.inputs[].upstream); "
                                 "joins and counts over them may be incomplete.")
    if dropped:
        # Never let a clipped page pass for the whole selection.
        result["status"] = "partial"
        result["omissions"]["upstream_rows"] = dropped
        result["next"].insert(0, "Input omitted rows, so aggregates undercount; "
                                 "rerun as sessions.py select --sql '...'.")
    return result


class SQLiteQuery:
    """One disposable SQL context for planning and execution.

    SQLite's compiler/authorizer resolves tables and columns, including CTE scope.
    Planning uses empty declared tables; providers are loaded only after validation.
    No lexical SQL dependency guesses and no external access or durable databases.
    """
    def __init__(self, schemas, seconds=10.0):
        import sqlite3
        import time
        self.sqlite3, self.time = sqlite3, time
        if seconds <= 0:
            raise EngineError("Query deadline must be positive")
        self.deadline = time.monotonic() + seconds
        self.connection = sqlite3.connect(":memory:")
        self.connection.execute(f"PRAGMA hard_heap_limit={SQLITE_HEAP}")
        self.connection.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, 4 * 1024 * 1024)
        self.connection.setlimit(sqlite3.SQLITE_LIMIT_SQL_LENGTH, 128 * 1024)
        self.connection.execute("PRAGMA temp_store=MEMORY")
        self.schemas = schemas
        self.reads = {}
        self.inputs = {}
        self.sql, self.params = None, None
        try:
            for name, schema in schemas.items():
                if not IDENTIFIER.fullmatch(name) or not schema:
                    raise EngineError(f"Invalid or empty table schema: {name}")
                declared = []
                for column, kind in schema.items():
                    if not isinstance(column, str) or not column or '\x00' in column:
                        raise EngineError("Column names must be nonempty strings without NUL")
                    value = TYPE_ALIASES.get(str(kind).upper())
                    if value is None:
                        raise EngineError(f"Unknown column type: {kind}")
                    sql_type = {"int": "INTEGER", "bool": "INTEGER", "float": "REAL", "str": "TEXT"}[value]
                    declared.append('"' + column.replace('"', '""') + '" ' + sql_type)
                self.connection.execute(f'CREATE TABLE "{name}" (' + ','.join(declared) + ')')
            self.rootpages = {page: name for name, page in self.connection.execute(
                "SELECT name, rootpage FROM sqlite_master WHERE type='table'")}
            self.connection.set_progress_handler(lambda: int(time.monotonic() > self.deadline), 1000)
        except Exception:
            self.close()
            raise

    def _authorize(self, action, arg1, arg2, database, trigger):
        s = self.sqlite3
        if action == s.SQLITE_READ:
            if arg1 not in self.schemas:
                # COUNT(*) over a CTE reads the CTE by name with no column; SQLite's own tables stay denied.
                return s.SQLITE_OK if arg2 == "" and not (arg1 or "").lower().startswith("sqlite_") else s.SQLITE_DENY
            self.reads.setdefault(arg1, set()).add(arg2)
        if action == s.SQLITE_FUNCTION and (arg2 or "").lower() in ("load_extension", "readfile", "writefile"):
            return s.SQLITE_DENY
        return s.SQLITE_OK if action in (s.SQLITE_SELECT, s.SQLITE_READ, s.SQLITE_FUNCTION, s.SQLITE_RECURSIVE) else s.SQLITE_DENY

    def plan(self, sql, params=None):
        if not isinstance(sql, str) or not sql.strip():
            raise EngineError("Supply one read-only SELECT or WITH query")
        self.sql, self.params = sql, params or {}
        self.reads = {}
        self.connection.set_authorizer(self._authorize)
        try:
            program = self.connection.execute("EXPLAIN " + sql, self.params).fetchall()
            # SQLite omits SQLITE_READ callbacks for some COUNT(*)/USING joins (the right
            # side's USING column). Its compiled OpenRead/Column bytecode still identifies
            # the exact base tables and columns; root pages are known because this private
            # schema has no indexes/views.
            cursors = {}
            for _, opcode, p1, p2, *_ in program:
                if opcode == "OpenRead" and p2 in self.rootpages:
                    cursors[p1] = self.rootpages[p2]
                    self.reads.setdefault(cursors[p1], set())
                elif opcode == "Column" and p1 in cursors:
                    names = list(self.schemas[cursors[p1]])
                    if 0 <= p2 < len(names):
                        self.reads[cursors[p1]].add(names[p2])
        except self.sqlite3.Error as error:
            raise EngineError(f"Read-only query failed: {error}") from None
        finally:
            self.connection.set_authorizer(None)
        # An empty column name is SQLite's rowid/table-only read (e.g. COUNT(*)).
        return {name: sorted(f for f in fields if f) for name, fields in self.reads.items()}

    def load(self, item):
        if item.name not in self.schemas:
            raise EngineError(f"Undeclared table: {item.name}")
        if item.name in self.inputs:
            raise EngineError(f"Table already loaded: {item.name}")
        columns(item.rows, list(self.schemas[item.name]))
        schema = self.schemas[item.name]
        names = list(schema)
        def record(row):
            if self.time.monotonic() > self.deadline:
                raise EngineError("Query/provider deadline exceeded; narrow the query or use --budget deep")
            values = []
            for name in names:
                value = row.get(name)
                if isinstance(value, bool) and TYPE_ALIASES.get(str(schema[name]).upper()) == "str":
                    value = "true" if value else "false"  # SQLite would store 1/0 in a text column.
                elif isinstance(value, (dict, list, tuple)):
                    value = json.dumps(value, ensure_ascii=True, default=_text, separators=(",", ":"))
                elif isinstance(value, int) and not -(2**63) <= value < 2**63:
                    value = str(value)
                values.append(value)
            return values
        try:
            self.connection.executemany(f'INSERT INTO "{item.name}" VALUES (' + ','.join('?' for _ in names) + ')',
                                        (record(row) for row in item.rows))
            self.connection.commit()
        except self.sqlite3.Error as error:
            raise EngineError(f"Input table {item.name}: {error}") from None
        except MemoryError:
            raise EngineError(f"Input table {item.name} exceeded the {SQLITE_HEAP >> 20} MiB SQLite memory cap") from None
        self.inputs[item.name] = item

    def evaluate(self, limit=1000):
        if not isinstance(limit, int) or limit <= 0:
            raise EngineError("Row limit must be positive")
        if self.time.monotonic() > self.deadline:
            raise EngineError("Query/provider deadline exceeded; narrow the query or use --budget deep")
        self.connection.set_authorizer(self._authorize)
        try:
            cursor = self.connection.execute(self.sql, self.params)
            if cursor.description is None:
                raise EngineError("Supply one read-only SELECT or WITH query")
            names = [column[0] for column in cursor.description]
            if len(set(names)) != len(names):
                raise EngineError("Alias duplicate output column names")
            fetched = cursor.fetchmany(limit + 1)
        except self.sqlite3.OperationalError as error:
            if str(error) != "interrupted":
                raise EngineError(f"Read-only query failed: {error}") from None
            if self.time.monotonic() <= self.deadline:
                raise KeyboardInterrupt from None  # Ctrl-C inside the progress handler, not the deadline.
            raise EngineError("Read-only query failed: interrupted at the query deadline; aggregate, narrow "
                              "or raise --seconds") from None
        except self.sqlite3.Error as error:
            raise EngineError(f"Read-only query failed: {error}") from None
        except MemoryError:
            raise EngineError(f"Query exceeded the {SQLITE_HEAP >> 20} MiB SQLite memory cap; aggregate or narrow it") from None
        finally:
            self.connection.set_authorizer(None)
        rows = []
        for record in fetched[:limit]:
            row = {}
            for name, value in zip(names, record):
                value = _jsonable(value)
                if name in REFERENCES and isinstance(value, str):
                    try:
                        decoded = json.loads(value)
                        if isinstance(decoded, (dict, list)):
                            value = decoded
                    except ValueError:
                        pass
                row[name] = value
            rows.append(row)
        return {"results": rows, "query_complete": len(fetched) <= limit,
                "scope": {"engine": "sqlite", "query": self.sql,
                          "inputs": [{"view": name, "rows": len(item.rows), "grain": item.grain,
                                      "upstream": item.upstream} for name, item in self.inputs.items()]}}

    def close(self):
        self.connection.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
