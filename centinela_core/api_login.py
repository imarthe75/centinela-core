"""API login for a test profile: POST the credentials, return the session token (from the JSON body or a response header).

`login` is the dict `test_credentials._derive_login()` builds:
  {url, method, json|form, token_json_path, token_header?, verify?, headers?, basic?}
Returns None on any failure and logs why (never the token, never the password).
"""
import logging
import re
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)
_OK = (200, 201)


def resolve_token(login: Dict[str, Any], timeout: int = 20, profile_name: str = "") -> Optional[str]:
    if not login:
        return None
    try:
        kw = {"timeout": timeout, "verify": login.get("verify", False)}
        if login.get("form"):
            kw["data"] = login["form"]
        elif login.get("json"):
            kw["json"] = login["json"]
        if login.get("headers"):
            kw["headers"] = login["headers"]
        if login.get("basic"):
            kw["auth"] = tuple(login["basic"])
        r = requests.request((login.get("method") or "POST").upper(), login["url"], **kw)
        if r.status_code not in _OK:
            logger.warning("login for profile %r -> HTTP %s", profile_name, r.status_code)
            return None
        if login.get("token_header"):
            val = r.headers.get(login["token_header"], "")
            return re.sub(r"^Bearer\s+", "", val, flags=re.IGNORECASE).strip() or None
        body = r.json()
        for k in (login.get("token_json_path") or "access_token").split("."):
            body = body[k]
        return str(body) or None
    except Exception:
        logger.error("login failed for profile %r", profile_name, exc_info=True)
        return None
