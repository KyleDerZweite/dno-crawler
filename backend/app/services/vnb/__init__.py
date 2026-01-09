"""
VNB Digital Module for DNO Crawler.

Provides DNO (Verteilnetzbetreiber) resolution via the vnbdigital.de GraphQL API.

Components:
- VNBDigitalClient: API client for VNB lookups
- SkeletonService: DNO skeleton creation with lazy registration

Usage:
    from app.services.vnb import VNBDigitalClient, skeleton_service
    
    client = VNBDigitalClient()
    vnbs = await client.lookup_by_coordinates("50.9375,6.9603")
    
    dno, created = await skeleton_service.get_or_create_dno(db, name, vnb_id)
"""

from app.services.vnb.client import VNBDigitalClient, vnb_client
from app.services.vnb.models import (
    DNODetails,
    LocationResult,
    VNBResult,
    VNBSearchResult,
)
from app.services.vnb.skeleton import (
    NormalizedAddress,
    SkeletonService,
    generate_slug,
    normalize_address,
    skeleton_service,
    snap_coordinate,
)

__all__ = [
    # Client
    "VNBDigitalClient",
    "vnb_client",

    # Skeleton service
    "SkeletonService",
    "skeleton_service",
    "normalize_address",
    "NormalizedAddress",
    "generate_slug",
    "snap_coordinate",

    # Data models
    "VNBResult",
    "LocationResult",
    "DNODetails",
    "VNBSearchResult",
]
