import requests
from typing import Dict, Any

def submit_answer(submit_url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Submit the JSON payload to submit_url. Returns JSON response as dict.
    Uses requests with short timeout; handles errors gracefully.
    """
    try:
        if not submit_url:
            # Some pages may include a POST endpoint in the page content; if absent, return a helpful error
            return {"error": "no_submit_url"}
        resp = requests.post(submit_url, json=payload, timeout=25)
        try:
            return resp.json()
        except Exception:
            return {"status_code": resp.status_code, "text": resp.text}
    except Exception as e:
        return {"error": str(e)}
