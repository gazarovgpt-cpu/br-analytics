"""ClinicIQ API data extractors.

Each function calls the API client, flattens nested JSON structures,
and returns a pandas DataFrame ready for loading into DWH.
"""

import logging
from typing import Optional

import pandas as pd

from etl.extractors.api_client import (
    ClinicIQClient,
    get_last_sync,
    update_last_sync,
)

logger = logging.getLogger(__name__)

# Shared client singleton (created on first use)
_client: Optional[ClinicIQClient] = None


def _get_client() -> ClinicIQClient:
    global _client
    if _client is None:
        _client = ClinicIQClient()
    return _client


# ── Branches ───────────────────────────────────────────────────


def extract_branches() -> pd.DataFrame:
    """Fetch branch directory from API."""
    client = _get_client()
    logger.info("Extracting branches from API...")

    records = client.fetch_all("/branches")
    if not records:
        logger.warning("No branches returned from API")
        return pd.DataFrame()

    rows = []
    for r in records:
        rows.append({
            "branch_id_api": r.get("branch_id"),
            "name": r.get("name"),
            "code": r.get("code"),
            "address": r.get("address"),
            "phone": r.get("phone"),
            "chairs_count": r.get("chairs_count"),
            "doctors_count": r.get("doctors_count"),
            "is_active": r.get("is_active"),
            "opened_date": r.get("opened_date"),
            "working_hours": str(r.get("working_hours", {})),
            "updated_at": r.get("updated_at"),
        })

    df = pd.DataFrame(rows)
    logger.info("Extracted %d branches", len(df))
    update_last_sync("branches")
    return df


# ── Doctors ────────────────────────────────────────────────────


def extract_doctors(incremental: bool = True) -> pd.DataFrame:
    """Fetch doctor directory from API."""
    client = _get_client()
    logger.info("Extracting doctors from API...")

    params = {}
    if incremental:
        last_sync = get_last_sync("doctors")
        if last_sync:
            params["modified_since"] = last_sync
            logger.info("Incremental sync since %s", last_sync)

    records = client.fetch_all("/doctors", params)
    if not records:
        logger.warning("No doctors returned from API")
        return pd.DataFrame()

    rows = []
    for r in records:
        primary_branch = r.get("primary_branch") or {}
        branches = r.get("branches", [])
        rows.append({
            "doctor_id_api": r.get("doctor_id"),
            "full_name": r.get("full_name"),
            "short_name": r.get("short_name"),
            "specialization": r.get("specialization"),
            "additional_specializations": ", ".join(
                r.get("additional_specializations", [])
            ),
            "primary_branch_id": primary_branch.get("id"),
            "primary_branch_name": primary_branch.get("name"),
            "branch_ids": ", ".join(str(b.get("id", "")) for b in branches),
            "is_active": r.get("is_active"),
            "hire_date": r.get("hire_date"),
            "updated_at": r.get("updated_at"),
        })

    df = pd.DataFrame(rows)
    logger.info("Extracted %d doctors", len(df))
    update_last_sync("doctors")
    return df


# ── Services ───────────────────────────────────────────────────


def extract_services(incremental: bool = True) -> pd.DataFrame:
    """Fetch service catalog from API."""
    client = _get_client()
    logger.info("Extracting services from API...")

    params = {}
    if incremental:
        last_sync = get_last_sync("services")
        if last_sync:
            params["modified_since"] = last_sync
            logger.info("Incremental sync since %s", last_sync)

    records = client.fetch_all("/services", params)
    if not records:
        logger.warning("No services returned from API")
        return pd.DataFrame()

    rows = []
    for r in records:
        rows.append({
            "service_id_api": r.get("service_id"),
            "code": r.get("code"),
            "name": r.get("name"),
            "category": r.get("category"),
            "subcategory": r.get("subcategory"),
            "base_price": r.get("base_price"),
            "duration_minutes": r.get("duration_minutes"),
            "is_active": r.get("is_active"),
            "updated_at": r.get("updated_at"),
        })

    df = pd.DataFrame(rows)
    logger.info("Extracted %d services", len(df))
    update_last_sync("services")
    return df


# ── Transactions ───────────────────────────────────────────────


