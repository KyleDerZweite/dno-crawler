"""Regression contracts for the audited framework, auth and document dependencies."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock

import fitz
import jwt
import pytest
from cryptography.fernet import InvalidToken
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from httpx import AsyncClient
from sqlalchemy import text

from app.core import auth
from app.core.config import settings
from app.core.parsers import decode_hlzf_season
from app.db.database import async_session_maker
from app.db.models import DNOModel, HLZFModel
from app.db.seeder import load_seed_data
from app.services.ai import encryption
from app.services.extraction.html_extractor import extract_hlzf_from_html
from app.services.extraction.pdf_extractor import extract_netzentgelte_from_pdf


@pytest.mark.asyncio
@pytest.mark.parametrize("storage", ["json", "text", "legacy_text"])
async def test_hlzf_reads_through_search_and_detail(client: AsyncClient, storage: str) -> None:
    expected = [{"start": "17:00:00", "end": "19:00:00"}]
    async with async_session_maker() as db:
        if storage != "json":
            for season in ("winter", "fruehling", "sommer", "herbst"):
                await db.execute(text(f"ALTER TABLE hlzf ALTER COLUMN {season} TYPE TEXT"))
        dno = DNOModel(name="Contract Testnetz", slug="contract-testnetz")
        db.add(dno)
        await db.flush()
        db.add(HLZFModel(dno_id=dno.id, year=2025, voltage_level="NS", winter=expected))
        await db.commit()
        dno_id = dno.id
        if storage == "legacy_text":
            await db.execute(text("UPDATE hlzf SET winter = '17:00-19:00'"))
            await db.commit()
    search = await client.post(
        "/api/v1/search/", json={"dno": {"dno_name": "Contract Testnetz"}, "years": [2025]}
    )
    assert search.status_code == 200
    assert search.json()["hlzf"][0]["winter"] == expected
    detail = await client.get(f"/api/v1/dnos/{dno_id}/data")
    assert detail.status_code == 200
    assert detail.json()["data"]["hlzf"][0]["winter"] == expected
    assert detail.json()["data"]["hlzf"][0]["sommer"] is None


def test_malformed_hlzf_storage_is_rejected() -> None:
    with pytest.raises(ValueError):
        decode_hlzf_season("unreadable season")
    with pytest.raises(ValueError):
        decode_hlzf_season("[broken json")


def test_provider_secret_encryption_and_tampering(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_ENCRYPTION_KEY", "synthetic-contract-key")
    encryption._get_fernet.cache_clear()
    try:
        encrypted = encryption.encrypt_secret("synthetic-provider-value")
        assert encryption.decrypt_secret(encrypted) == "synthetic-provider-value"
        with pytest.raises(InvalidToken):
            encryption.decrypt_secret(encrypted[:30] + "!" + encrypted[31:])
    finally:
        encryption._get_fernet.cache_clear()


def test_existing_parquet_capture_remains_readable() -> None:
    """Exercise the shipped capture through the updated Arrow reader and normalizer."""
    records = load_seed_data()
    assert records
    assert all(isinstance(record["name"], str) and record["name"] for record in records)


def test_pdf_tariff_extraction_and_invalid_document(tmp_path: Path) -> None:
    """Exercise actual PDF bytes through pdfplumber/pdfminer, including rejection."""
    path = tmp_path / "tariff.pdf"
    with fitz.open() as document:
        page = document.new_page()
        page.insert_text((72, 72), "Netzentgelte\nNiederspannung 26,88 8,58 230,39 0,44")
        document.save(path)
    records = extract_netzentgelte_from_pdf(path)
    assert len(records) == 1
    assert records[0]["leistung_unter_2500h"] == 26.88
    assert records[0]["arbeit"] == 0.44
    assert records[0]["source_page"] == 1
    path.write_bytes(b"invalid PDF")
    with pytest.raises(Exception, match="No /Root object"):
        extract_netzentgelte_from_pdf(path)


def test_html_hlzf_preserves_multiline_windows() -> None:
    records = extract_hlzf_from_html(
        "<h3>gültig ab 01.01.2026</h3><table><tbody><tr>"
        "<td>Niederspannung</td><td>08:00-10:00<br>16:00-18:00</td>"
        "<td></td><td>17:00-19:00</td><td>-</td></tr></tbody></table>",
        2026,
    )
    assert records == [
        {
            "voltage_level": "Niederspannung",
            "fruehling": "08:00-10:00\n16:00-18:00",
            "sommer": None,
            "herbst": "17:00-19:00",
            "winter": "-",
        }
    ]
    assert extract_hlzf_from_html("<p>No tariff table</p>", 2026) == []


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [None, "expired", "audience", "issuer", "signature"])
async def test_signed_oidc_claims_and_rejection(
    monkeypatch: pytest.MonkeyPatch, failure: str | None
) -> None:
    """Use actual RSA/JWKS verification without contacting a live identity provider."""
    monkeypatch.setattr(settings, "zitadel_domain", "identity.invalid")
    monkeypatch.setattr(settings, "zitadel_client_id", "test-client")
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
    public_jwk["kid"] = "test-key"
    monkeypatch.setattr(auth, "fetch_jwks", AsyncMock(return_value={"keys": [public_jwk]}))
    claims = {
        "sub": "contract-user",
        "iss": auth.auth_settings.issuer,
        "aud": "test-client",
        "exp": datetime.now(UTC) + timedelta(minutes=5),
        "email": "contract@example.invalid",
        "name": "Contract User",
        "urn:zitadel:iam:org:project:roles": {"MEMBER": {}},
    }
    if failure == "expired":
        claims["exp"] = datetime.now(UTC) - timedelta(minutes=5)
    elif failure == "audience":
        claims["aud"] = "another-client"
    elif failure == "issuer":
        claims["iss"] = "https://another.invalid"
    elif failure == "signature":
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = jwt.encode(claims, key, algorithm="RS256", headers={"kid": "test-key"})
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    if failure:
        with pytest.raises(HTTPException) as rejected:
            await auth.get_current_user(credentials)
        assert rejected.value.status_code == 401
    else:
        user = await auth.get_current_user(credentials)
        assert user.id == "contract-user"
        assert user.roles == ["MEMBER"]
