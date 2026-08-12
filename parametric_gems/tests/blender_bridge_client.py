from __future__ import annotations

import json
import socket
import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: blender_bridge_client.py <blender-script.py>")

    code = Path(sys.argv[1]).read_text(encoding="utf-8")
    request = {
        "type": "execute",
        "code": code,
        "strict_json": True,
    }

    with socket.create_connection(("127.0.0.1", 9876), timeout=10.0) as connection:
        connection.sendall(json.dumps(request).encode("utf-8") + b"\0")
        response_bytes = bytearray()
        while b"\0" not in response_bytes:
            chunk = connection.recv(4096)
            if not chunk:
                raise RuntimeError("Blender MCP bridge closed the connection")
            response_bytes.extend(chunk)

    response = json.loads(bytes(response_bytes[: response_bytes.index(b"\0")]))
    print(json.dumps(response, indent=2))
    if response.get("status") != "ok":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
