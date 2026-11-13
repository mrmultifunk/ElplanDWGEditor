from __future__ import annotations

"""Read-only client for the PL-dåse field-registration PWA.

The integration deliberately imports cable-entry documentation only.  It has
no functions that write conductor assignments, terminals or Wago splices.
"""

import json
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen

import core_logic as core


class PLDaaseApiError(RuntimeError):
    pass


def normalize_base_url(value: str) -> str:
    text=str(value or "").strip()
    if not text:
        return ""
    if "://" not in text:
        text="https://"+text
    parsed=urlsplit(text)
    if parsed.scheme not in {"http","https"} or not parsed.netloc:
        raise ValueError("Angiv en gyldig http- eller https-adresse.")
    path=parsed.path.rstrip("/")
    for suffix in ("/api/export","/api"):
        if path.endswith(suffix):
            path=path[:-len(suffix)].rstrip("/")
            break
    return urlunsplit((parsed.scheme,parsed.netloc,path,"",""))


def _error_message(status: int, detail: str = "") -> str:
    if status==401:return "API-tokenet mangler eller er ugyldigt."
    if status==404:return "PL-dåse-API'et blev ikke fundet på adressen."
    if status==429:return "PL-dåse-serveren har midlertidigt begrænset adgangen. Prøv igen senere."
    return detail or f"PL-dåse-serveren svarede med HTTP {status}."


def normalize_export_payload(payload, source_url: str = "") -> dict:
    if not isinstance(payload,dict) or not isinstance(payload.get("boxes"),list):
        raise PLDaaseApiError("Serveren returnerede ikke et gyldigt PL-dåse-eksportformat.")
    base=normalize_base_url(source_url) if source_url else ""
    exported=str(payload.get("exported","") or "").strip()
    imported_at=datetime.now(timezone.utc).isoformat().replace("+00:00","Z")
    boxes=[]
    for raw in payload.get("boxes",[]):
        if not isinstance(raw,dict):continue
        record=core.normalize_pl_field_record({
            **raw,
            "box_id":raw.get("id",raw.get("box_id","")),
            "source_url":base,
            "exported":exported,
            "imported_at":imported_at,
        })
        if record:boxes.append(record)
    boxes.sort(key=lambda row:(str(row.get("name","")).casefold(),str(row.get("box_id","")).casefold()))
    return {
        "exported":exported,
        "user":str(payload.get("user","") or "").strip(),
        "source_url":base,
        "boxes":boxes,
    }


def fetch_export(base_url: str, token: str, *, timeout: float = 15.0) -> dict:
    base=normalize_base_url(base_url)
    secret=str(token or "").strip()
    if not base:
        raise PLDaaseApiError("Angiv adressen til PL-dåse-serveren under Indstillinger.")
    if not secret:
        raise PLDaaseApiError("Angiv et API-token til PL-dåse-serveren under Indstillinger.")
    request=Request(
        base+"/api/export",
        headers={
            "Authorization":f"Bearer {secret}",
            "Accept":"application/json",
            "User-Agent":f"ElplanDWGEditor/{core.APP_VERSION}",
        },
    )
    try:
        with urlopen(request,timeout=max(1.0,float(timeout))) as response:
            raw=response.read(8_000_001)
            if len(raw)>8_000_000:raise PLDaaseApiError("PL-dåse-eksporten er større end den tilladte grænse på 8 MB.")
    except HTTPError as exc:
        detail=""
        try:detail=str(json.loads(exc.read().decode("utf-8")).get("error","") or "")
        except Exception:pass
        raise PLDaaseApiError(_error_message(int(exc.code),detail)) from exc
    except (URLError,TimeoutError,OSError) as exc:
        reason=getattr(exc,"reason",exc)
        raise PLDaaseApiError(f"Kunne ikke kontakte PL-dåse-serveren: {reason}") from exc
    try:payload=json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError,json.JSONDecodeError) as exc:
        raise PLDaaseApiError("PL-dåse-serveren returnerede ugyldig JSON.") from exc
    return normalize_export_payload(payload,base)


def fetch_photo(url: str, token: str, *, source_url: str = "", timeout: float = 15.0) -> bytes:
    photo_url=str(url or "").strip(); secret=str(token or "").strip()
    parsed=urlsplit(photo_url)
    if parsed.scheme not in {"http","https"} or not parsed.netloc:
        raise PLDaaseApiError("Fotoadressen er ugyldig.")
    if source_url:
        source=urlsplit(normalize_base_url(source_url))
        if (parsed.scheme,parsed.netloc)!=(source.scheme,source.netloc):
            raise PLDaaseApiError("Fotoadressen peger ikke på den konfigurerede PL-dåse-server.")
    request=Request(photo_url,headers={
        "Authorization":f"Bearer {secret}",
        "Accept":"image/jpeg",
        "User-Agent":f"ElplanDWGEditor/{core.APP_VERSION}",
    })
    try:
        with urlopen(request,timeout=max(1.0,float(timeout))) as response:
            content_type=str(response.headers.get("Content-Type","") or "").lower()
            raw=response.read(3_000_001)
            if len(raw)>3_000_000:raise PLDaaseApiError("Fotoet er større end den tilladte grænse på 3 MB.")
            if "image/jpeg" not in content_type:raise PLDaaseApiError("Serveren returnerede ikke et JPEG-foto.")
            return raw
    except HTTPError as exc:
        raise PLDaaseApiError(_error_message(int(exc.code))) from exc
    except (URLError,TimeoutError,OSError) as exc:
        reason=getattr(exc,"reason",exc)
        raise PLDaaseApiError(f"Kunne ikke hente fotoet: {reason}") from exc
