import base64
import json

import httpx
import pytest
from conformance import cases

from xhandler import ErrorKind, XhandlerError
from xhandler.xsender import (
    BILL_CONSULT_SERVICE_URL,
    CDR,
    ConsultDocument,
    Credentials,
    FileSender,
    Status,
    SunatClient,
    URLs,
)

CREDENTIALS = Credentials(
    username="12345678959MODDATOS",
    password="MODDATOS",
    client_id="client-id",
    client_secret="client-secret",
)


def corpus_input(op: str, name: str) -> dict:
    return next(c for c in cases(op) if c.name == name).input


def answer(name: str) -> tuple[int, str]:
    """The SUNAT answer (status and body) recorded in a parse case."""
    case = corpus_input("parse", name)
    return case["status"], case["body"]


def document(name: str) -> bytes:
    """A UBL file of the corpus, e.g. "F001-1"."""
    return base64.b64decode(corpus_input("prepare_send_file", name)["xml"])


class Sunat:
    """Answers every request, whatever its host, with ``handle``."""

    def __init__(self, handle) -> None:
        self.requests: list[httpx.Request] = []
        self.handle = handle

    def client(self) -> SunatClient:
        def respond(request: httpx.Request) -> httpx.Response:
            self.requests.append(request)
            status, body = self.handle(request)
            return httpx.Response(status, text=body)

        return SunatClient(httpx.Client(transport=httpx.MockTransport(respond)))

    def sender(self, urls: URLs) -> FileSender:
        return FileSender(urls, CREDENTIALS, self.client())


def test_send_file_reads_the_cdr() -> None:
    sunat = Sunat(lambda _: answer("send_file_cdr"))
    result = sunat.sender(URLs.beta()).send_file(document("F001-1"))

    assert result.cdr is not None
    assert result.cdr.status is Status.ACCEPTED
    assert result.cdr.zip
    assert result.cdr.document_description is None
    assert result.send_target.url == URLs.beta().invoice
    assert result.verify_ticket_target is None
    request = sunat.requests[0]
    assert request.headers["SOAPAction"] == "urn:sendBill"
    assert str(request.url) == URLs.beta().invoice


def test_cdrs_carry_the_document_description() -> None:
    """A newer core may add fields: the answers keep reading"""
    cdr = CDR.model_validate(
        {
            "zip": "",
            "response_code": "0",
            "description": "La Guia numero T001-1, ha sido aceptada",
            "notes": [],
            "document_description": "https://e-factura.sunat.gob.pe/v1/contribuyente/gre/comprobantes/descargaqr?hashqr=abc",
            "status": "ACEPTADO",
            "added_by_a_newer_core": True,
        }
    )
    assert cdr.document_description == (
        "https://e-factura.sunat.gob.pe/v1/contribuyente/gre/comprobantes/descargaqr?hashqr=abc"
    )


def test_send_file_reads_faults() -> None:
    """SUNAT answers SOAP faults with HTTP 500"""
    sunat = Sunat(lambda _: answer("send_file_rejected"))
    result = sunat.sender(URLs.beta()).send_file(document("F001-1"))
    assert result.fault is not None
    assert result.fault.status is Status.REJECTED


def test_unreadable_answers_are_response_errors() -> None:
    sunat = Sunat(lambda _: (503, "<html>Service Unavailable</html>"))
    with pytest.raises(XhandlerError) as error:
        sunat.sender(URLs.beta()).send_file(document("F001-1"))
    assert error.value.kind is ErrorKind.RESPONSE


def test_verify_file_ticket_in_progress() -> None:
    sunat = Sunat(lambda _: answer("verify_ticket_in_progress"))
    result = sunat.sender(URLs.beta()).verify_file_ticket(
        document("RA-20200328-1"), "1703154974517"
    )
    assert result.no_cdr is not None
    assert result.no_cdr.status is Status.IN_PROGRESS


def test_guias_reuse_the_token_until_rejected() -> None:
    calls = {"tokens": 0, "sends": 0}

    def handle(request: httpx.Request) -> tuple[int, str]:
        if "/oauth2/token/" in request.url.path:
            calls["tokens"] += 1
            assert b"grant_type=password" in request.content
            return 200, json.dumps({"access_token": "the-token", "expires_in": 3600})
        calls["sends"] += 1
        assert request.headers["Authorization"] == "Bearer the-token"
        if calls["sends"] == 2:
            return 401, '{"cod":"401","msg":"Unauthorized"}'
        return 200, '{"numTicket":"a7b3c1d2-0001"}'

    sender = Sunat(handle).sender(URLs.production())
    for _ in range(3):
        assert sender.send_file(document("despatch-advice-T")).ticket
    # The second send is rejected once and retried with a new token
    assert calls == {"tokens": 2, "sends": 4}


