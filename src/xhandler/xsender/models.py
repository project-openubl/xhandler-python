"""Inputs and answers of the SUNAT services."""

from __future__ import annotations

import base64
from collections.abc import Iterator
from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, PlainSerializer


def _from_base64(value: object) -> object:
    return base64.b64decode(value) if isinstance(value, str) else value


Bytes = Annotated[
    bytes,
    BeforeValidator(_from_base64),
    PlainSerializer(lambda b: base64.b64encode(b).decode(), return_type=str, when_used="json"),
]
"""Raw bytes in Python, base64 in the JSON of the core."""


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class _Answer(BaseModel):
    """An answer of the core: ignores the fields a newer core adds."""

    model_config = ConfigDict(extra="ignore", frozen=True)


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


class Status(str, Enum):
    """The SUNAT verdict of a document; prints as SUNAT says it, e.g. ACEPTADO."""

    ACCEPTED = "ACEPTADO"
    REJECTED = "RECHAZADO"
    EXCEPTION = "EXCEPCION"
    IN_PROGRESS = "EN_PROCESO"
    UNKNOWN = "UNKNOWN"

    def __str__(self) -> str:
        return self.value


class CDR(_Answer):
    """The receipt SUNAT gives back (Constancia de Recepcion)."""

    zip: Bytes
    response_code: str
    description: str
    notes: list[str]
    document_description: str | None = None
    """For an accepted guía de remisión, the URL its printed copy's QR code must
    encode; None for other documents (and with a core older than 6.0.0-alpha.2)."""
    status: Status
    status_code: str | None = None
    """The ticket status, only when verifying a ticket."""


class Fault(_Answer):
    """An error answered by SUNAT."""

    code: str
    """SUNAT's code as given: the SOAP faultcode (e.g. "soap-env:Client.0111") or
    the error code of a REST answer (e.g. "1033")."""
    sunat_code: int | None = None
    """The number in ``code`` (111), when it has one."""
    http_status: int | None = None
    """The status of the answer, e.g. 500 for SOAP faults or 422 for REST errors."""
    message: str
    status: Status


class NoCDR(_Answer):
    """A ticket status without CDR, e.g. "98" (in progress)."""

    status_code: str
    status: Status


class SendResult(_Answer):
    """The answer to a sent file: a CDR, a ticket to verify later (summaries,
    voided documents, packs, guias) or a fault."""

    cdr: CDR | None = None
    ticket: str | None = None
    fault: Fault | None = None
    send_target: Target
    verify_ticket_target: Target | None = None
    """Where the ticket is verified."""


class VerifyResult(_Answer):
    """The answer to a ticket: a CDR, no CDR yet (e.g. in progress) or a fault."""

    cdr: CDR | None = None
    no_cdr: NoCDR | None = None
    fault: Fault | None = None


class ConsultStatus(_Answer):
    """e.g. "0001" (accepted) for get_status, or "0" for validate_cdp."""

    status_code: str
    status_message: str | None = None
    cdr_zip: Bytes | None = None
    """The CDR of get_status_cdr."""


class ConsultResult(_Answer):
    """The answer of the consult and validation services."""

    status: ConsultStatus | None = None
    fault: Fault | None = None
