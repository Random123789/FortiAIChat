import os
import requests
from dotenv import load_dotenv
# mcp_server.py
from fastmcp import FastMCP

# Load environment variables
load_dotenv()
FMG_HOST = os.getenv("FMG_HOST")
FMG_USERNAME = os.getenv("FMG_USERNAME")   
FMG_PASSWORD = os.getenv("FMG_PASSWORD")


def require_env(name: str, value: str | None) -> str:
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


FMG_HOST = require_env("FMG_HOST", FMG_HOST).rstrip("/")
FMG_USERNAME = require_env("FMG_USERNAME", FMG_USERNAME)
FMG_PASSWORD = require_env("FMG_PASSWORD", FMG_PASSWORD)
# Create the MCP server instance
mcp = FastMCP("My First MCP Server")

# Define Tool 1: Add two numbers
@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers together"""
    return a + b

# Define Tool 2: Greet someone
@mcp.tool()
def greet(name: str) -> str:
    """Greet someone by name"""
    return f"Hello, {name}! Welcome!"

# Define Tool 3: Multiply numbers
@mcp.tool()
def multiply(a: float, b: float) -> float:
    """Multiply two numbers"""
    return a * b

# Define Tool 4: Get current time
@mcp.tool()
def get_time() -> str:
    """Get the current time"""
    from datetime import datetime
    return datetime.now().strftime("%I:%M %p")

def fmg_rpc(payload : dict) -> dict:
    response = requests.post(
        f"{FMG_HOST}/jsonrpc",
        json=payload,
        headers={"Content-Type": "application/json"},
        verify=False,
    )
    response.raise_for_status()
    data = response.json()

    result = data.get("result")
    if isinstance(result, list) and result:
        first_result = result[0]
        if isinstance(first_result, dict):
            status = first_result.get("status")
            if isinstance(status, dict):
                code = status.get("code", 0)
                if code not in (0, "0"):
                    message = status.get("message", "Unknown FortiManager error")
                    url = first_result.get("url", payload.get("params", [{}])[0].get("url", "unknown"))
                    raise RuntimeError(
                        f"FortiManager RPC error for {url}: code={code}, message={message}, response={data}"
                    )

    return data


def extract_session(login_data: dict) -> str | None:
    session = login_data.get("session")
    if session:
        return session

    result = login_data.get("result")
    if isinstance(result, list) and result:
        first_result = result[0]
        if isinstance(first_result, dict):
            session = first_result.get("session")
            if session:
                return session

    return None

def fmg_login() -> str:
    login_data = fmg_rpc({
        "method": "exec",
        "params": [
            {
                "url": "/sys/login/user",
                "data": {
                    "user": FMG_USERNAME,
                    "passwd": FMG_PASSWORD
                }
            }
        ],
        "id": 1
    })

    session = extract_session(login_data)

    if not session:
        raise RuntimeError(f"Failed to log in to FortiManager: {login_data}")

    return session

def fmg_logout(session: str) -> None:
    try:
        fmg_rpc({
            "method": "exec",
            "params": [
                {
                    "url": "/sys/logout",
                }
            ],
            "session": session,
            "id": 999
        })
    except Exception:
        pass

@mcp.tool()
def fortimanager_get_system_status() -> dict:
    """Get system status from FortiManager"""
    session = fmg_login()
    try:
        return fmg_rpc({
            "method": "get",
            "params": [
                {
                    "url": "/sys/status"
                }
            ],
            "session": session,
            "verbose": 1,
            "id": 2
        })
    finally:
        fmg_logout(session)

if __name__ == "__main__":
    stateless_http = True
    # Start the server
    mcp.run(transport="http", port=8080, stateless_http=True)