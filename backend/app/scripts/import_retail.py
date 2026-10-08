"""Explicit, repeatable UCI import. No private customer identifier is stored."""

import argparse
import csv
import hashlib
import hmac
import io
import tempfile
import urllib.request
import zipfile
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from openpyxl import load_workbook

from app.core.db import engine

SOURCE_URL = "https://archive.ics.uci.edu/static/public/352/online+retail.zip"
MAX_DOWNLOAD_BYTES = 40_000_000


def download_archive(destination: Path) -> None:
    request = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "retail-analytics-forecasting/1.0"})
    with urllib.request.urlopen(request, timeout=90) as source, destination.open("wb") as output:
        copied = 0
        while chunk := source.read(1024 * 1024):
            copied += len(chunk)
            if copied > MAX_DOWNLOAD_BYTES:
                raise ValueError("Dataset download exceeded the expected size")
            output.write(chunk)


def archive_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def convert_archive(archive: Path, destination: Path, min_rows: int = 500_000) -> tuple[int, int]:
    kept = dropped = 0
    with zipfile.ZipFile(archive) as zipped:
        names = [name for name in zipped.namelist() if name.lower().endswith(".xlsx")]
        if len(names) != 1 or zipped.getinfo(names[0]).file_size > 100_000_000:
            raise ValueError("Unexpected UCI archive contents")
        with zipped.open(names[0]) as source:
            workbook = load_workbook(io.BytesIO(source.read()), read_only=True, data_only=True)
        sheet = workbook.active
        with destination.open("w", newline="", encoding="utf-8") as output:
            writer = csv.writer(output)
            rows = sheet.values
            headers = next(rows)
            if tuple(headers) != ("InvoiceNo", "StockCode", "Description", "Quantity", "InvoiceDate", "UnitPrice", "CustomerID", "Country"):
                raise ValueError("UCI dataset columns changed")
            for invoice, code, description, quantity, when, price, _customer, country in rows:
                try:
                    if not isinstance(when, datetime):
                        raise ValueError("Missing invoice date")
                    invoice, code = str(invoice or "").strip(), str(code or "").strip()
                    if not invoice or not code or not country or quantity is None or price is None:
                        raise ValueError("Missing required value")
                    quantity = int(quantity)
                    price = Decimal(str(price)).quantize(Decimal("0.01"))
                    if abs(quantity) > 1_000_000 or not (0 <= price <= 1_000_000):
                        raise ValueError("Out-of-range value")
                    sale = not invoice.upper().startswith("C") and quantity > 0 and price > 0
                    writer.writerow((invoice[:20], code[:30], str(description or "Unknown product")[:300],
                                     quantity, price, when.isoformat(sep=" "), str(country)[:100], sale))
                    kept += 1
                except (ValueError, InvalidOperation, TypeError):
                    dropped += 1
        workbook.close()
    if kept < min_rows:
        raise ValueError("Dataset is unexpectedly small; database was not changed")
    return kept, dropped


def import_csv(
    path: Path,
    *,
    source_name: str,
    source_sha256: str,
    archive_bytes: int,
    imported_lines: int,
    dropped_lines: int,
) -> None:
    connection = engine.raw_connection()
    try:
        with connection.cursor() as cursor, path.open("r", encoding="utf-8") as source:
            cursor.execute("TRUNCATE retail_forecasts, retail_lines RESTART IDENTITY")
            cursor.copy_expert("COPY retail_lines (invoice_no, stock_code, description, quantity, unit_price, invoice_date, country, is_sale) FROM STDIN WITH (FORMAT csv)", source)
            cursor.execute(
                """
                INSERT INTO retail_imports
                (source, source_sha256, archive_bytes, imported_lines, dropped_lines)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (source_name, source_sha256, archive_bytes, imported_lines, dropped_lines),
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, help="Use an already downloaded UCI ZIP archive")
    parser.add_argument(
        "--expected-sha256",
        help="Abort before import unless the archive has this SHA-256 digest",
    )
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as temporary:
        archive = args.archive or Path(temporary) / "online-retail.zip"
        if not args.archive:
            download_archive(archive)
        digest = archive_sha256(archive)
        if args.expected_sha256 and not hmac.compare_digest(digest, args.expected_sha256.lower()):
            raise ValueError("Archive SHA-256 does not match --expected-sha256; database was not changed")
        csv_path = Path(temporary) / "retail.csv"
        kept, dropped = convert_archive(archive, csv_path)
        import_csv(
            csv_path,
            source_name=SOURCE_URL if not args.archive else "user-supplied UCI archive",
            source_sha256=digest,
            archive_bytes=archive.stat().st_size,
            imported_lines=kept,
            dropped_lines=dropped,
        )
    print(f"Imported {kept} UCI lines; skipped {dropped}; source SHA-256 {digest}")


if __name__ == "__main__":
    main()