def _flatten_transaction(r: dict) -> dict:
    """Flatten a single transaction record from nested JSON."""
    branch = r.get("branch") or {}
    patient = r.get("patient") or {}
    payment = r.get("payment_type") or {}
    invoice = r.get("invoice") or {}
    doctor = r.get("doctor") or {}
    visit = r.get("visit") or {}

    services = r.get("services", [])
    first_service = services[0] if services else {}

    return {
        "transaction_id_api": r.get("transaction_id"),
        "transaction_date": r.get("transaction_date"),
        "transaction_datetime": r.get("transaction_datetime"),
        "branch_id_api": branch.get("id"),
        "branch_name": branch.get("name"),
        "branch_code": branch.get("code"),
        "patient_id": patient.get("id"),
        "patient_age": patient.get("age"),
        "patient_age_group": patient.get("age_group"),
        "is_child": patient.get("age_group") == "child",
        "payment_type_code": payment.get("code"),
        "payment_type_name": payment.get("name"),
        "operation_type": r.get("operation_type"),
        "invoice_id": invoice.get("id"),
        "invoice_total_amount": invoice.get("total_amount"),
        "invoice_debt": invoice.get("debt"),
        "invoice_status": invoice.get("status"),
        "invoice_discount_amount": invoice.get("discount_amount"),
        "invoice_discount_percent": invoice.get("discount_percent"),
        "service_id_api": first_service.get("service_id"),
        "service_code": first_service.get("code"),
        "service_name": first_service.get("name"),
        "service_category": first_service.get("category"),
        "service_quantity": first_service.get("quantity"),
        "service_price": first_service.get("price"),
        "service_discount": first_service.get("discount"),
        "service_total": first_service.get("total"),
        "services_count": len(services),
        "doctor_id_api": doctor.get("id"),
        "doctor_name": doctor.get("name"),
        "doctor_specialization": doctor.get("specialization"),
        "visit_date": visit.get("date"),
        "visit_type": visit.get("type"),
        "visit_reason": visit.get("reason"),
        "is_primary_visit": visit.get("type") == "primary",
        "amount": r.get("amount"),
        "created_at": r.get("created_at"),
        "updated_at": r.get("updated_at"),
    }


def extract_transactions(
    date_from: str,
    date_to: str,
    branch_id: Optional[int] = None,
    incremental: bool = False,
) -> pd.DataFrame:
    """Fetch transactions from API.

    Args:
        date_from: Start date (YYYY-MM-DD)
        date_to: End date (YYYY-MM-DD)
        branch_id: Optional branch filter
        incremental: If True, use modified_since from last sync

    Returns:
        Flattened DataFrame of transactions
    """
    client = _get_client()
    logger.info("Extracting transactions %s to %s...", date_from, date_to)

    params: dict = {"date_from": date_from, "date_to": date_to}
    if branch_id:
        params["branch_id"] = branch_id
    if incremental:
        last_sync = get_last_sync("transactions")
        if last_sync:
            params["modified_since"] = last_sync
            logger.info("Incremental sync since %s", last_sync)

    records = client.fetch_all("/transactions", params)
    if not records:
        logger.warning("No transactions returned from API")
        return pd.DataFrame()

    rows = [_flatten_transaction(r) for r in records]
    df = pd.DataFrame(rows)
    logger.info("Extracted %d transactions", len(df))
    update_last_sync("transactions")
    return df


# ── Appointments ───────────────────────────────────────────────


def extract_appointments(
    date_from: str,
    date_to: str,
    branch_id: Optional[int] = None,
    incremental: bool = False,
) -> pd.DataFrame:
    """Fetch appointments/visits from API."""
    client = _get_client()
    logger.info("Extracting appointments %s to %s...", date_from, date_to)

    params: dict = {"date_from": date_from, "date_to": date_to}
    if branch_id:
        params["branch_id"] = branch_id
    if incremental:
        last_sync = get_last_sync("appointments")
        if last_sync:
            params["modified_since"] = last_sync
            logger.info("Incremental sync since %s", last_sync)

    records = client.fetch_all("/appointments", params)
    if not records:
        logger.warning("No appointments returned from API")
        return pd.DataFrame()

    rows = []
    for r in records:
        branch = r.get("branch") or {}
        doctor = r.get("doctor") or {}
        patient = r.get("patient") or {}
        rows.append({
            "appointment_id_api": r.get("appointment_id"),
            "date": r.get("date"),
            "time_start": r.get("time_start"),
            "time_end": r.get("time_end"),
            "duration_minutes": r.get("duration_minutes"),
            "branch_id_api": branch.get("id"),
            "branch_name": branch.get("name"),
            "doctor_id_api": doctor.get("id"),
            "doctor_name": doctor.get("name"),
            "doctor_specialization": doctor.get("specialization"),
            "patient_id": patient.get("id"),
            "patient_age": patient.get("age"),
            "patient_age_group": patient.get("age_group"),
            "visit_type": r.get("visit_type"),
            "reason": r.get("reason"),
            "status": r.get("status"),
            "source": r.get("source"),
            "created_at": r.get("created_at"),
            "updated_at": r.get("updated_at"),
        })

    df = pd.DataFrame(rows)
    logger.info("Extracted %d appointments", len(df))
    update_last_sync("appointments")
    return df


