#!/usr/bin/env python3
"""Entry point for local development."""

import uvicorn

if __name__ == "__main__":
    uvicorn.run("src.app:create_app", factory=True, host="0.0.0.0", port=3333, reload=True)
