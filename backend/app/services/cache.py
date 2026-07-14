import json
import redis.asyncio as redis
from typing import Dict, Any
import os

# Initialize Redis client (typically configured centrally).
redis_client = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))

async def get_revenue_summary(property_id: str, tenant_id: str) -> Dict[str, Any]:
    """
    Fetches revenue summary, utilizing caching to improve performance.
    """
    # NOTE: the cache key MUST include tenant_id. Property IDs are only unique
    # *within* a tenant (see database/schema.sql - properties has a composite
    # PRIMARY KEY (id, tenant_id)), so two different clients can have a property
    # with the same id (e.g. both tenant-a and tenant-b have a "prop-001").
    # Keying the cache by property_id alone meant whichever tenant requested a
    # given property id first would populate the cache, and every other tenant
    # with a colliding property id would be served that tenant's cached revenue
    # data on refresh - a serious cross-tenant data leak.
    cache_key = f"revenue:{tenant_id}:{property_id}"
    
    # Try to get from cache
    cached = await redis_client.get(cache_key)
    if cached:
        return json.loads(cached)
    
    # Revenue calculation is delegated to the reservation service.
    from app.services.reservations import calculate_total_revenue
    
    # Calculate revenue
    result = await calculate_total_revenue(property_id, tenant_id)
    
    # Cache the result for 5 minutes
    await redis_client.setex(cache_key, 300, json.dumps(result))
    
    return result


async def get_monthly_revenue_summary(property_id: str, tenant_id: str, month: int, year: int) -> Dict[str, Any]:
    """
    Fetches a specific month's revenue summary, utilizing caching to improve performance.
    """
    cache_key = f"revenue:{tenant_id}:{property_id}:{year}-{month:02d}"

    cached = await redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    from app.services.reservations import calculate_monthly_revenue

    result = await calculate_monthly_revenue(property_id, tenant_id, month, year)

    await redis_client.setex(cache_key, 300, json.dumps(result))

    return result
