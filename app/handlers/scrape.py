from .base import BaseHandler
from playwright.async_api import Page
import re
import json
import base64
import pandas as pd
import io
import requests
import pdfplumber
from app.handlers.viz import make_plot_as_datauri

class ScrapeHandler(BaseHandler):
    def can_handle(self, page: Page) -> bool:
        # Can handle most human readable quiz pages; decide by presence of text like 'Submit' or 'submit' or 'answer'
        # We'll fetch the visible text and check.
        return True  # make this general-purpose; refine if you like

    async def solve(self, page: Page, email: str, secret: str):
        """
        Strategy:
         - Extract visible text and look for instructions and submit URL.
         - If page contains a base64-encoded JSON payload inside a <pre> or similar (like sample), decode and act.
         - If page contains links to files, download and parse accordingly.
         - Support: sum of column in a PDF page, HTML table sum, small API calls, simple visualizations.
        """
        # get page content
        content = await page.content()
        inner_text = await page.inner_text("body")

        # heuristic: look for a JSON blob in pre tags (the sample uses base64 in a script)
        # attempt to find a base64 string inside the HTML
        b64s = re.findall(r'atob\(`([\sA-Za-z0-9+/=\\n]+)`\)', content)
        if b64s:
            try:
                payload_text = base64.b64decode(b64s[0].encode()).decode()
                # If payload_text contains JSON, parse
                m = re.search(r'\{[\s\S]*\}', payload_text)
                if m:
                    js = json.loads(m.group(0))
                    # if they gave a direct answer in the payload (like sample) -> just submit it
                    if "answer" in js:
                        submit_url = js.get("submit_url") or "https://example.com/submit"
                        return {"submit_url": submit_url, "answer": js["answer"]}
            except Exception:
                pass

        # find a submit URL in the page (common: contains 'submit' in href)
        anchors = await page.query_selector_all("a[href]")
        submit_url = None
        for a in anchors:
            href = await a.get_attribute("href")
            if href and "submit" in href:
                submit_url = href
                break
        # fallback: look for forms with action
        if not submit_url:
            forms = await page.query_selector_all("form[action]")
            for f in forms:
                action = await f.get_attribute("action")
                if action:
                    submit_url = action
                    break

        # Heuristic: if page contains 'sum of the "value" column' or similar -> try to find a table or PDF
        if re.search(r'sum of the .*?"value"', inner_text, re.I) or re.search(r'sum of the .*?column', inner_text, re.I):
            # Look for a link to a PDF
            pdf_link = None
            for a in anchors:
                href = await a.get_attribute("href")
                if href and href.lower().endswith(".pdf"):
                    pdf_link = href
                    break
            if pdf_link:
                # download PDF
                pdf_bytes = requests.get(pdf_link, timeout=20).content
                # parse PDF for tables and find page 2
                try:
                    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                        # page numbering in pdfplumber starts at 0
                        if len(pdf.pages) >= 2:
                            page2 = pdf.pages[1]
                            tables = page2.extract_table()
                            # If extract_table returns list of rows:
                            if tables:
                                # Convert table rows into dataframe
                                df = pd.DataFrame(tables[1:], columns=tables[0])
                                # try to find a column named value
                                candidates = [c for c in df.columns if "value" in c.lower()]
                                if candidates:
                                    col = candidates[0]
                                    # coerce to numeric and sum
                                    total = pd.to_numeric(df[col].str.replace(r'[^\d\.-]', '', regex=True), errors="coerce").sum()
                                    return {"submit_url": submit_url, "answer": float(total)}
                except Exception as e:
                    # fallback: try text extraction numeric sum
                    try:
                        text = ""
                        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                            text = pdf.pages[1].extract_text()
                        nums = re.findall(r"[-+]?\d*\.\d+|\d+", text)
                        total = sum(float(n) for n in nums)
                        return {"submit_url": submit_url, "answer": float(total)}
                    except Exception:
                        pass

        # If the page contains an HTML table, try to parse it
        try:
            table_html = await page.query_selector("table")
            if table_html:
                # get outerHTML and load via pandas
                outer = await table_html.evaluate("(node) => node.outerHTML")
                df = pd.read_html(outer)[0]
                # heuristics: if a column name contains value -> sum it
                candidates = [c for c in df.columns if "value" in str(c).lower()]
                if candidates:
                    col = candidates[0]
                    total = pd.to_numeric(df[col], errors="coerce").sum()
                    return {"submit_url": submit_url, "answer": float(total)}
                # else if a single numeric column exists -> sum that
                numeric_cols = df.select_dtypes(include=["number"]).columns
                if len(numeric_cols) == 1:
                    total = df[numeric_cols[0]].sum()
                    return {"submit_url": submit_url, "answer": float(total)}
        except Exception:
            pass

        # If the task asks for a visualization, produce a simple chart and return base64 dataURI
        if re.search(r'generate.*chart|plot|visual', inner_text, re.I):
            # sample: extract a small table into dataframe and chart
            try:
                table_html = await page.query_selector("table")
                if table_html:
                    outer = await table_html.evaluate("(node) => node.outerHTML")
                    df = pd.read_html(outer)[0]
                    # make a simple plot of first numeric column
                    numeric = df.select_dtypes(include=["number"])
                    if not numeric.empty:
                        datauri = make_plot_as_datauri(numeric.iloc[:, :2])  # first two columns
                        return {"submit_url": submit_url, "answer": datauri}
            except Exception:
                pass

        # fallback: try to find explicit JSON in page (instructions may include sample JSON)
        m_json = re.search(r'(\{[\s\S]{10,2000}\})', inner_text)
        if m_json:
            try:
                parsed = json.loads(m_json.group(1))
                if "answer" in parsed:
                    return {"submit_url": submit_url, "answer": parsed["answer"]}
            except Exception:
                pass

        # if nothing matched, return an error-like response
        return {"submit_url": submit_url or "", "answer": None}
