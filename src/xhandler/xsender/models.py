"""Inputs of the SUNAT services, and the answers: generated from the core's
schema in models_gen.py, re-exported here."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# Bytes (raw bytes, base64 in JSON) also types the zip of File
from xhandler.xsender.models_gen import (
    CDR,
    Bytes,
    ConsultResult,
    ConsultStatus,
    Fault,
    NoCDR,
    SendFileAnswer,
    Status,
    VerifyResult,
)

__all__ = [
    "BILL_CONSULT_SERVICE_URL",
    "BILL_VALID_SERVICE_URL",
    "CDR",
    "ConsultDocument",
    "ConsultResult",
    "ConsultStatus",
    "Credentials",
    "Fault",
    "File",
    "NoCDR",
    "SendFileAnswer",
    "SendResult",
    "Status",
    "Target",
    "URLs",
    "ValidateCDP",
    "VerifyResult",
]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class URLs(_Model):
    """The SUNAT services where a company sends its documents."""

    invoice: str
    perception_retention: str
    despatch: str = ""
    """The REST API of the guias de remision; SUNAT has no beta for it."""

    @classmethod
    def beta(cls) -> URLs:
        """SUNAT beta (testing) services; without guias de remision."""
        return cls(
            invoice="https://e-beta.sunat.gob.pe/ol-ti-itcpfegem-beta/billService",
            perception_retention="https://e-beta.sunat.gob.pe/ol-ti-itemision-otroscpe-gem-beta/billService",
        )

    @classmethod
    def production(cls) -> URLs:
        """SUNAT production services."""
        return cls(
            invoice="https://e-factura.sunat.gob.pe/ol-ti-itcpfegem/billService",
            perception_retention="https://e-factura.sunat.gob.pe/ol-ti-itemision-otroscpe-gem/billService",
            despatch="https://api-cpe.sunat.gob.pe/v1/contribuyente/gem",
        )


BILL_CONSULT_SERVICE_URL = "https://e-factura.sunat.gob.pe/ol-it-wsconscpegem/billConsultService"
"""Looks up documents already sent (get_status, get_status_cdr)."""
BILL_VALID_SERVICE_URL = "https://e-factura.sunat.gob.pe/ol-it-wsconsvalidcpe/billValidService"
"""Validates documents (validate_cdp, validate_file)."""


class Credentials(_Model):
    """Credentials of the company. They never show their secrets."""

    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    username: str
    """SOL user, e.g. "20123456789MODDATOS"."""
    password: str
    client_id: str | None = None
    """API client of the REST services (guias de remision), from SUNAT's SOL menu."""
    client_secret: str | None = None
    token: str | None = Field(default=None, exclude=True)
    """A token of the guias obtained elsewhere; used as is when set."""

    def __repr_args__(self) -> Iterator[tuple[str | None, Any]]:
        """For repr and str: only the username."""
        yield "username", self.username


class Target(_Model):
    """A SUNAT service for a file or a ticket."""

    protocol: Literal["soap", "rest"]
    url: str
    action: Literal["bill", "summary", "pack"] | None = None
    """The operation of the SOAP files."""


class File(_Model):
    """A zip for SUNAT."""

    filename: str
    zip: Bytes


class ConsultDocument(_Model):
    """A document already sent to SUNAT."""

    ruc: str
    tipo_comprobante: str
    """Catalog1, e.g. "01"."""
    serie: str
    numero: int


class ValidateCDP(ConsultDocument):
    """The criteria of validaCDPcriterios."""

    tipo_documento_identidad_receptor: str
    """Catalog6."""
    numero_documento_identidad_receptor: str
    fecha_emision: str
    """dd/MM/yyyy."""
    importe_total: str
    numero_autorizacion: str | None = None


class SendResult(SendFileAnswer):
    """The answer to a sent file (a CDR, a ticket to verify later or a fault)
    and where it went."""

    send_target: Target
    verify_ticket_target: Target | None = None
    """Where the ticket is verified."""
