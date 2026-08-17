"""MCP-style tool endpoints — để Claude/agent kết nối LedgerLens như một tool.

MCP (Model Context Protocol) là chuẩn mở cho LLM/agent gọi tool & data source qua
một giao thức thống nhất ('USB-C cho AI tool'). Ở đây expose dạng tối giản: một
endpoint liệt kê tool (schema) + một endpoint gọi tool. Điểm quan trọng về BẢO MẬT:
tool 'search_policies' vẫn chạy qua ĐÚNG Identity + ACL pre-filter của người gọi —
agent KHÔNG được vượt quyền; kết quả vẫn bắt buộc citation. Tức là dù truy cập qua
agent, mọi guardrail compliance vẫn giữ nguyên.

Production: dùng SDK MCP thật (stdio/SSE transport, JSON-RPC). Interface tool giữ nguyên.
"""
from __future__ import annotations

from typing import Callable

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from .models import Identity
from .service import LedgerLensService


class ToolCall(BaseModel):
    name: str
    arguments: dict


def build_router(service: LedgerLensService, identity_dep: Callable) -> APIRouter:
    router = APIRouter(prefix="/mcp")

    @router.get("/tools")
    def list_tools():
        return {
            "tools": [{
                "name": "search_policies",
                "description": "Hỏi câu hỏi về policy/quy định; trả lời có citation, "
                               "tôn trọng ACL của người gọi, refuse nếu thiếu căn cứ.",
                "input_schema": {
                    "type": "object",
                    "properties": {"question": {"type": "string"}},
                    "required": ["question"],
                },
            }]
        }

    @router.post("/call")
    def call_tool(call: ToolCall, ident: Identity = Depends(identity_dep)):
        if call.name != "search_policies":
            return {"error": f"unknown tool: {call.name}"}
        question = str(call.arguments.get("question", ""))
        ans = service.query(ident, question)  # ACL + audit + guardrail vẫn áp dụng
        return {
            "content": ans.text,
            "citations": ans.citations,
            "refused": ans.refused,
            "out_of_scope_hint": ans.out_of_scope_hint,
        }

    return router
