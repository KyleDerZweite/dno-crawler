"""
BDEW Codes API Client.

Fetches BDEW (Bundesverband der Energie- und Wasserwirtschaft) codes
from the bdew-codes.de public API.

The API has two endpoints:
1. GetCompanyList - paginated list of companies with Id, CompanyUId, Company name
2. GetBdewCodeListOfCompany?companyId=XXX - detailed info including BDEW code

POST /Codenumbers/BDEWCodes/GetCompanyList?jtStartIndex=0&jtPageSize=500
POST /Codenumbers/BDEWCodes/GetBdewCodeListOfCompany?companyId=XXX&filter=
"""

import asyncio
from dataclasses import dataclass

import httpx
import structlog

logger = structlog.get_logger()


@dataclass
class BDEWCompany:
    """A company entry from the list endpoint."""
    id: int                     # Internal ID for detail lookup ("Id" in API)
    company_uid: int            # Company UID ("CompanyUId" in API)
    name: str                   # Company name ("Company" in API, cleaned)


@dataclass
class BDEWRecord:
    """
    A detailed BDEW code record with all identifiers.
    
    Contains three IDs from the BDEW system:
    - bdew_internal_id: The "Id" used for API lookups
    - bdew_company_uid: The "CompanyUId" - another internal identifier
    - bdew_code: The actual 13-digit BDEW code (e.g., "9900001000002")
    """
    bdew_internal_id: int       # Internal ID for API lookups ("Id")
    bdew_company_uid: int       # Company UID ("CompanyUId")
    bdew_code: str              # 13-digit code (e.g., "9900001000002")
    company_name: str           # Company name
    street: str | None = None
    zip_code: str | None = None
    city: str | None = None
    website: str | None = None
    market_function: str | None = None
    contact_name: str | None = None
    contact_phone: str | None = None
    contact_email: str | None = None


