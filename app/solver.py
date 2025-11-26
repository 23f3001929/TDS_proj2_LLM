# app/solver.py

import time
import re
import json
import base64
import io
from typing import Dict, Any, Optional
from urllib.parse import urljoin

import requests
import pdfplumber
import pandas as pd
from playwright.sync_api import sync_playwright
import matplotlib.pyplot as plt

from app.config import MAX_QUIZ_SECONDS
from app.submitter import submit_answer


# -----------------------------------------------------------
# Helpers
# -----------------------------------------------------------

def now_seconds():
    return int(time.time())


def _extract_base64_payload_from_html(content: str) -> Optional[Dict[str, Any]]:
    """Extract a base64-encoded JSON payload from patterns like atob(`.....`)."""
    m = re.search(r'atob\(`([\sA-Za-z0-9+/=\n\r]+)`\)', content)
    if not m:
        return None
    try:
        decoded = base64.b64decode(m.group(1)).decode()
        j = re.search(r'(\{[\s\S]*\})', decoded)
        if j:
            return json.loads(j.group(1))
    except Exception:
        return None
    return None


def _find_submit_url_from_anchors(anchors):
    """Return the first href containing 'submit', else the first href, else None."""
    for h in anchors:
        if h and "submit" in h.lower():
            return h
    for h in anchors:
        if h:
            return h
    return None


def _scan_text_for_submit_url(text: str) -> Optional[str]:
    """Scan visible text for any URLs; prefer those containing 'submit'."""
    urls = re.findall(r'https?://[^\s\'"<>]+', text or "")
    if not urls:
        return None
    for u in urls:
        if "submit" in u.lower():
            return u
    return urls[0]  # fallback: first URL


def _sum_value_in_pdf_bytes(pdf_bytes: bytes) -> Optional[float]:
    """Parse PDF content, extract table on page 2, and sum 'value' column."""
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            if len(pdf.pages) < 2:
                return None

            page2 = pdf.pages[1]

            # Try table extraction
            table = page2.extract_table()
            if table and len(table) > 1:
                df = pd.DataFrame(table[1:], columns=table[0])
                candidates = [c for c in df.columns if "value" in str(c).lower()]
                if candidates:
                    col = candidates[0]
                    total = pd.to_numeric(
                        df[col].astype(str).str.replace(r"[^\d\.-]", "", regex=True),
                        errors="coerce"
                    ).sum()
                    return float(total)

            # Fallback: sum all numbers on page
            text = page2.extract_text() or ""
            nums = re.findall(r"[-+]?\d*\.\d+|\d+", text)
            if nums:
                return float(sum(float(n) for n in nums))

    except Exception:
        return None

    return None


def _sum_value_in_html_table(html: str) -> Optional[float]:
    """Parse HTML table and sum 'value' column or numeric columns."""
    try:
        dfs = pd.read_html(html)
        if not dfs:
            return None

        for df in dfs:
            # Check for 'value' column
            candidates = [c for c in df.columns if "value" in str(c).lower()]
            if candidates:
                col = candidates[0]
                total = pd.to_numeric(df[col], errors="coerce").sum()
                return float(total)

            # If exactly one numeric column exists
            numeric_cols = df.select_dtypes(include=["number"]).columns
            if len(numeric_cols) == 1:
                return float(df[numeric_cols[0]].sum())

    except Exception:
        return None

    return None


def _make_plot_datauri_from_html_table(html: str) -> Optional[str]:
    """Generate a PNG chart from the first numeric columns and return as base64 data URI."""
    try:
        dfs = pd.read_html(html)
        if not dfs:
            return None

        df = dfs[0]
        numeric = df.select_dtypes(include=["number"])
        if numeric.shape[1] == 0:
            return None

        buf = io.BytesIO()
        fig, ax = plt.subplots()

        if numeric.shape[1] == 1:
            numeric.plot(ax=ax)
        else:
            numeric.iloc[:, :2].plot(ax=ax)

        fig.tight_layout()
        fig.savefig(buf, format="png")
        plt.close(fig)

        buf.seek(0)
        encoded = base64.b64encode(buf.read()).decode()
        return f"data:image/png;base64,{encoded}"

    except Exception:
        return None


# -----------------------------------------------------------
# Core synchronous solver
# -----------------------------------------------------------

