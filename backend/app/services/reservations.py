from datetime import datetime, timezone as dt_timezone
from decimal import Decimal
from typing import Dict, Any, List, Optional
from zoneinfo import ZoneInfo


async def _get_property_timezone(session, property_id: str, tenant_id: str) -> str:
    """Looks up the IANA timezone configured for a property (defaults to UTC)."""
    from sqlalchemy import text

    result = await session.execute(
        text("SELECT timezone FROM properties WHERE id = :property_id AND tenant_id = :tenant_id"),
        {"property_id": property_id, "tenant_id": tenant_id},
    )
    row = result.fetchone()
    return row.timezone if row and row.timezone else "UTC"


async def calculate_monthly_revenue(property_id: str, tenant_id: str, month: int, year: int) -> Dict[str, Any]:
    """
    Calculates revenue for a specific calendar month for a property.

    Bookings are bucketed into months using the PROPERTY'S LOCAL TIMEZONE, not
    naive UTC. `check_in_date` is stored as `TIMESTAMP WITH TIME ZONE`, so a
    check-in of "2024-02-29 23:30:00+00" for a Paris property (UTC+1) actually
    falls on "2024-03-01 00:30" local time - i.e. it belongs to March, not
    February. Comparing against naive UTC month boundaries (the previous
    behaviour) silently drops that reservation from March's total, which is
    exactly the kind of "March revenue doesn't match our records" discrepancy
    clients would notice.
    """
    from app.core.database_pool import db_pool
    from sqlalchemy import text

    if not db_pool.session_factory:
        await db_pool.initialize()

    async with db_pool.get_session() as session:
        tz_name = await _get_property_timezone(session, property_id, tenant_id)
        local_tz = ZoneInfo(tz_name)

        local_start = datetime(year, month, 1, tzinfo=local_tz)
        if month < 12:
            local_end = datetime(year, month + 1, 1, tzinfo=local_tz)
        else:
            local_end = datetime(year + 1, 1, 1, tzinfo=local_tz)

        # Convert local month boundaries to UTC for comparison against the
        # timezone-aware check_in_date column.
        start_utc = local_start.astimezone(dt_timezone.utc)
        end_utc = local_end.astimezone(dt_timezone.utc)

        query = text("""
            SELECT SUM(total_amount) as total, COUNT(*) as count
            FROM reservations
            WHERE property_id = :property_id
              AND tenant_id = :tenant_id
              AND check_in_date >= :start_date
              AND check_in_date < :end_date
        """)

        result = await session.execute(query, {
            "property_id": property_id,
            "tenant_id": tenant_id,
            "start_date": start_utc,
            "end_date": end_utc,
        })
        row = result.fetchone()

        total = Decimal(str(row.total)) if row and row.total is not None else Decimal("0")
        count = row.count if row and row.count is not None else 0

        return {
            "property_id": property_id,
            "tenant_id": tenant_id,
            "month": month,
            "year": year,
            "timezone": tz_name,
            "total": str(total),
            "currency": "USD",
            "count": count,
        }


async def calculate_total_revenue(property_id: str, tenant_id: str) -> Dict[str, Any]:
    """
    Aggregates all-time revenue for a property from the database.
    """
    try:
        from app.core.database_pool import db_pool

        if not db_pool.session_factory:
            await db_pool.initialize()

        if db_pool.session_factory:
            async with db_pool.get_session() as session:
                from sqlalchemy import text

                query = text("""
                    SELECT 
                        property_id,
                        SUM(total_amount) as total_revenue,
                        COUNT(*) as reservation_count
                    FROM reservations 
                    WHERE property_id = :property_id AND tenant_id = :tenant_id
                    GROUP BY property_id
                """)

                result = await session.execute(query, {
                    "property_id": property_id, 
                    "tenant_id": tenant_id
                })
                row = result.fetchone()
                
                if row:
                    total_revenue = Decimal(str(row.total_revenue))
                    return {
                        "property_id": property_id,
                        "tenant_id": tenant_id,
                        "total": str(total_revenue),
                        "currency": "USD", 
                        "count": row.reservation_count
                    }
                else:
                    # No reservations found for this property
                    return {
                        "property_id": property_id,
                        "tenant_id": tenant_id,
                        "total": "0.00",
                        "currency": "USD",
                        "count": 0
                    }
        else:
            raise Exception("Database pool not available")
            
    except Exception as e:
        print(f"Database error for {property_id} (tenant: {tenant_id}): {e}")
        
        # Fallback mock data used only when the database is genuinely unreachable.
        mock_data = {
            'prop-001': {'total': '1000.00', 'count': 3},
            'prop-002': {'total': '4975.50', 'count': 4}, 
            'prop-003': {'total': '6100.50', 'count': 2},
            'prop-004': {'total': '1776.50', 'count': 4},
            'prop-005': {'total': '3256.00', 'count': 3}
        }
        
        mock_property_data = mock_data.get(property_id, {'total': '0.00', 'count': 0})
        
        return {
            "property_id": property_id,
            "tenant_id": tenant_id, 
            "total": mock_property_data['total'],
            "currency": "USD",
            "count": mock_property_data['count']
        }
