"""Extract MIS transactions from Детализация_транзакций_+_услуги Excel file."""

import hashlib
import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

EXPECTED_COLUMNS = [
    "Дата транзакции",
    "Клиника",
    "Пациент",
    "Возраст пациента",
    "Взрослый/Ребенок",
    "Тип оплаты",
    "Тип операции",
    "Клиника, где создан счет на оплату",
    "Сумма счета",
    "Долг в рамках текущего счета",
    "Статус счета",
    "Позиции счета",
    "Даты визитов",
    "Причины обращения",
    "Врач",
    "Статус визитов",
    "Сумма транзакции",
]


def hash_patient(name: str) -> str:
    """Create anonymized patient hash from full name."""
    if not name or pd.isna(name):
        return None
    return hashlib.sha256(name.strip().encode("utf-8")).hexdigest()[:16]


def extract_transactions(filepath: Path) -> pd.DataFrame:
    """
    Read MIS transaction file and return cleaned DataFrame.

    Expected file: Детализация_транзакций_+_услуги_2025_01_05.xlsx
    Sheet: "result", ~51K rows
    """
    logger.info(f"Reading transactions from {filepath}")

    df = pd.read_excel(filepath, sheet_name="result", engine="openpyxl")
    logger.info(f"Read {len(df)} rows, columns: {list(df.columns)}")

    missing = [c for c in EXPECTED_COLUMNS if c not in df.columns]
    if missing:
        logger.warning(f"Missing expected columns: {missing}")

    rename_map = {
        "Дата транзакции": "transaction_date",
        "Клиника": "clinic",
        "Пациент": "patient_name",
        "Возраст пациента": "patient_age",
        "Взрослый/Ребенок": "age_group",
        "Тип оплаты": "payment_type",
        "Тип операции": "operation_type",
        "Клиника, где создан счет на оплату": "invoice_clinic",
        "Сумма счета": "invoice_amount",
        "Долг в рамках текущего счета": "invoice_debt",
        "Статус счета": "invoice_status",
        "Позиции счета": "service_items",
        "Даты визитов": "visit_dates",
        "Причины обращения": "visit_reasons",
        "Врач": "doctor_name",
        "Статус визитов": "visit_status",
        "Сумма транзакции": "transaction_amount",
    }

    df = df.rename(columns=rename_map)

    df["transaction_date"] = pd.to_datetime(df["transaction_date"], errors="coerce")
    df["transaction_amount"] = pd.to_numeric(df["transaction_amount"], errors="coerce")
    df["invoice_amount"] = pd.to_numeric(df["invoice_amount"], errors="coerce")
    df["invoice_debt"] = pd.to_numeric(df["invoice_debt"], errors="coerce")
    df["patient_age"] = pd.to_numeric(df["patient_age"], errors="coerce").astype(
        "Int64"
    )

    df["patient_hash"] = df["patient_name"].apply(hash_patient)

    invalid = df["transaction_date"].isna() | df["transaction_amount"].isna()
    if invalid.sum() > 0:
        logger.warning(f"Dropping {invalid.sum()} rows with null date/amount")
        df = df[~invalid]

    logger.info(
        f"Extracted {len(df)} transactions, "
        f"date range: {df['transaction_date'].min()} - {df['transaction_date'].max()}"
    )
    return df