# ── Invoices ───────────────────────────────────────────────────


def extract_invoices(
    date_from: str,
    date_to: str,
    branch_id: Optional[int] = None,
    incremental: bool = False,
) -> pd.DataFrame:
    """Fetch invoices from API."""
    client = _get_client()
    logger.info("Extracting invoices %s to %s...", date_from, date_to)

    params: dict = {"date_from": date_from, "date_to": date_to}
    if branch_id:
        params["branch_id"] = branch_id
    if incremental:
        last_sync = get_last_sync("invoices")
        if last_sync:
            params["modified_since"] = last_sync
            logger.info("Incremental sync since %s", last_sync)

    records = client.fetch_all("/invoices", params)
    if not records:
        logger.warning("No invoices returned from API")
        return pd.DataFrame()

    rows = []
    for r in records:
        branch = r.get("branch") or {}
        patient = r.get("patient") or {}
        doctor = r.get("doctor") or {}
        items = r.get("items", [])
        payments = r.get("payments", [])

        rows.append({
            "invoice_id_api": r.get("invoice_id"),
            "created_date": r.get("created_date"),
            "branch_id_api": branch.get("id"),
            "branch_name": branch.get("name"),
            "patient_id": patient.get("id"),
            "patient_age_group": patient.get("age_group"),
            "doctor_id_api": doctor.get("id"),
            "doctor_name": doctor.get("name"),
            "items_count": len(items),
            "subtotal": r.get("subtotal"),
            "discount_total": r.get("discount_total"),
            "total_amount": r.get("total_amount"),
            "paid_amount": r.get("paid_amount"),
            "debt": r.get("debt"),
            "status": r.get("status"),
            "payments_count": len(payments),
            "created_at": r.get("created_at"),
            "updated_at": r.get("updated_at"),
        })

    df = pd.DataFrame(rows)
    logger.info("Extracted %d invoices", len(df))
    update_last_sync("invoices")
    return df


# ── Patient Stats ──────────────────────────────────────────────


def extract_patient_stats(
    date_from: str,
    date_to: str,
    group_by: str = "month,branch",
) -> pd.DataFrame:
    """Fetch aggregated patient statistics from API."""
    client = _get_client()
    logger.info("Extracting patient stats %s to %s...", date_from, date_to)

    params: dict = {
        "date_from": date_from,
        "date_to": date_to,
        "group_by": group_by,
    }

    data = client.get("/patients/stats", params)
    records = data.get("data", [])
    if not records:
        logger.warning("No patient stats returned from API")
        return pd.DataFrame()

    rows = []
    for r in records:
        branch = r.get("branch") or {}
        age_dist = r.get("age_distribution") or {}
        rows.append({
            "period": r.get("period"),
            "branch_id_api": branch.get("id"),
            "branch_name": branch.get("name"),
            "total_patients": r.get("total_patients"),
            "new_patients": r.get("new_patients"),
            "returning_patients": r.get("returning_patients"),
            "retention_rate": r.get("retention_rate"),
            "avg_age": r.get("avg_age"),
            "age_0_17": age_dist.get("0_17"),
            "age_18_30": age_dist.get("18_30"),
            "age_31_45": age_dist.get("31_45"),
            "age_46_60": age_dist.get("46_60"),
            "age_60_plus": age_dist.get("60_plus"),
            "avg_visits_per_patient": r.get("avg_visits_per_patient"),
            "avg_revenue_per_patient": r.get("avg_revenue_per_patient"),
            "avg_ltv": r.get("avg_ltv"),
        })

    df = pd.DataFrame(rows)
    logger.info("Extracted %d patient stats rows", len(df))
    update_last_sync("patient_stats")
    return df