def run_sync_solver(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Visit the quiz URL, solve the task on each page, submit answers, follow next URLs.
    Fully synchronous using Playwright sync_api.
    """
    start = now_seconds()
    deadline = start + MAX_QUIZ_SECONDS

    current_url = payload.get("url")
    email = payload.get("email")
    secret = payload.get("secret")

    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        while current_url and now_seconds() < deadline:
            # Load page
            try:
                page.goto(current_url, wait_until="networkidle")
            except Exception as e:
                results.append({"url": current_url, "error": f"navigation_failed: {str(e)}"})
                break

            time.sleep(0.3)  # let JS settle

            content = page.content()
            try:
                body_text = page.inner_text("body")
            except Exception:
                body_text = ""

            # ---------------------------------------------------
            # 1) Check for embedded base64 instructions (the sample quiz does this)
            # ---------------------------------------------------
            base_json = _extract_base64_payload_from_html(content)
            if base_json:
                anchors = [a.get_attribute("href") for a in page.query_selector_all("a[href]")]
                submit_url = base_json.get("submit_url") or _find_submit_url_from_anchors(anchors) or _scan_text_for_submit_url(body_text)
                # Resolve relative URLs against current page
                resolved_submit = urljoin(current_url, submit_url or "") if submit_url else ""
                if "answer" in base_json:
                    answer = base_json["answer"]
                    resp = submit_answer(
                        resolved_submit,
                        {"email": email, "secret": secret, "url": current_url, "answer": answer}
                    )
                    results.append({"url": current_url, "submit_response": resp})
                    current_url = resp.get("url")
                    continue

            # ---------------------------------------------------
            # 2) Locate submit URL (anchors + text scanning fallback)
            # ---------------------------------------------------
            anchors = [a.get_attribute("href") for a in page.query_selector_all("a[href]")]
            submit_url = _find_submit_url_from_anchors(anchors)

            if not submit_url:
                submit_url = _scan_text_for_submit_url(body_text)

            # Resolve relative submit URL against the current page URL
            resolved_submit = urljoin(current_url, submit_url or "") if submit_url else ""

            # ---------------------------------------------------
            # 3) Look for PDF link → compute sum on page 2
            # ---------------------------------------------------
            pdf_link = next((h for h in anchors if h and str(h).lower().endswith(".pdf")), None)
            if pdf_link:
                try:
                    r = requests.get(pdf_link, timeout=20)
                    if r.ok:
                        total = _sum_value_in_pdf_bytes(r.content)
                        if total is not None:
                            resp = submit_answer(
                                resolved_submit,
                                {"email": email, "secret": secret, "url": current_url, "answer": float(total)}
                            )
                            results.append({"url": current_url, "submit_response": resp})
                            current_url = resp.get("url")
                            continue
                except Exception:
                    pass

            # ---------------------------------------------------
            # 4) HTML table → sum or visualization
            # ---------------------------------------------------
            try:
                table = page.query_selector("table")
                if table:
                    html_table = table.evaluate("(node) => node.outerHTML")

                    # Try sum of values
                    total = _sum_value_in_html_table(html_table)
                    if total is not None:
                        resp = submit_answer(
                            resolved_submit,
                            {"email": email, "secret": secret, "url": current_url, "answer": float(total)}
                        )
                        results.append({"url": current_url, "submit_response": resp})
                        current_url = resp.get("url")
                        continue

                    # Try visualization
                    if re.search(r"generate.*chart|plot|visual", body_text, re.I):
                        datauri = _make_plot_datauri_from_html_table(html_table)
                        if datauri:
                            resp = submit_answer(
                                resolved_submit,
                                {"email": email, "secret": secret, "url": current_url, "answer": datauri}
                            )
                            results.append({"url": current_url, "submit_response": resp})
                            current_url = resp.get("url")
                            continue
            except Exception:
                pass

            # ---------------------------------------------------
            # 5) Fallback: inline JSON in text
            # ---------------------------------------------------
            m_json = re.search(r"(\{[\s\S]{10,2000}\})", body_text)
            if m_json:
                try:
                    parsed = json.loads(m_json.group(1))
                    if "answer" in parsed:
                        resp = submit_answer(
                            resolved_submit,
                            {"email": email, "secret": secret, "url": current_url, "answer": parsed["answer"]}
                        )
                        results.append({"url": current_url, "submit_response": resp})
                        current_url = resp.get("url")
                        continue
                except Exception:
                    pass

            # ---------------------------------------------------
            # No handler matched → stop
            # ---------------------------------------------------
            results.append({"url": current_url, "error": "no_handler_matched"})
            break

        try:
            browser.close()
        except Exception:
            pass

    return {
        "results": results,
        "elapsed_seconds": now_seconds() - start
    }


# -----------------------------------------------------------
# Async wrapper called by FastAPI
# -----------------------------------------------------------

async def handle_quiz_request(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Run the synchronous solver in a worker thread so FastAPI stays async."""
    import asyncio
    return await asyncio.to_thread(run_sync_solver, payload)
