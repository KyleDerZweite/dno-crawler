"""
Source Data Models for DNO Crawler.

These models store raw data from external sources in a hub-and-spoke pattern:
- DNOMastrData: Data from Marktstammdatenregister (MaStR)
- DNOVnbData: Data from VNB Digital API
- DNOBdewData: Data from BDEW Codes API

Each DNO can have 0 or 1 record from each source (One-to-One or One-to-Zero).
BDEW is One-to-Many since a company can have multiple BDEW codes for different
market functions (Netzbetreiber, Lieferant, Messstellenbetreiber, etc.).

The core DNOModel remains the "Golden Record" with computed/resolved fields
that choose the best value from available sources.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.database import Base
from app.db.models import TimestampMixin

if TYPE_CHECKING:
    from app.db.models import DNOModel


# ==============================================================================
# MaStR (Marktstammdatenregister) Data
# ==============================================================================


class DNOMastrData(Base, TimestampMixin):
    """
    Source data from Marktstammdatenregister (MaStR).

    MaStR is the German register of energy market participants.
    Contains official registration info, market roles, and activity status.

    Relationship: One-to-One with DNO.
    """

    __tablename__ = "dno_mastr_data"
    __table_args__ = (
        Index("idx_mastr_nr", "mastr_nr"),
        Index("idx_mastr_acer", "acer_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dno_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("dnos.id", ondelete="CASCADE"),
        unique=True,  # Enforces One-to-One
        nullable=False,
        index=True,
    )

    # MaStR Identification
    mastr_nr: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False
    )  # e.g., SNB982046657236
    acer_code: Mapped[str | None] = mapped_column(String(50))  # e.g., A00014369.DE

    # Company name as registered in MaStR
    registered_name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Address (structured)
    address_components: Mapped[dict | None] = mapped_column(JSON)
    # Structure: {street, house_number, zip_code, city, country}

    contact_address: Mapped[str | None] = mapped_column(String(500))  # Formatted display string
    region: Mapped[str | None] = mapped_column(String(255))  # Bundesland

    # Market roles (e.g., ["Anschlussnetzbetreiber", "Messstellenbetreiber"])
    marktrollen: Mapped[list | None] = mapped_column(JSON)

    # Activity status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)  # Tätigkeitsstatus
    closed_network: Mapped[bool] = mapped_column(
        Boolean, default=False
    )  # Geschlossenes Verteilernetz
    activity_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    activity_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # MaStR metadata
    registration_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    mastr_last_updated: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Sync tracking
    last_synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationship
    dno: Mapped["DNOModel"] = relationship(back_populates="mastr_data")


# ==============================================================================
# VNB Digital Data
# ==============================================================================


class DNOVnbData(Base, TimestampMixin):
    """
    Source data from VNB Digital API.

    VNB Digital is a public API providing grid operator information,
    including contact details, voltage types, and service areas.

    Relationship: One-to-One with DNO.
    """

    __tablename__ = "dno_vnb_data"
    __table_args__ = (Index("idx_vnb_id", "vnb_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dno_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("dnos.id", ondelete="CASCADE"),
        unique=True,  # Enforces One-to-One
        nullable=False,
        index=True,
    )

    # VNB Digital Identification
    vnb_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    # Names
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    official_name: Mapped[str | None] = mapped_column(String(255))  # Full legal name

    # Contact information
    homepage_url: Mapped[str | None] = mapped_column(String(500))
    phone: Mapped[str | None] = mapped_column(String(100))
    email: Mapped[str | None] = mapped_column(String(255))
    address: Mapped[str | None] = mapped_column(String(500))

    # VNB characteristics
    types: Mapped[list | None] = mapped_column(JSON)  # ["STROM", "GAS"]
    voltage_types: Mapped[list | None] = mapped_column(JSON)  # ["Niederspannung", "Mittelspannung"]
    logo_url: Mapped[str | None] = mapped_column(String(500))

    # Sync tracking
    last_synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationship
    dno: Mapped["DNOModel"] = relationship(back_populates="vnb_data")

    @property
    def is_electricity(self) -> bool:
        """Check if this VNB handles electricity."""
        return self.types is not None and "STROM" in self.types


# ==============================================================================
# BDEW Codes Data
# ==============================================================================


class DNOBdewData(Base, TimestampMixin):
    """
    Source data from BDEW Codes API.

    BDEW (Bundesverband der Energie- und Wasserwirtschaft) codes are
    13-digit identifiers for energy market participants.

    A company can have MULTIPLE BDEW codes for different market functions:
    - Netzbetreiber (Grid Operator)
    - Lieferant (Supplier)
    - Messstellenbetreiber (Metering Point Operator)
    - Bilanzkreisverantwortlicher (Balance Responsible Party)
    - etc.

    Relationship: One-to-Many with DNO.
    """

    __tablename__ = "dno_bdew_data"
    __table_args__ = (
        Index("idx_bdew_code", "bdew_code"),
        Index("idx_bdew_market_function", "market_function"),
        # Unique constraint: one DNO can only have one code per market function
        Index("idx_bdew_dno_function", "dno_id", "market_function", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dno_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("dnos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # BDEW Identification (all three IDs from the BDEW system)
    bdew_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)  # 13-digit code
    bdew_internal_id: Mapped[int] = mapped_column(Integer)  # API lookup ID ("Id")
    bdew_company_uid: Mapped[int] = mapped_column(Integer)  # Company UID ("CompanyUId")

    # Company name as registered in BDEW
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Market function this code is for
    market_function: Mapped[str | None] = mapped_column(String(100))
    # Values: Netzbetreiber, Lieferant, Messstellenbetreiber,
    #         Bilanzkreisverantwortlicher, Übertragungsnetzbetreiber, etc.

    # Contact (BDEW-specific)
    contact_name: Mapped[str | None] = mapped_column(String(255))
    contact_phone: Mapped[str | None] = mapped_column(String(100))
    contact_email: Mapped[str | None] = mapped_column(String(255))

    # Address (from BDEW, may differ from MaStR)
    street: Mapped[str | None] = mapped_column(String(255))
    zip_code: Mapped[str | None] = mapped_column(String(20))
    city: Mapped[str | None] = mapped_column(String(100))
    website: Mapped[str | None] = mapped_column(String(500))

    # Sync tracking
    last_synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationship
    dno: Mapped["DNOModel"] = relationship(back_populates="bdew_data")

    @property
    def is_grid_operator(self) -> bool:
        """Check if this is a grid operator (VNB/ÜNB) code."""
        return self.market_function in (
            "Netzbetreiber",
            "Verteilnetzbetreiber",
            "Übertragungsnetzbetreiber",
        )
