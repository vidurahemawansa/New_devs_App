from decimal import Decimal, ROUND_HALF_UP
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Dict, Any, Optional
from app.services.cache import get_revenue_summary, get_monthly_revenue_summary
from app.core.auth import authenticate_request as get_current_user

router = APIRouter()

CENTS = Decimal("0.01")


def _quantize_to_cents(value: str) -> str:
    """
    Rounds a currency amount to 2 decimal places using Decimal arithmetic.

    Reservation amounts are stored with sub-cent precision (NUMERIC(10,3)), and
    the previous code returned `float(revenue_data['total'])` straight to the
    client. Round-tripping money through a binary float is exactly the kind of
    thing that produces the "off by a few cents, but only sometimes" reports
    finance was seeing - some decimal totals aren't exactly representable in
    IEEE-754 floats. Quantizing with Decimal first, and only converting to
    float for JSON transport *after* rounding to cents, keeps the value the
    client sees deterministic and correct.
    """
    return str(Decimal(value).quantize(CENTS, rounding=ROUND_HALF_UP))


@router.get("/dashboard/summary")
async def get_dashboard_summary(
    property_id: str,
    month: Optional[int] = Query(None, ge=1, le=12),
    year: Optional[int] = Query(None, ge=1900),
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:

    tenant_id = getattr(current_user, "tenant_id", "default_tenant") or "default_tenant"

    if month is not None and year is not None:
        revenue_data = await get_monthly_revenue_summary(property_id, tenant_id, month, year)
    else:
        revenue_data = await get_revenue_summary(property_id, tenant_id)

    total_revenue_str = _quantize_to_cents(revenue_data['total'])

    return {
        "property_id": revenue_data['property_id'],
        "total_revenue": total_revenue_str,
        "currency": revenue_data['currency'],
        "reservations_count": revenue_data['count'],
        "month": revenue_data.get('month'),
        "year": revenue_data.get('year'),
    }
