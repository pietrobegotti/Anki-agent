"""Build a private Anki Agent plugin archive for a deployed MCP endpoint."""
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from urllib.parse import urlparse
from zipfile import ZIP_DEFLATED, ZipFile


PLUGIN_SOURCE = Path(__file__).resolve().parent / "anki-agent"
MCP_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json"


def validate_mcp_url(value: str) -> str:
    parsed = urlparse(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or not parsed.path.startswith("/")
        or parsed.path.rstrip("/").split("/")[-1] != "mcp"
    ):
        raise ValueError("MCP URL must be an HTTPS endpoint URL without credentials, query, or fragment")
    return value.rstrip("/")


def build_package(mcp_url: str, output: Path) -> Path:
    endpoint = validate_mcp_url(mcp_url)
    if not (PLUGIN_SOURCE / "plugin.json").is_file():
        raise FileNotFoundError(f"Plugin source is missing: {PLUGIN_SOURCE}")
    output = output.expanduser().resolve()
    if output == PLUGIN_SOURCE or PLUGIN_SOURCE in output.parents:
        raise ValueError("Write the archive outside the plugin source directory")

    mcp_manifest = {
        "$schema": MCP_SCHEMA,
        "mcpServers": {
            "anki-agent": {
                "type": "streamable-http",
                "url": endpoint,
                "extensions": {
                    "com.openai": {
                        "auth": {"type": "api_key", "headerScheme": "bearer"}
                    }
                },
            }
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="anki-agent-plugin-") as temp_dir:
        staging = Path(temp_dir) / "anki-agent"
        staging.mkdir()
        for source in PLUGIN_SOURCE.rglob("*"):
            if source.is_file():
                relative = source.relative_to(PLUGIN_SOURCE)
                destination = staging / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(source.read_bytes())
        (staging / "mcp.json").write_text(
            json.dumps(mcp_manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
            for source in sorted(staging.rglob("*")):
                if source.is_file():
                    archive.write(source, source.relative_to(staging.parent))

    with ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise ValueError("The generated plugin archive failed its CRC check")
        names = set(archive.namelist())
        required = {"anki-agent/plugin.json", "anki-agent/mcp.json", "anki-agent/skills/chat-to-anki/SKILL.md"}
        if not required.issubset(names):
            raise ValueError("The archive is missing a required plugin component")
        parsed_manifest = json.loads(archive.read("anki-agent/mcp.json"))
        if parsed_manifest["mcpServers"]["anki-agent"]["url"] != endpoint:
            raise ValueError("The archive MCP URL does not match the requested endpoint")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mcp-url", required=True, help="Public HTTPS MCP endpoint ending in /mcp")
    parser.add_argument("--output", type=Path, default=Path("dist/anki-agent-plugin.zip"))
    args = parser.parse_args()
    result = build_package(args.mcp_url, args.output)
    print(f"Plugin archive ready: {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