class BDEWClient:
    """
    Client for BDEW Codes API.
    
    Fetches all BDEW codes and provides lookup by company name.
    """

    BASE_URL = "https://bdew-codes.de/Codenumbers/BDEWCodes"
    LIST_ENDPOINT = "/GetCompanyList"
    DETAIL_ENDPOINT = "/GetBdewCodeListOfCompany"
    PAGE_SIZE = 500

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "de-DE,de;q=0.6",
        "Origin": "https://bdew-codes.de",
        "Referer": "https://bdew-codes.de/Codenumbers/BDEWCodes/CodeOverview",
        "X-Requested-With": "XMLHttpRequest",
    }

    def __init__(self, request_delay: float = 0.2):
        self.request_delay = request_delay
        self.log = logger.bind(component="BDEWClient")
        self._companies: list[BDEWCompany] = []
        self._records: list[BDEWRecord] = []
        self._name_index: dict[str, BDEWRecord] = {}

    async def fetch_company_list(self) -> list[BDEWCompany]:
        """
        Fetch all companies from the list endpoint.
        
        Returns:
            List of BDEWCompany entries.
        """
        if self._companies:
            return self._companies

        self.log.info("Fetching BDEW company list...")
        companies = []
        start_index = 0

        async with httpx.AsyncClient(timeout=30.0) as client:
            while True:
                url = f"{self.BASE_URL}{self.LIST_ENDPOINT}?jtStartIndex={start_index}&jtPageSize={self.PAGE_SIZE}"

                try:
                    response = await client.post(url, headers=self.HEADERS)
                    response.raise_for_status()
                    data = response.json()

                    if data.get("Result") != "OK":
                        self.log.error("API returned error", result=data.get("Result"))
                        break

                    page_records = data.get("Records", [])
                    total_count = data.get("TotalRecordCount", 0)

                    for record in page_records:
                        name = record.get("Company", "").strip()
                        # Clean up name (remove leading tabs/spaces)
                        name = name.lstrip('\t ')

                        companies.append(BDEWCompany(
                            id=record.get("Id", 0),
                            company_uid=record.get("CompanyUId", 0),
                            name=name,
                        ))

                    self.log.info(
                        "Fetched BDEW company page",
                        start=start_index,
                        count=len(page_records),
                        total=total_count
                    )

                    start_index += self.PAGE_SIZE
                    if start_index >= total_count:
                        break

                    await asyncio.sleep(self.request_delay)

                except httpx.HTTPError as e:
                    self.log.error("HTTP error fetching company list", error=str(e))
                    break

        self._companies = companies
        self.log.info("Fetched all companies", total=len(companies))
        return companies

    async def fetch_company_details(self, company: BDEWCompany) -> BDEWRecord | None:
        """
        Fetch detailed BDEW info for a single company.
        
        Args:
            company: BDEWCompany from the list endpoint.
        
        Returns:
            BDEWRecord with full details, or None if not found.
        """
        url = f"{self.BASE_URL}{self.DETAIL_ENDPOINT}?companyId={company.id}&filter="

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(url, headers=self.HEADERS)
                response.raise_for_status()

                # The response might be HTML or JSON
                content_type = response.headers.get("content-type", "")
                if "json" not in content_type:
                    self.log.debug("Non-JSON response for company", company_id=company.id)
                    return None

                data = response.json()

                # Response is {Result: "OK", Records: [...]}
                if data.get("Result") != "OK":
                    self.log.debug("API error for company", company_id=company.id, result=data.get("Result"))
                    return None

                records = data.get("Records", [])
                if not records:
                    return None

                # Each record is a different market function (Netzbetreiber, Lieferant, etc.)
                # Prefer "Netzbetreiber" (VNB) or "Verteilnetzbetreiber" role
                preferred_roles = ["Netzbetreiber", "Verteilnetzbetreiber", "Übertragungsnetzbetreiber"]
                item = None

                for role in preferred_roles:
                    for r in records:
                        if r.get("MarketFunctionName") == role:
                            item = r
                            break
                    if item:
                        break

                # If no preferred role found, use first record
                if not item:
                    item = records[0]

                return BDEWRecord(
                    bdew_internal_id=company.id,
                    bdew_company_uid=company.company_uid,
                    bdew_code=str(item.get("BdewCode", "")),
                    company_name=company.name,
                    market_function=item.get("MarketFunctionName"),
                    contact_name=item.get("ContactName"),
                    # Note: Street/City/etc not available in this endpoint
                )

        except httpx.HTTPError as e:
            self.log.debug("HTTP error fetching company details", company_id=company.id, error=str(e))
            return None
        except Exception as e:
            self.log.debug("Error parsing company details", company_id=company.id, error=str(e))
            return None

    async def fetch_all_with_details(self, limit: int | None = None) -> list[BDEWRecord]:
        """
        Fetch all companies and their BDEW codes.
        
        This makes N+1 requests (1 for list, N for details).
        Use with caution - can be slow for 4000+ companies.
        
        Args:
            limit: Optional limit for testing.
        
        Returns:
            List of BDEWRecord with full details.
        """
        if self._records:
            return self._records

        # First fetch the company list
        companies = await self.fetch_company_list()

        if limit:
            companies = companies[:limit]

        self.log.info("Fetching details for companies", count=len(companies))

        records = []
        async with httpx.AsyncClient(timeout=15.0) as client:
            for i, company in enumerate(companies):
                url = f"{self.BASE_URL}{self.DETAIL_ENDPOINT}?companyId={company.id}&filter="

                try:
                    response = await client.post(url, headers=self.HEADERS)

                    if response.status_code == 200:
                        content_type = response.headers.get("content-type", "")
                        if "json" in content_type:
                            data = response.json()

                            # Response is {Result: "OK", Records: [...]}
                            if data.get("Result") != "OK":
                                continue

                            api_records = data.get("Records", [])
                            if not api_records:
                                continue

                            # Prefer Netzbetreiber role
                            preferred_roles = ["Netzbetreiber", "Verteilnetzbetreiber", "Übertragungsnetzbetreiber"]
                            item = None

                            for role in preferred_roles:
                                for r in api_records:
                                    if r.get("MarketFunctionName") == role:
                                        item = r
                                        break
                                if item:
                                    break

                            if not item:
                                item = api_records[0]

                            bdew_code = str(item.get("BdewCode", ""))
                            if bdew_code:
                                record = BDEWRecord(
                                    bdew_internal_id=company.id,
                                    bdew_company_uid=company.company_uid,
                                    bdew_code=bdew_code,
                                    company_name=company.name,
                                    market_function=item.get("MarketFunctionName"),
                                    contact_name=item.get("ContactName"),
                                )
                                records.append(record)

                    if (i + 1) % 100 == 0:
                        self.log.info("Progress", processed=i + 1, found=len(records))

                    await asyncio.sleep(self.request_delay)

                except Exception as e:
                    self.log.debug("Error fetching details", company=company.name, error=str(e))

        self._records = records
        self._build_name_index()

        self.log.info("Fetched all BDEW details", total=len(records))
        return records

    def _build_name_index(self) -> None:
        """Build index for fast lookup by normalized name."""
        for record in self._records:
            normalized = self._normalize_name(record.company_name)
            self._name_index[normalized] = record

    @staticmethod
    def _normalize_name(name: str) -> str:
        """Normalize company name for matching."""
        name = name.lower().strip()
        # Common abbreviations and variations
        replacements = {
            "gmbh & co. kg": "gmbh co kg",
            "gmbh & co kg": "gmbh co kg",
            "gmbh&co.kg": "gmbh co kg",
            " & ": " ",
            ".": "",
            ",": "",
            "-": " ",
            "  ": " ",
        }
        for old, new in replacements.items():
            name = name.replace(old, new)
        return name.strip()

    def find_by_name(self, company_name: str) -> BDEWRecord | None:
        """
        Find BDEW record by company name.
        
        Uses exact normalized match first, then fuzzy containment.
        
        Args:
            company_name: Company name to search for.
        
        Returns:
            BDEWRecord if found, None otherwise.
        """
        if not self._records:
            return None

        normalized = self._normalize_name(company_name)

        # Exact match
        if normalized in self._name_index:
            return self._name_index[normalized]

        # Fuzzy: check if search term is contained in any name
        for norm_name, record in self._name_index.items():
            if normalized in norm_name or norm_name in normalized:
                return record

        # Try matching on key words (first 2-3 significant words)
        search_words = [w for w in normalized.split() if len(w) > 3][:3]
        if search_words:
            for norm_name, record in self._name_index.items():
                name_words = norm_name.split()
                if all(any(sw in nw or nw in sw for nw in name_words) for sw in search_words):
                    return record

        return None

    def find_by_zip_and_name(self, zip_code: str, company_name: str) -> BDEWRecord | None:
        """
        Find BDEW record by ZIP code and partial name match.
        
        Args:
            zip_code: ZIP code to filter by.
            company_name: Partial company name.
        
        Returns:
            BDEWRecord if found, None otherwise.
        """
        if not self._records:
            return None

        normalized = self._normalize_name(company_name)

        # Filter by ZIP code first
        zip_matches = [r for r in self._records if r.zip_code == zip_code]

        for record in zip_matches:
            record_normalized = self._normalize_name(record.company_name)
            if normalized in record_normalized or record_normalized in normalized:
                return record

        return None

    async def find_in_list_by_name(self, company_name: str) -> BDEWCompany | None:
        """
        Find company in the list by name (without fetching details).
        
        Useful for quick lookup before fetching details.
        """
        companies = await self.fetch_company_list()
        normalized = self._normalize_name(company_name)

        for company in companies:
            company_normalized = self._normalize_name(company.name)
            if normalized in company_normalized or company_normalized in normalized:
                return company

        # Fuzzy word match
        search_words = [w for w in normalized.split() if len(w) > 3][:3]
        if search_words:
            for company in companies:
                company_normalized = self._normalize_name(company.name)
                name_words = company_normalized.split()
                if all(any(sw in nw or nw in sw for nw in name_words) for sw in search_words):
                    return company

        return None

    async def get_bdew_code_for_name(self, company_name: str) -> str | None:
        """
        Get BDEW code for a company name (fetches details on demand).
        
        Args:
            company_name: Company name to look up.
        
        Returns:
            BDEW code string if found, None otherwise.
        """
        # First find in the company list
        company = await self.find_in_list_by_name(company_name)
        if not company:
            return None

        # Then fetch details
        details = await self.fetch_company_details(company)
        if details and details.bdew_code:
            return details.bdew_code

        return None

    async def get_bdew_record_for_name(self, company_name: str) -> BDEWRecord | None:
        """
        Get full BDEW record for a company name (fetches details on demand).
        
        Returns the complete BDEWRecord with all identifiers and metadata,
        useful for enrichment where you want to store all BDEW data.
        
        Args:
            company_name: Company name to look up.
        
        Returns:
            BDEWRecord with all details if found, None otherwise.
        """
        company = await self.find_in_list_by_name(company_name)
        if not company:
            return None

        return await self.fetch_company_details(company)


# Singleton instance
bdew_client = BDEWClient()


async def main():
    """Test fetching BDEW codes."""
    client = BDEWClient()

    # Test quick lookup
    test_names = [
        "50Hertz Transmission GmbH",
        "Westnetz GmbH",
        "Netze BW GmbH",
        "Stadtwerke München",
    ]

    print("Testing on-demand lookup:")
    for name in test_names:
        code = await client.get_bdew_code_for_name(name)
        if code:
            print(f"  {name} -> {code}")
        else:
            print(f"  {name} -> NOT FOUND")
        await asyncio.sleep(0.3)


if __name__ == "__main__":
    asyncio.run(main())

