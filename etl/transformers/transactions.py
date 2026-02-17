"""Transform MIS transactions: map branches, doctors, services, anonymize patients."""

import logging

import pandas as pd

from etl.config import MIS_BRANCH_MAP, classify_service

logger = logging.getLogger(__name__)


def resolve_branch_id(clinic_name: str, branch_lookup: dict) -> int | None:
    """Map clinic name from MIS to branch_id using dim_branch."""
    if pd.isna(clinic_name):
        return None
    name = str(clinic_name).strip()
    code = MIS_BRANCH_MAP.get(name)
    if code and code in branch_lookup:
        return branch_lookup[code]
    return None


def resolve_payment_type_id(payment_type: str, pt_lookup: dict) -> int | None:
    """Map payment type string to payment_type_id."""
    if pd.isna(payment_type):
        return None
    name = str(payment_type).strip()
    return pt_lookup.get(name)


def transform_transactions(
    df: pd.DataFrame,
    branch_lookup: dict,
    payment_type_lookup: dict,
    doctor_names: set,
) -> pd.DataFrame:
    """
    Transform raw transactions DataFrame into DWH-ready format.

    Args:
        df: Raw extracted transactions
        branch_lookup: code -> branch_id mapping
        payment_type_lookup: name -> payment_type_id mapping
        doctor_names: set of known doctor names (to collect new ones)

    Returns:
        Transformed DataFrame ready for dwh.fact_transactions
    """
    logger.info(f"Transforming {len(df)} transactions")

    result = pd.DataFrame()

    result["transaction_date"] = df["transaction_date"]
    result["branch_id"] = df["clinic"].apply(
        lambda x: resolve_branch_id(x, branch_lookup)
    )
    result["patient_hash"] = df["patient_hash"]
    result["patient_age"] = df["patient_age"]
    result["is_child"] = df["age_group"].apply(
        lambda x: str(x).strip() == "Ребенок" if pd.notna(x) else None
    )
    result["payment_type_id"] = df["payment_type"].apply(
        lambda x: resolve_payment_type_id(x, payment_type_lookup)
    )
    result["operation_type"] = df["operation_type"]
    result["invoice_branch_id"] = df["invoice_clinic"].apply(
        lambda x: resolve_branch_id(x, branch_lookup)
    )
    result["invoice_amount"] = df["invoice_amount"]
    result["invoice_debt"] = df["invoice_debt"]

    result["service_name"] = df["service_items"].apply(
        lambda x: str(x).strip()[:200] if pd.notna(x) else None
    )
    result["service_category"] = result["service_name"].apply(classify_service)

    result["visit_date"] = pd.to_datetime(
        df["visit_dates"].apply(lambda x: str(x).split(",")[0].strip() if pd.notna(x) else None),
        errors="coerce",
    )
    result["doctor_name"] = df["doctor_name"].apply(
        lambda x: str(x).strip() if pd.notna(x) else None
    )

    new_doctors = set(result["doctor_name"].dropna()) - doctor_names
    if new_doctors:
        logger.info(f"Found {len(new_doctors)} new doctors")

    result["is_primary_visit"] = df["visit_status"].apply(
        lambda x: str(x).strip() == "Первичный" if pd.notna(x) else None
    )
    result["transaction_amount"] = df["transaction_amount"]

    null_branches = result["branch_id"].isna().sum()
    if null_branches > 0:
        logger.warning(f"{null_branches} transactions with unmapped branch")

    logger.info(f"Transformation complete: {len(result)} rows")
    return result