def test_rate_limited_requests_are_retried() -> None:
    def handle(_: httpx.Request) -> tuple[int, str]:
        if len(sunat.requests) == 1:
            return 401, "<html><title>401 Authorization Required</title></html>"
        return answer("send_file_cdr")

    sunat = Sunat(handle)
    result = sunat.sender(URLs.beta()).send_file(document("F001-1"))
    assert result.cdr is not None
    assert len(sunat.requests) == 2


def test_the_security_api_url_can_be_set() -> None:
    token_urls: list[str] = []

    def handle(request: httpx.Request) -> tuple[int, str]:
        if "/oauth2/token/" in request.url.path:
            token_urls.append(str(request.url))
            return 200, json.dumps({"access_token": "the-token", "expires_in": 3600})
        return 200, '{"numTicket":"a7b3c1d2-0001"}'

    sunat = Sunat(handle)
    client = SunatClient(sunat.client()._http, security_api_url="http://localhost:8080")
    FileSender(URLs.production(), CREDENTIALS, client).send_file(document("despatch-advice-T"))
    assert token_urls == ["http://localhost:8080/v1/clientessol/client-id/oauth2/token/"]


def test_get_status_cdr() -> None:
    sunat = Sunat(lambda _: answer("get_status_cdr"))
    document = ConsultDocument(ruc="12345678912", tipo_comprobante="01", serie="F001", numero=1)
    result = sunat.client().get_status_cdr(BILL_CONSULT_SERVICE_URL, document, CREDENTIALS)

    assert result.status is not None
    assert result.status.status_code == "0004"
    assert result.status.cdr_zip == base64.b64decode("UEsDBA==")
    assert sunat.requests[0].headers["SOAPAction"] == "urn:getStatusCdr"


def test_credentials_hide_their_secrets() -> None:
    credentials = Credentials(
        username="user", password="the-password", client_secret="the-secret", token="the-token"
    )
    shown = f"{credentials!r} {credentials!s} {credentials}"
    for secret in ("the-password", "the-secret", "the-token"):
        assert secret not in shown


def test_a_supplied_token_is_used_as_is() -> None:
    def handle(request: httpx.Request) -> tuple[int, str]:
        assert request.headers["Authorization"] == "Bearer given-token"
        return 401, '{"cod":"401","msg":"Unauthorized"}'

    sunat = Sunat(handle)
    sender = FileSender(
        URLs.production(),
        Credentials(username="", password="", token="given-token"),
        sunat.client(),
    )
    sender.send_file(document("despatch-advice-T"))
    assert len(sunat.requests) == 1


def test_failed_connections_are_retried_once() -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if len(requests) == 1:
            raise httpx.ConnectError("connection refused", request=request)
        status, body = answer("send_file_cdr")
        return httpx.Response(status, text=body)

    client = SunatClient(httpx.Client(transport=httpx.MockTransport(respond)))
    result = FileSender(URLs.beta(), CREDENTIALS, client).send_file(document("F001-1"))
    assert result.cdr is not None
    assert len(requests) == 2


def test_guia_errors_carry_both_codes() -> None:
    def handle(request: httpx.Request) -> tuple[int, str]:
        if "/oauth2/token/" in request.url.path:
            return 200, json.dumps({"access_token": "the-token", "expires_in": 3600})
        return 422, json.dumps(
            {"cod": "422", "msg": "Unprocessable Entity", "errors": [{"cod": "1033", "msg": "x"}]}
        )

    result = Sunat(handle).sender(URLs.production()).send_file(document("despatch-advice-T"))
    assert result.fault is not None
    assert (result.fault.code, result.fault.http_status) == ("1033", 422)


def test_the_sunat_code_can_come_in_a_header() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        if "/oauth2/token/" in request.url.path:
            return httpx.Response(200, json={"access_token": "the-token", "expires_in": 3600})
        return httpx.Response(400, headers={"cod": "2033"}, json={"cod": "400", "msg": "Bad"})

    client = SunatClient(httpx.Client(transport=httpx.MockTransport(respond)))
    result = FileSender(URLs.production(), CREDENTIALS, client).send_file(
        document("despatch-advice-T")
    )
    assert result.fault is not None
    assert (result.fault.code, result.fault.status) == ("2033", Status.REJECTED)
