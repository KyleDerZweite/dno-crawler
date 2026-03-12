"""
DNO Crawler API Client

Standalone Python client for the DNO Crawler API.
Maps non-admin endpoints to callable methods using httpx.
"""

from __future__ import annotations

from pathlib import Path

import httpx

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass

import os


class DNOCrawlerClient:
    """Synchronous client for the DNO Crawler API.

    Works both unauthenticated (public search, health) and authenticated
    (DNO management, jobs, verification). Supports Zitadel JWTs and
    API keys (``dno_...``) as bearer tokens.

    Usage::

        with DNOCrawlerClient() as client:
            result = client.search_by_address("Musterstr. 1", "10115", "Berlin")
            print(result)
    """

    def __init__(
        self,
        base_url: str | None = None,
        token: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = (base_url or os.getenv("DNO_BASE_URL", "https://dno.kylehub.dev")).rstrip(
            "/"
        )
        self.token = token or os.getenv("DNO_TOKEN") or None

        headers: dict[str, str] = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        self._client = httpx.Client(base_url=self.base_url, headers=headers, timeout=timeout)

    def __enter__(self) -> DNOCrawlerClient:
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    # -- internal helpers --

    def _get(self, path: str, **kwargs) -> dict:
        resp = self._client.get(path, **kwargs)
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, **kwargs) -> dict:
        resp = self._client.post(path, **kwargs)
        resp.raise_for_status()
        return resp.json()

    def _delete(self, path: str, **kwargs) -> dict:
        resp = self._client.delete(path, **kwargs)
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------ #
    #  Health                                                              #
    # ------------------------------------------------------------------ #

    def health(self) -> dict:
        """GET /api/health"""
        return self._get("/api/health")

    def ready(self) -> dict:
        """GET /api/ready"""
        return self._get("/api/ready")

    # ------------------------------------------------------------------ #
    #  Search (public, no auth required)                                   #
    # ------------------------------------------------------------------ #

    def search_by_address(
        self,
        street: str,
        zip_code: str,
        city: str,
        *,
        year: int | None = None,
        years: list[int] | None = None,
    ) -> dict:
        """Search for a DNO by postal address."""
        body: dict = {"address": {"street": street, "zip_code": zip_code, "city": city}}
        if year is not None:
            body["year"] = year
        if years is not None:
            body["years"] = years
        return self._post("/api/v1/search/", json=body)

    def search_by_coordinates(
        self,
        latitude: float,
        longitude: float,
        *,
        year: int | None = None,
        years: list[int] | None = None,
    ) -> dict:
        """Search for a DNO by GPS coordinates."""
        body: dict = {"coordinates": {"latitude": latitude, "longitude": longitude}}
        if year is not None:
            body["year"] = year
        if years is not None:
            body["years"] = years
        return self._post("/api/v1/search/", json=body)

    def search_by_dno(
        self,
        *,
        dno_name: str | None = None,
        dno_id: int | None = None,
        mastr_nr: str | None = None,
        year: int | None = None,
        years: list[int] | None = None,
    ) -> dict:
        """Search by DNO identifier (name, ID, or MaStR number)."""
        dno: dict = {}
        if dno_name is not None:
            dno["dno_name"] = dno_name
        if dno_id is not None:
            dno["dno_id"] = dno_id
        if mastr_nr is not None:
            dno["mastr_nr"] = mastr_nr
        body: dict = {"dno": dno}
        if year is not None:
            body["year"] = year
        if years is not None:
            body["years"] = years
        return self._post("/api/v1/search/", json=body)

    # ------------------------------------------------------------------ #
    #  Files (public download)                                             #
    # ------------------------------------------------------------------ #

    def download_file(self, filepath: str) -> bytes:
        """GET /api/v1/files/downloads/{filepath} -- returns raw bytes."""
        resp = self._client.get(f"/api/v1/files/downloads/{filepath}")
        resp.raise_for_status()
        return resp.content

    # ------------------------------------------------------------------ #
    #  Auth                                                                #
    # ------------------------------------------------------------------ #

    def me(self) -> dict:
        """GET /api/v1/auth/me"""
        return self._get("/api/v1/auth/me")

    # ------------------------------------------------------------------ #
    #  DNOs                                                                #
    # ------------------------------------------------------------------ #

    def list_dnos(
        self,
        *,
        page: int = 1,
        per_page: int = 50,
        q: str | None = None,
        status: str | None = None,
        sort_by: str | None = None,
        include_stats: bool = False,
    ) -> dict:
        """GET /api/v1/dnos/"""
        params: dict = {"page": page, "per_page": per_page, "include_stats": include_stats}
        if q is not None:
            params["q"] = q
        if status is not None:
            params["status"] = status
        if sort_by is not None:
            params["sort_by"] = sort_by
        return self._get("/api/v1/dnos/", params=params)

    def get_dno(self, dno_id: str | int) -> dict:
        """GET /api/v1/dnos/{dno_id} -- accepts numeric ID or slug."""
        return self._get(f"/api/v1/dnos/{dno_id}")

    def create_dno(self, name: str, **kwargs) -> dict:
        """POST /api/v1/dnos/"""
        body = {"name": name, **kwargs}
        return self._post("/api/v1/dnos/", json=body)

    def get_dno_stats(self) -> dict:
        """GET /api/v1/dnos/stats"""
        return self._get("/api/v1/dnos/stats")

    def get_dno_data(self, dno_id: int) -> dict:
        """GET /api/v1/dnos/{dno_id}/data"""
        return self._get(f"/api/v1/dnos/{dno_id}/data")

    def search_vnb(self, query: str) -> dict:
        """GET /api/v1/dnos/search-vnb?q=..."""
        return self._get("/api/v1/dnos/search-vnb", params={"q": query})

    def get_vnb_details(self, vnb_id: str) -> dict:
        """GET /api/v1/dnos/search-vnb/{vnb_id}/details"""
        return self._get(f"/api/v1/dnos/search-vnb/{vnb_id}/details")

    # ------------------------------------------------------------------ #
    #  Crawl / Jobs                                                        #
    # ------------------------------------------------------------------ #

    def trigger_crawl(
        self,
        dno_id: str | int,
        year: int,
        *,
        priority: int = 5,
        job_type: str = "full",
    ) -> dict:
        """POST /api/v1/dnos/{dno_id}/crawl"""
        body = {"year": year, "priority": priority, "job_type": job_type}
        return self._post(f"/api/v1/dnos/{dno_id}/crawl", json=body)

    def get_dno_jobs(self, dno_id: int, *, limit: int = 10) -> dict:
        """GET /api/v1/dnos/{dno_id}/jobs"""
        return self._get(f"/api/v1/dnos/{dno_id}/jobs", params={"limit": limit})

    def list_jobs(
        self,
        *,
        status: str | None = None,
        limit: int = 50,
        page: int = 1,
    ) -> dict:
        """GET /api/v1/jobs/"""
        params: dict = {"limit": limit, "page": page}
        if status is not None:
            params["status"] = status
        return self._get("/api/v1/jobs/", params=params)

    def get_job(self, job_id: int) -> dict:
        """GET /api/v1/jobs/{job_id}"""
        return self._get(f"/api/v1/jobs/{job_id}")

    # ------------------------------------------------------------------ #
    #  DNO Files                                                           #
    # ------------------------------------------------------------------ #

    def list_dno_files(self, dno_id: int) -> dict:
        """GET /api/v1/dnos/{dno_id}/files"""
        return self._get(f"/api/v1/dnos/{dno_id}/files")

    def upload_file(self, dno_id: int, filepath: str | Path) -> dict:
        """POST /api/v1/dnos/{dno_id}/upload"""
        path = Path(filepath)
        with path.open("rb") as f:
            return self._post(
                f"/api/v1/dnos/{dno_id}/upload",
                files={"file": (path.name, f)},
            )

    # ------------------------------------------------------------------ #
    #  Import / Export                                                      #
    # ------------------------------------------------------------------ #

    def export_data(
        self,
        dno_id: int,
        *,
        data_types: list[str] | None = None,
        years: list[int] | None = None,
    ) -> dict:
        """GET /api/v1/dnos/{dno_id}/export"""
        params: dict = {}
        if data_types is not None:
            params["data_types"] = data_types
        if years is not None:
            params["years"] = years
        return self._get(f"/api/v1/dnos/{dno_id}/export", params=params)

    def import_data(
        self,
        dno_id: int,
        *,
        mode: str = "merge",
        netzentgelte: list[dict] | None = None,
        hlzf: list[dict] | None = None,
    ) -> dict:
        """POST /api/v1/dnos/{dno_id}/import"""
        body: dict = {"mode": mode}
        if netzentgelte is not None:
            body["netzentgelte"] = netzentgelte
        if hlzf is not None:
            body["hlzf"] = hlzf
        return self._post(f"/api/v1/dnos/{dno_id}/import", json=body)

    # ------------------------------------------------------------------ #
    #  Verification                                                        #
    # ------------------------------------------------------------------ #

    def verify_netzentgelte(self, record_id: int, *, notes: str | None = None) -> dict:
        """POST /api/v1/verification/netzentgelte/{record_id}/verify"""
        body: dict = {}
        if notes is not None:
            body["notes"] = notes
        return self._post(f"/api/v1/verification/netzentgelte/{record_id}/verify", json=body)

    def flag_netzentgelte(self, record_id: int, reason: str) -> dict:
        """POST /api/v1/verification/netzentgelte/{record_id}/flag"""
        return self._post(
            f"/api/v1/verification/netzentgelte/{record_id}/flag", json={"reason": reason}
        )

    def unflag_netzentgelte(self, record_id: int) -> dict:
        """DELETE /api/v1/verification/netzentgelte/{record_id}/flag"""
        return self._delete(f"/api/v1/verification/netzentgelte/{record_id}/flag")

    def verify_hlzf(self, record_id: int, *, notes: str | None = None) -> dict:
        """POST /api/v1/verification/hlzf/{record_id}/verify"""
        body: dict = {}
        if notes is not None:
            body["notes"] = notes
        return self._post(f"/api/v1/verification/hlzf/{record_id}/verify", json=body)

    def flag_hlzf(self, record_id: int, reason: str) -> dict:
        """POST /api/v1/verification/hlzf/{record_id}/flag"""
        return self._post(
            f"/api/v1/verification/hlzf/{record_id}/flag", json={"reason": reason}
        )

    def unflag_hlzf(self, record_id: int) -> dict:
        """DELETE /api/v1/verification/hlzf/{record_id}/flag"""
        return self._delete(f"/api/v1/verification/hlzf/{record_id}/flag")
