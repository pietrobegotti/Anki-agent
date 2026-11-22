"""MCP Streamable HTTP adapter for the authenticated remote Anki gateway."""
from __future__ import annotations

import os
from typing import Any

from mcp.server.mcpserver import Context, MCPServer

from .ankiconnect import AnkiConnect
from .config import AgentConfig
from .mutations import NoteMutationService
from .reader import NoteReader
from .remote import RemoteGateway, RemoteUserContext


def create_mcp_server(gateway: RemoteGateway) -> MCPServer:
    """Expose conversation-facing tools while reusing gateway auth and policy."""
    server = MCPServer("Anki Agent")

    def dispatch(ctx: Context, method: str, path: str, payload: dict[str, Any] | None = None):
        headers = ctx.headers or {}
        authorization = headers.get("authorization")
        status, result = gateway.dispatch(authorization, method, path, payload)
        return {"status": status, **result}

    @server.tool()
    def get_collection(ctx: Context) -> dict[str, Any]:
        """List the connected collection's decks and note types."""
        return dispatch(ctx, "GET", "/v1/collection")

    @server.tool()
    def inspect_note_type(ctx: Context, note_type: str) -> dict[str, Any]:
        """Return a note type's actual fields and card templates."""
        return dispatch(ctx, "POST", "/v1/note-types/inspect", {"note_type": note_type})

    @server.tool()
    def list_collection_docs(ctx: Context) -> dict[str, Any]:
        """List available note type, deck, and agent preference guides."""
        return dispatch(ctx, "GET", "/v1/collection/docs")

    @server.tool()
    def read_collection_doc(ctx: Context, path: str) -> dict[str, Any]:
        """Read one collection guide returned by list_collection_docs."""
        return dispatch(ctx, "POST", "/v1/collection/docs/read", {"path": path})

    @server.tool()
    def search_notes(
        ctx: Context,
        text: str | None = None,
        deck: str | None = None,
        note_type: str | None = None,
        tags: list[str] | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Search this user's Anki notes using optional text, deck, type, or tag filters."""
        return dispatch(ctx, "POST", "/v1/notes/search", {
            "text": text, "deck": deck, "note_type": note_type,
            "tags": tags or [], "limit": limit,
        })

    @server.tool()
    def propose_add_batch(ctx: Context, notes: list[dict[str, Any]]) -> dict[str, Any]:
        """Prepare and preview up to 50 new notes. Does not write to Anki."""
        return dispatch(ctx, "POST", "/v1/proposals/add-batch", {"notes": notes})

    @server.tool()
    def confirm_add_batch(
        ctx: Context, batch_id: str, decisions: dict[str, str]
    ) -> dict[str, Any]:
        """Apply approved notes and sync the changed local collection to AnkiWeb."""
        return dispatch(ctx, "POST", f"/v1/batches/{batch_id}/confirm", {"decisions": decisions})

    @server.tool()
    def cancel_add_batch(ctx: Context, batch_id: str) -> dict[str, Any]:
        """Cancel a pending batch without writing to Anki."""
        return dispatch(ctx, "POST", f"/v1/batches/{batch_id}/cancel", {})

    return server


def create_single_user_gateway() -> RemoteGateway:
    """Build the default remote context from process environment settings."""
    token = os.environ.get("ANKI_AGENT_BEARER_TOKEN", "").strip()
    if len(token) < 32:
        raise ValueError("ANKI_AGENT_BEARER_TOKEN must contain at least 32 characters")
    config = AgentConfig.from_env()
    anki = config.create_anki()
    gateway = RemoteGateway()
    gateway.register(
        token,
        RemoteUserContext(
            config.user_id,
            NoteReader(anki),
            NoteMutationService(anki),
        ),
    )
    return gateway


def main() -> int:
    """Run a single-user Streamable HTTP server behind an HTTPS proxy."""
    import argparse

    parser = argparse.ArgumentParser(prog="anki-agent-mcp")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    server = create_mcp_server(create_single_user_gateway())
    server.run(transport="streamable-http", host=args.host, port=args.port, json_response=True)
    return 0

