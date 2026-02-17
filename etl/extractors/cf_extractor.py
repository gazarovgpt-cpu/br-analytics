"""Extract Cash Flow data from 1C Excel exports."""

import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


def extract_cf_entries(filepath: Path) -> pd.DataFrame:
    """
    Extract detailed CF entries from 1C export.

    Expected file: 2024_08_БР CF.xlsx, sheet "2023_офиц"
    Columns: ВИД | Тип | МЕСЯЦ | Дата | Документ | Содержание операции |
             Дт | Кт | Сумма_УУ | КОНТРАГЕНТ | Подразделение_УУ |
             Счет_УУ | НОВАЯ СТАТЬЯ | ...
    """
    logger.info(f"Reading CF entries from {filepath}")

    df = pd.read_excel(filepath, sheet_name="2023_офиц", engine="openpyxl", header=1)
    logger.info(f"Read {len(df)} rows")

    rename_map = {
        "ВИД": "entry_type",
        "Тип": "direction",
        "МЕСЯЦ": "month_num",
        "Дата": "entry_date",
        "Документ": "document",
        "Содержание операции": "description",
        "Дт": "debit_account",
        "Кт": "credit_account",
        "Сумма_УУ": "amount",
        "КОНТРАГЕНТ (для расхода)": "counterparty",
        "Подразделение_УУ": "branch_uu",
        "Счет_УУ": "account_uu",
        "НОВАЯ СТАТЬЯ": "expense_category",
    }

    available = {k: v for k, v in rename_map.items() if k in df.columns}
    df = df.rename(columns=available)

    if "entry_date" in df.columns:
        df["entry_date"] = pd.to_datetime(df["entry_date"], errors="coerce", dayfirst=True)

    if "amount" in df.columns:
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce")

    df = df.dropna(subset=["amount"])
    df["source_file"] = filepath.name

    logger.info(f"Extracted {len(df)} CF entries")
    return df


def extract_cf_monthly_svod(filepath: Path, sheet_name: str = "CF_СВОД") -> pd.DataFrame:
    """
    Extract monthly consolidated CF from CF_СВОД file.

    Expected: CF_СВОД_+_КЛИНИК_АЙ_КЬЮ_янв_ноя2025_в02.xlsx
    Complex multi-header structure with ЮЛ (БР, БР-1, ИП, БРЦ) columns per month.
    """
    logger.info(f"Reading CF monthly SVOD from {filepath}, sheet={sheet_name}")

    df_raw = pd.read_excel(filepath, sheet_name=sheet_name, engine="openpyxl", header=None)
    logger.info(f"Read raw sheet: {df_raw.shape}")

    # This file has a complex multi-row header structure.
    # Row 0: year-month labels (2025-1, 2025-2, ...)
    # Row 1: ЮЛ (БР, БР-1, ИП, БРЦ)
    # Row 5: Column headers (Статья, then per ЮЛ per month)
    # Row 6+: Data

    # We parse the line items from the Статья column and pivot
    records = []

    year_months_row = df_raw.iloc[0]
    le_row = df_raw.iloc[1]
    header_row = df_raw.iloc[5]

    stat_col = None
    for idx, val in header_row.items():
        if val == "Статья":
            stat_col = idx
            break

    if stat_col is None:
        logger.error("Could not find 'Статья' column in CF_СВОД")
        return pd.DataFrame()

    # Build column mapping: col_index -> (year_month, legal_entity)
    col_map = {}
    for col_idx in range(stat_col + 1, len(header_row)):
        ym = year_months_row.iloc[col_idx]
        le = le_row.iloc[col_idx]
        if pd.notna(ym) and pd.notna(le):
            col_map[col_idx] = (str(ym), str(le))

    for row_idx in range(6, len(df_raw)):
        line_item = df_raw.iloc[row_idx, stat_col]
        if pd.isna(line_item) or not str(line_item).strip():
            continue
        line_item = str(line_item).strip()

        for col_idx, (ym, le) in col_map.items():
            val = df_raw.iloc[row_idx, col_idx]
            if pd.notna(val):
                try:
                    amount = float(val)
                except (ValueError, TypeError):
                    continue
                if amount == 0:
                    continue
                records.append({
                    "year_month_str": ym,
                    "legal_entity": le,
                    "line_item": line_item,
                    "amount": amount,
                    "source_file": filepath.name,
                })

    df = pd.DataFrame(records)
    if not df.empty:
        logger.info(f"Extracted {len(df)} CF monthly records")
    else:
        logger.warning("No CF monthly records extracted")

    return df


def extract_cf_clinics(filepath: Path) -> pd.DataFrame:
    """
    Extract CF data broken down by clinics.

    Expected: 2025_01_БР CF (2).xlsx, sheet "CF сlinics"
    Structure: columns per clinic (ТАГАНКА, БАУМАНКА, ДИНАМО, РУБЛЕВКА, ЗИЛАРТ)
    """
    logger.info(f"Reading CF by clinics from {filepath}")

    df_raw = pd.read_excel(
        filepath, sheet_name="CF сlinics", engine="openpyxl", header=None
    )
    logger.info(f"Read raw sheet: {df_raw.shape}")

    # Row 1 has clinic names, Row 3 has line items (Статья column)
    clinic_row = df_raw.iloc[1]
    clinics = {}
    for idx, val in clinic_row.items():
        if pd.notna(val) and str(val).strip():
            name = str(val).strip()
            if name in ("ТАГАНКА", "БАУМАНКА", "ДИНАМО", "РУБЛЕВКА", "ЗИЛАРТ"):
                clinics[idx] = name

    records = []
    for row_idx in range(3, len(df_raw)):
        line_item = df_raw.iloc[row_idx, 1]
        if pd.isna(line_item) or not str(line_item).strip():
            continue
        line_item = str(line_item).strip()

        for col_idx, clinic_name in clinics.items():
            val = df_raw.iloc[row_idx, col_idx]
            if pd.notna(val):
                try:
                    amount = float(val)
                except (ValueError, TypeError):
                    continue
                if amount == 0:
                    continue
                records.append({
                    "branch": clinic_name,
                    "line_item": line_item,
                    "amount": amount,
                    "source_file": filepath.name,
                })

    df = pd.DataFrame(records)
    logger.info(f"Extracted {len(df)} CF clinic records")
    return df
