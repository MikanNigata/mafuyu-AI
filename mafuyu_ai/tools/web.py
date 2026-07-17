"""Public web and local tweet-search tools."""

import json
import sqlite3

import urllib3

from mafuyu_ai.settings import (
    DATA_DIR,
    FETCH_MAX_CHARS,
    FETCH_MAX_HTML_BYTES,
    FETCH_MAX_JSON_BYTES,
    FETCH_MAX_TEXT_BYTES,
)
from mafuyu_ai.tools.safety import _read_limited_response_body, fetch_public_response


def fetch_url(url: str) -> dict:
    """公開URLの本文を文字列として取得する。"""
    try:
        validated_url, resp = fetch_public_response(url)
        try:
            text_full = _read_limited_response_body(resp, FETCH_MAX_TEXT_BYTES).decode(
                "utf-8", errors="replace"
            )
        finally:
            resp.release_conn()

        text = text_full[:FETCH_MAX_CHARS]
        truncated = len(text_full) > FETCH_MAX_CHARS

        return {
            "url": validated_url,
            "status": resp.status,
            "content": text,
            "truncated": truncated,
        }
    except Exception as e:
        return {"error": f"fetch_url failed: {e}"}


def fetch_json(url: str) -> dict:
    """公開URLの JSON を取得して Python オブジェクトへ変換する。"""
    try:
        validated_url, resp = fetch_public_response(url)
        try:
            body = _read_limited_response_body(resp, FETCH_MAX_JSON_BYTES).decode(
                "utf-8", errors="strict"
            )
        finally:
            resp.release_conn()

        return {"url": validated_url, "status": resp.status, "data": json.loads(body)}
    except json.JSONDecodeError as e:
        return {"error": f"JSON parse failed: {e}"}
    except (ValueError, UnicodeDecodeError, urllib3.exceptions.HTTPError) as e:
        return {"error": f"fetch_json failed: {e}"}


def read_url(url: str) -> dict:
    """
    Web ページを取得し、人が読みやすい本文テキストへ整形する。

    LLM に外部コンテンツを再要約させると間接プロンプトインジェクションの
    面が増えるため、ここでは BeautifulSoup で機械的に整形するだけにしている。
    """
    try:
        from bs4 import BeautifulSoup

        validated_url, resp = fetch_public_response(url)
        try:
            html = _read_limited_response_body(resp, FETCH_MAX_HTML_BYTES).decode(
                "utf-8", errors="replace"
            )
        finally:
            resp.release_conn()
        soup = BeautifulSoup(html, "html.parser")

        # スクリプトやレイアウト要素は本文抽出のノイズになるので落とす。
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.decompose()

        # ページ全体からテキストだけを抜き出す。
        text = soup.get_text(separator="\n")

        # 改行や余白を整えて、読みやすいプレーンテキストに寄せる。
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = "\n".join(chunk for chunk in chunks if chunk)

        title = soup.title.string if soup.title else ""
        # 長すぎるページは deterministic に打ち切る。
        if len(text) > 3000:
            text = text[:3000] + "...(truncated)"

        return {"url": validated_url, "title": title, "content": text}
    except ImportError:
        return {"error": "bs4 not installed. Run `pip install beautifulsoup4`"}
    except Exception as e:
        return {"error": f"read_url failed: {e}"}


def search_web(query: str) -> dict:
    """
    Search the web using duckduckgo-search library.
    Returns structured results: [{title, url, snippet}, ...]
    """
    try:
        # Sanity Check
        query = query.strip()
        if not query:
            return {"error": "Empty query"}
        if len(query) < 2 and not query.isascii():  # Single kana is ok? Maybe too risky
            pass  # Let it slide for now, but watch out

        # Self-referential loop prevention
        # e.g. "search_web: search_web: ..."
        if "search_web:" in query or "tools." in query:
            clean_query = query.replace("search_web:", "").strip()
            if not clean_query:
                return {"error": "Invalid query (self-reference)"}
            query = clean_query  # Auto-fix

        # Temporal Awareness: Add current date to time-sensitive queries
        from datetime import datetime

        time_keywords = [
            "現在",
            "今",
            "最新",
            "今日",
            "首相",
            "大統領",
            "総裁",
            "current",
            "now",
            "latest",
            "president",
            "prime minister",
        ]
        query_lower = query.lower()
        if any(kw in query_lower or kw in query for kw in time_keywords):
            current_date = datetime.now().strftime("%Y年%m月")
            if current_date not in query:
                query = f"{query} {current_date}"
                print(f"[Smart Search] Added date: {query}")

        from ddgs import DDGS

        results = []
        with DDGS() as ddgs:
            # region="jp-jp" prioritizes Japanese results
            ddg_gen = ddgs.text(query, region="jp-jp", max_results=5)
            if ddg_gen:
                for r in ddg_gen:
                    results.append(
                        {
                            "title": r.get("title", ""),
                            "url": r.get("href", ""),
                            "snippet": r.get("body", ""),
                        }
                    )

        return {"query": query, "results": results}
    except Exception as e:
        return {"error": f"search_web failed: {e}"}


def search_tweets(query: str, limit: int = 5) -> dict:
    """
    Search past tweets in the local database.
    RAG (Retrieval-Augmented Generation) function.
    """
    try:
        db_path = DATA_DIR / "memory.db"
        if not db_path.exists():
            return {"error": "Tweet database not found. Has ingestion been run?"}

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Simple LIKE search
        sql = "SELECT date, text, likes, retweets FROM tweets WHERE text LIKE ? ORDER BY date DESC LIMIT ?"
        cursor.execute(sql, (f"%{query}%", limit))
        rows = cursor.fetchall()

        results = []
        for row in rows:
            date, text, likes, retweets = row
            results.append(f"[{date}] {text} (Fav:{likes})")

        conn.close()

        if not results:
            return {"results": [], "summary": f"No tweets found for '{query}'"}

        return {
            "query": query,
            "count": len(results),
            "results": results,
            "formatted": "\n".join(results),
        }
    except Exception as e:
        return {"error": f"search_tweets failed: {e}"}
