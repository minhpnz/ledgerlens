#Developed by HenryPhan
"""Query analytics warehouse — dùng sqlite3 (stdlib) làm cột-analytics nhẹ.

Vì sao sqlite3 ở đây (và cái gì thật sự dùng ở prod): plan gốc dùng DuckDB/BigQuery.
sqlite3 là stdlib → repo chạy được không cần cài gì, và ĐỦ để minh hoạ đúng ý tưởng:
tách analytics/audit-report ra khỏi đường query nóng, đổ vào một store truy vấn được
bằng SQL cho báo cáo compliance. Interface (record_query + report) không đổi khi thay
sang DuckDB (OLAP thật, cột-hoá, nhanh cho aggregate) — chỉ đổi connection.

Mỗi truy vấn ghi một dòng: ai, phòng ban, latency, số chunk lấy về, có cite/refuse/
injection không → phục vụ SLO dashboard + báo cáo kiểm toán ("tuần này có bao nhiêu
truy vấn bị injection, bao nhiêu bị refuse vì thiếu căn cứ").
"""
from __future__ import annotations

import sqlite3
import threading
from typing import Any, Dict, List


class Warehouse:
    def __init__(self, path: str = ":memory:") -> None:
        # check_same_thread=False + lock: FastAPI chạy đa luồng; sqlite cần bảo vệ.
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._lock = threading.Lock()
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS query_analytics(
                   ts TEXT, dept TEXT, actor TEXT, latency_ms REAL,
                   retrieved_count INTEGER, cited INTEGER, refused INTEGER,
                   injection INTEGER, out_of_scope INTEGER)"""
        )
        self._conn.commit()

    def record_query(self, ts: str, dept: str, actor: str, latency_ms: float,
                     retrieved_count: int, cited: bool, refused: bool,
                     injection: bool, out_of_scope: bool) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO query_analytics VALUES (?,?,?,?,?,?,?,?,?)",
                (ts, dept, actor, latency_ms, retrieved_count,
                 int(cited), int(refused), int(injection), int(out_of_scope)),
            )
            self._conn.commit()

    def report(self) -> Dict[str, Any]:
        """Tổng hợp cho SLO/compliance dashboard."""
        with self._lock:
            cur = self._conn.execute(
                """SELECT COUNT(*), AVG(latency_ms),
                          SUM(cited), SUM(refused), SUM(injection), SUM(out_of_scope)
                   FROM query_analytics"""
            )
            total, avg_lat, cited, refused, injection, oos = cur.fetchone()
            by_dept = self._conn.execute(
                "SELECT dept, COUNT(*) FROM query_analytics GROUP BY dept"
            ).fetchall()
        total = total or 0
        return {
            "total_queries": total,
            "avg_latency_ms": round(avg_lat or 0.0, 2),
            "citation_coverage": round((cited or 0) / total, 3) if total else 0.0,
            "refused": refused or 0,
            "injection_flagged": injection or 0,
            "out_of_scope_hints": oos or 0,
            "by_dept": {d: c for d, c in by_dept},
        }

    def recent(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._lock:
            cols = [c[0] for c in self._conn.execute("SELECT * FROM query_analytics LIMIT 0").description]
            rows = self._conn.execute(
                "SELECT * FROM query_analytics ORDER BY ts DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(zip(cols, r)) for r in rows]
