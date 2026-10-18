"""Turning source payloads into all-string Arrow tables.

Raw keeps text exactly as published; dbt does the typing.
"""

import csv
import io
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.csv as pacsv


def unique_names(names: Sequence[str]) -> list[str]:
    """Suffix repeated column names (_2, _3, ...) so they survive Parquet."""
    seen: dict[str, int] = {}
    out = []
    for name in names:
        seen[name] = seen.get(name, 0) + 1
        out.append(name if seen[name] == 1 else f"{name}_{seen[name]}")
    return out


def _header(first_line: bytes, encoding: str) -> list[str]:
    text = first_line.decode("utf-8-sig" if encoding.lower() in ("utf-8", "utf8") else encoding)
    return unique_names(next(csv.reader([text])))


def _options(names: list[str], encoding: str, block_size: int | None = None):
    read = pacsv.ReadOptions(column_names=names, skip_rows=1, encoding=encoding)
    if block_size:
        read.block_size = block_size
    parse = pacsv.ParseOptions(newlines_in_values=True)
    convert = pacsv.ConvertOptions(
        column_types={n: pa.string() for n in names}, strings_can_be_null=True
    )
    return read, parse, convert


def csv_bytes_to_table(body: bytes, encoding: str = "utf-8") -> pa.Table:
    """Parse one CSV payload (header + rows). An empty payload yields an empty table."""
    if not body.strip():
        return pa.table({})
    names = _header(body.split(b"\n", 1)[0].rstrip(b"\r"), encoding)
    read, parse, convert = _options(names, encoding)
    return pacsv.read_csv(
        io.BytesIO(body), read_options=read, parse_options=parse, convert_options=convert
    )


def iter_csv_file(
    path: Path, encoding: str = "utf-8", extra: dict[str, str] | None = None
) -> Iterator[pa.RecordBatch]:
    """Stream a CSV file as all-string batches, optionally appending constant columns."""
    with path.open("rb") as fh:
        names = _header(fh.readline().rstrip(b"\r\n"), encoding)
    read, parse, convert = _options(names, encoding, block_size=16 << 20)
    reader = pacsv.open_csv(path, read_options=read, parse_options=parse, convert_options=convert)
    for batch in reader:
        if extra:
            arrays = [*batch.columns]
            arrays += [pa.array([v] * batch.num_rows, pa.string()) for v in extra.values()]
            batch = pa.RecordBatch.from_arrays(arrays, names=[*batch.schema.names, *extra])
        yield batch


def records_to_table(records: list[dict[str, Any]], columns: Sequence[str]) -> pa.Table:
    """JSON records to an all-string table with a fixed column order."""
    return pa.table(
        {
            c: pa.array([None if r.get(c) is None else str(r[c]) for r in records], pa.string())
            for c in columns
        }
    )
