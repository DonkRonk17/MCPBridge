#!/usr/bin/env python3
"""
MCPBridge - MCP/A2A Protocol Interoperability for BCH (Beacon Command Hub)

Enables BCH agents to discover and collaborate with external AI agents via
standardized protocols: MCP (Model Context Protocol by Anthropic) and A2A
(Agent-to-Agent Protocol by Google). Creates a true 'Internet of Agents' by
making BCH a node in the global agent network.

Key Components:
  - AgentCard: Data class for agent capability advertisement (A2A spec)
  - MCPServerAdapter: Exposes BCH agents as MCP-compliant servers
  - A2AClientModule: Discovers and communicates with external A2A agents
  - CapabilityRegistry: SQLite-backed store for agent capabilities
  - ProtocolBridge: Orchestrates routing between MCP/A2A and BCH WebSocket

Protocol Support:
  - MCP (Model Context Protocol): Tools, resources, prompts over JSON-RPC
  - A2A (Agent-to-Agent): Agent cards, task delegation, streaming

Author: ATLAS (Team Brain Implementation Lead)
For: Logan Smith / Metaphy LLC
Version: 1.0
Date: February 21, 2026
License: MIT
"""

import argparse
import json
import logging
import os
import sqlite3
import sys
import threading
import time
import urllib.request
import urllib.error
import urllib.parse
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VERSION = "1.0.0"
DEFAULT_DB_PATH = Path.home() / ".mcpbridge" / "registry.db"
DEFAULT_LOG_PATH = Path.home() / ".mcpbridge" / "mcpbridge.log"
DEFAULT_MCP_PORT = 8765
DEFAULT_A2A_PORT = 8766

# MCP JSON-RPC method constants
MCP_METHOD_INITIALIZE = "initialize"
MCP_METHOD_TOOLS_LIST = "tools/list"
MCP_METHOD_TOOLS_CALL = "tools/call"
MCP_METHOD_RESOURCES_LIST = "resources/list"
MCP_METHOD_RESOURCES_READ = "resources/read"
MCP_METHOD_PROMPTS_LIST = "prompts/list"
MCP_METHOD_PROMPTS_GET = "prompts/get"
MCP_NOTIFICATION_INITIALIZED = "notifications/initialized"

# A2A well-known endpoints
A2A_AGENT_CARD_PATH = "/.well-known/agent.json"

# Status codes
STATUS_OK = "ok"
STATUS_ERROR = "error"
STATUS_PENDING = "pending"
STATUS_RUNNING = "running"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"


# ---------------------------------------------------------------------------
# Logging Setup
# ---------------------------------------------------------------------------

def setup_logging(log_path: Optional[Path] = None, verbose: bool = False) -> logging.Logger:
    """Configure logging with file and console handlers."""
    logger = logging.getLogger("mcpbridge")
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S"
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    if log_path:
        log_path = Path(log_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------

@dataclass
class MCPTool:
    """Represents an MCP tool definition."""
    name: str
    description: str
    input_schema: Dict[str, Any] = field(default_factory=dict)

    def to_mcp_dict(self) -> Dict[str, Any]:
        """Serialize to MCP protocol format."""
        schema = self.input_schema if self.input_schema else {
            "type": "object",
            "properties": {},
            "required": []
        }
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": schema
        }


@dataclass
class MCPResource:
    """Represents an MCP resource."""
    uri: str
    name: str
    description: str = ""
    mime_type: str = "text/plain"

    def to_mcp_dict(self) -> Dict[str, Any]:
        """Serialize to MCP protocol format."""
        result = {
            "uri": self.uri,
            "name": self.name,
            "mimeType": self.mime_type
        }
        if self.description:
            result["description"] = self.description
        return result


@dataclass
class MCPPrompt:
    """Represents an MCP prompt template."""
    name: str
    description: str
    arguments: List[Dict[str, Any]] = field(default_factory=list)

    def to_mcp_dict(self) -> Dict[str, Any]:
        """Serialize to MCP protocol format."""
        return {
            "name": self.name,
            "description": self.description,
            "arguments": self.arguments
        }


@dataclass
class AgentCard:
    """
    A2A Agent Card - describes an agent's capabilities and endpoints.

    Follows Google A2A specification for agent discovery and capability
    advertisement. Agent cards are served at /.well-known/agent.json.
    """
    name: str
    description: str
    url: str
    version: str = "1.0.0"
    capabilities: Dict[str, Any] = field(default_factory=dict)
    skills: List[Dict[str, Any]] = field(default_factory=list)
    default_input_modes: List[str] = field(default_factory=lambda: ["text/plain"])
    default_output_modes: List[str] = field(default_factory=lambda: ["text/plain"])
    authentication: Dict[str, Any] = field(default_factory=lambda: {"schemes": ["none"]})
    provider: Optional[Dict[str, str]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to A2A-compliant JSON format."""
        result = {
            "name": self.name,
            "description": self.description,
            "url": self.url,
            "version": self.version,
            "capabilities": self.capabilities,
            "skills": self.skills,
            "defaultInputModes": self.default_input_modes,
            "defaultOutputModes": self.default_output_modes,
            "authentication": self.authentication
        }
        if self.provider:
            result["provider"] = self.provider
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentCard":
        """Deserialize from A2A JSON format."""
        return cls(
            name=data.get("name", "Unknown Agent"),
            description=data.get("description", ""),
            url=data.get("url", ""),
            version=data.get("version", "1.0.0"),
            capabilities=data.get("capabilities", {}),
            skills=data.get("skills", []),
            default_input_modes=data.get("defaultInputModes", ["text/plain"]),
            default_output_modes=data.get("defaultOutputModes", ["text/plain"]),
            authentication=data.get("authentication", {"schemes": ["none"]}),
            provider=data.get("provider")
        )

    @classmethod
    def for_bch_agent(cls, agent_name: str, agent_description: str,
                      host: str = "localhost", port: int = DEFAULT_A2A_PORT,
                      skills: Optional[List[Dict[str, Any]]] = None) -> "AgentCard":
        """
        Factory method to generate an A2A Agent Card for a BCH agent.

        Args:
            agent_name: BCH agent name (e.g., ATLAS, FORGE, CLIO)
            agent_description: What the agent does
            host: Host where A2A server runs
            port: Port for A2A endpoint
            skills: Optional list of skill definitions

        Returns:
            AgentCard ready for A2A publication
        """
        url = f"http://{host}:{port}/agents/{agent_name.lower()}"
        return cls(
            name=agent_name,
            description=agent_description,
            url=url,
            version="1.0.0",
            capabilities={
                "streaming": True,
                "pushNotifications": False,
                "stateTransitionHistory": True
            },
            skills=skills or [
                {
                    "id": f"{agent_name.lower()}_default",
                    "name": f"{agent_name} Default Skill",
                    "description": agent_description,
                    "inputModes": ["text/plain"],
                    "outputModes": ["text/plain"]
                }
            ],
            provider={
                "organization": "Metaphy LLC",
                "url": "https://github.com/DonkRonk17"
            }
        )


@dataclass
class A2ATask:
    """Represents an A2A task (unit of work delegated between agents)."""
    task_id: str
    agent_name: str
    message: str
    status: str = STATUS_PENDING
    result: Optional[str] = None
    error: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to A2A task format."""
        return {
            "id": self.task_id,
            "status": {"state": self.status},
            "agentName": self.agent_name,
            "message": self.message,
            "result": self.result,
            "error": self.error,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
            "metadata": self.metadata
        }


# ---------------------------------------------------------------------------
# Capability Registry
# ---------------------------------------------------------------------------

class CapabilityRegistry:
    """
    SQLite-backed registry for agent capabilities.

    Stores and retrieves Agent Cards, tool registrations, and capability
    metadata. Enables fast lookup and discovery of available agents.
    """

    def __init__(self, db_path: Path = DEFAULT_DB_PATH):
        """
        Initialize the capability registry.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS agent_cards (
                    agent_name TEXT PRIMARY KEY,
                    card_json TEXT NOT NULL,
                    registered_at TEXT NOT NULL,
                    last_seen TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS mcp_tools (
                    tool_id TEXT PRIMARY KEY,
                    agent_name TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    tool_json TEXT NOT NULL,
                    registered_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS task_log (
                    task_id TEXT PRIMARY KEY,
                    agent_name TEXT NOT NULL,
                    message TEXT NOT NULL,
                    status TEXT NOT NULL,
                    result TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_mcp_tools_agent
                ON mcp_tools (agent_name)
            """)
            conn.commit()

    def register_agent(self, card: AgentCard) -> None:
        """
        Register or update an agent card in the registry.

        Args:
            card: AgentCard to register
        """
        now = datetime.now(timezone.utc).isoformat()
        card_json = json.dumps(card.to_dict())
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO agent_cards
                (agent_name, card_json, registered_at, last_seen)
                VALUES (?, ?, COALESCE(
                    (SELECT registered_at FROM agent_cards WHERE agent_name = ?), ?
                ), ?)
            """, (card.name, card_json, card.name, now, now))
            conn.commit()

    def get_agent(self, agent_name: str) -> Optional[AgentCard]:
        """
        Retrieve an agent card by name.

        Args:
            agent_name: Name of the agent to retrieve

        Returns:
            AgentCard if found, None otherwise
        """
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT card_json FROM agent_cards WHERE agent_name = ?",
                (agent_name,)
            ).fetchone()
        if row:
            return AgentCard.from_dict(json.loads(row[0]))
        return None

    def list_agents(self) -> List[AgentCard]:
        """
        List all registered agents.

        Returns:
            List of all AgentCard entries
        """
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT card_json FROM agent_cards ORDER BY agent_name"
            ).fetchall()
        return [AgentCard.from_dict(json.loads(row[0])) for row in rows]

    def remove_agent(self, agent_name: str) -> bool:
        """
        Remove an agent from the registry.

        Args:
            agent_name: Name of agent to remove

        Returns:
            True if removed, False if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM agent_cards WHERE agent_name = ?", (agent_name,)
            )
            conn.commit()
            return cursor.rowcount > 0

    def register_tool(self, agent_name: str, tool: MCPTool) -> None:
        """
        Register an MCP tool for an agent.

        Args:
            agent_name: Agent that owns this tool
            tool: MCPTool to register
        """
        tool_id = f"{agent_name}::{tool.name}"
        now = datetime.now(timezone.utc).isoformat()
        tool_json = json.dumps(tool.to_mcp_dict())
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO mcp_tools
                (tool_id, agent_name, tool_name, tool_json, registered_at)
                VALUES (?, ?, ?, ?, ?)
            """, (tool_id, agent_name, tool.name, tool_json, now))
            conn.commit()

    def get_tools_for_agent(self, agent_name: str) -> List[MCPTool]:
        """
        Get all MCP tools registered for an agent.

        Args:
            agent_name: Agent to query

        Returns:
            List of MCPTool entries
        """
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT tool_json FROM mcp_tools WHERE agent_name = ? ORDER BY tool_name",
                (agent_name,)
            ).fetchall()
        tools = []
        for row in rows:
            data = json.loads(row[0])
            tools.append(MCPTool(
                name=data["name"],
                description=data["description"],
                input_schema=data.get("inputSchema", {})
            ))
        return tools

    def log_task(self, task: A2ATask) -> None:
        """
        Log an A2A task to the database.

        Args:
            task: A2ATask to store
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO task_log
                (task_id, agent_name, message, status, result, error, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                task.task_id, task.agent_name, task.message, task.status,
                task.result, task.error, task.created_at, task.updated_at
            ))
            conn.commit()

    def get_task(self, task_id: str) -> Optional[A2ATask]:
        """
        Retrieve a task by ID.

        Args:
            task_id: Task identifier

        Returns:
            A2ATask if found, None otherwise
        """
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM task_log WHERE task_id = ?", (task_id,)
            ).fetchone()
        if row:
            return A2ATask(
                task_id=row[0], agent_name=row[1], message=row[2],
                status=row[3], result=row[4], error=row[5],
                created_at=row[6], updated_at=row[7]
            )
        return None

    def list_tasks(self, agent_name: Optional[str] = None,
                   limit: int = 50) -> List[A2ATask]:
        """
        List recent tasks, optionally filtered by agent.

        Args:
            agent_name: Filter by agent (None = all agents)
            limit: Maximum number of tasks to return

        Returns:
            List of A2ATask entries, newest first
        """
        with sqlite3.connect(self.db_path) as conn:
            if agent_name:
                rows = conn.execute(
                    "SELECT * FROM task_log WHERE agent_name = ? "
                    "ORDER BY created_at DESC LIMIT ?",
                    (agent_name, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM task_log ORDER BY created_at DESC LIMIT ?",
                    (limit,)
                ).fetchall()
        return [
            A2ATask(
                task_id=row[0], agent_name=row[1], message=row[2],
                status=row[3], result=row[4], error=row[5],
                created_at=row[6], updated_at=row[7]
            )
            for row in rows
        ]


# ---------------------------------------------------------------------------
# MCP JSON-RPC Protocol Implementation
# ---------------------------------------------------------------------------

class MCPProtocol:
    """
    MCP (Model Context Protocol) JSON-RPC 2.0 protocol handler.

    Implements the MCP specification for exposing BCH agent capabilities
    as MCP-compliant server instances. Supports:
    - initialize / notifications/initialized handshake
    - tools/list and tools/call
    - resources/list and resources/read
    - prompts/list and prompts/get
    """

    PROTOCOL_VERSION = "2024-11-05"

    def __init__(self, server_name: str, server_version: str = "1.0.0",
                 tools: Optional[List[MCPTool]] = None,
                 resources: Optional[List[MCPResource]] = None,
                 prompts: Optional[List[MCPPrompt]] = None):
        """
        Initialize MCP protocol handler.

        Args:
            server_name: Name for this MCP server
            server_version: Server version string
            tools: List of tools to expose
            resources: List of resources to expose
            prompts: List of prompt templates to expose
        """
        self.server_name = server_name
        self.server_version = server_version
        self.tools = tools or []
        self.resources = resources or []
        self.prompts = prompts or []
        self._tool_handlers: Dict[str, Callable] = {}
        self._resource_handlers: Dict[str, Callable] = {}
        self._prompt_handlers: Dict[str, Callable] = {}
        self._initialized = False

    def register_tool_handler(self, tool_name: str,
                               handler: Callable[[Dict[str, Any]], Any]) -> None:
        """
        Register a handler function for a tool call.

        Args:
            tool_name: Name of the tool (must match a registered MCPTool)
            handler: Callable that accepts arguments dict and returns result
        """
        self._tool_handlers[tool_name] = handler

    def register_resource_handler(self, uri: str,
                                   handler: Callable[[], str]) -> None:
        """
        Register a handler to read a resource.

        Args:
            uri: Resource URI (must match a registered MCPResource)
            handler: Callable that returns resource content
        """
        self._resource_handlers[uri] = handler

    def register_prompt_handler(self, name: str,
                                 handler: Callable[[Dict[str, Any]], List[Dict[str, Any]]]) -> None:
        """
        Register a handler to render a prompt template.

        Args:
            name: Prompt name
            handler: Callable that accepts arguments and returns messages list
        """
        self._prompt_handlers[name] = handler

    def handle_request(self, raw_message: str) -> Optional[str]:
        """
        Process an incoming JSON-RPC 2.0 message.

        Args:
            raw_message: Raw JSON string from MCP client

        Returns:
            JSON response string, or None for notifications
        """
        try:
            msg = json.loads(raw_message)
        except json.JSONDecodeError as exc:
            return self._error_response(
                None, -32700, f"Parse error: {exc}"
            )

        msg_id = msg.get("id")
        method = msg.get("method", "")
        params = msg.get("params", {})

        # Notification (no response needed)
        if "id" not in msg:
            if method == MCP_NOTIFICATION_INITIALIZED:
                self._initialized = True
            return None

        # Route to handler
        try:
            result = self._dispatch(method, params)
            return json.dumps({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": result
            })
        except MCPError as exc:
            return self._error_response(msg_id, exc.code, exc.message)
        except Exception as exc:
            return self._error_response(
                msg_id, -32603, f"Internal error: {exc}"
            )

    def _dispatch(self, method: str,
                  params: Dict[str, Any]) -> Any:
        """Route method to appropriate handler."""
        dispatch_map = {
            MCP_METHOD_INITIALIZE: self._handle_initialize,
            MCP_METHOD_TOOLS_LIST: self._handle_tools_list,
            MCP_METHOD_TOOLS_CALL: self._handle_tools_call,
            MCP_METHOD_RESOURCES_LIST: self._handle_resources_list,
            MCP_METHOD_RESOURCES_READ: self._handle_resources_read,
            MCP_METHOD_PROMPTS_LIST: self._handle_prompts_list,
            MCP_METHOD_PROMPTS_GET: self._handle_prompts_get,
        }
        handler = dispatch_map.get(method)
        if not handler:
            raise MCPError(-32601, f"Method not found: {method}")
        return handler(params)

    def _handle_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle MCP initialize handshake."""
        client_info = params.get("clientInfo", {})
        client_name = client_info.get("name", "Unknown Client")
        return {
            "protocolVersion": self.PROTOCOL_VERSION,
            "capabilities": {
                "tools": {} if self.tools else None,
                "resources": {} if self.resources else None,
                "prompts": {} if self.prompts else None
            },
            "serverInfo": {
                "name": self.server_name,
                "version": self.server_version
            },
            "_meta": {
                "clientName": client_name,
                "bchBridge": "MCPBridge v1.0"
            }
        }

    def _handle_tools_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tools/list request."""
        return {"tools": [t.to_mcp_dict() for t in self.tools]}

    def _handle_tools_call(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tools/call request."""
        tool_name = params.get("name")
        if not tool_name:
            raise MCPError(-32602, "Missing required parameter: name")

        tool_names = [t.name for t in self.tools]
        if tool_name not in tool_names:
            raise MCPError(-32602, f"Unknown tool: {tool_name}")

        handler = self._tool_handlers.get(tool_name)
        if not handler:
            raise MCPError(-32603, f"No handler registered for tool: {tool_name}")

        arguments = params.get("arguments", {})
        result = handler(arguments)

        if isinstance(result, str):
            content = [{"type": "text", "text": result}]
        elif isinstance(result, dict):
            content = [{"type": "text", "text": json.dumps(result, indent=2)}]
        else:
            content = [{"type": "text", "text": str(result)}]

        return {"content": content, "isError": False}

    def _handle_resources_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle resources/list request."""
        return {"resources": [r.to_mcp_dict() for r in self.resources]}

    def _handle_resources_read(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle resources/read request."""
        uri = params.get("uri")
        if not uri:
            raise MCPError(-32602, "Missing required parameter: uri")

        resource_uris = [r.uri for r in self.resources]
        if uri not in resource_uris:
            raise MCPError(-32002, f"Resource not found: {uri}")

        handler = self._resource_handlers.get(uri)
        if not handler:
            raise MCPError(-32603, f"No handler for resource: {uri}")

        content = handler()
        return {
            "contents": [{
                "uri": uri,
                "mimeType": "text/plain",
                "text": content
            }]
        }

    def _handle_prompts_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle prompts/list request."""
        return {"prompts": [p.to_mcp_dict() for p in self.prompts]}

    def _handle_prompts_get(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle prompts/get request."""
        name = params.get("name")
        if not name:
            raise MCPError(-32602, "Missing required parameter: name")

        prompt_names = [p.name for p in self.prompts]
        if name not in prompt_names:
            raise MCPError(-32002, f"Prompt not found: {name}")

        handler = self._prompt_handlers.get(name)
        if not handler:
            raise MCPError(-32603, f"No handler for prompt: {name}")

        arguments = params.get("arguments", {})
        messages = handler(arguments)
        return {"messages": messages}

    @staticmethod
    def _error_response(msg_id: Any, code: int, message: str) -> str:
        """Build a JSON-RPC error response."""
        return json.dumps({
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {"code": code, "message": message}
        })


class MCPError(Exception):
    """MCP protocol error with JSON-RPC error code."""

    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


# ---------------------------------------------------------------------------
# A2A Client Module
# ---------------------------------------------------------------------------

class A2AClientModule:
    """
    A2A (Agent-to-Agent) client for discovering and communicating with
    external AI agents that implement the A2A protocol.

    Supports:
    - Agent card discovery via /.well-known/agent.json
    - Task submission and status polling
    - Capability negotiation
    """

    def __init__(self, timeout: int = 30,
                 logger: Optional[logging.Logger] = None):
        """
        Initialize A2A client.

        Args:
            timeout: HTTP request timeout in seconds
            logger: Optional logger instance
        """
        self.timeout = timeout
        self.logger = logger or logging.getLogger("mcpbridge.a2a_client")
        self._discovered_agents: Dict[str, AgentCard] = {}

    def discover_agent(self, base_url: str) -> Optional[AgentCard]:
        """
        Discover an agent by fetching its well-known card.

        Args:
            base_url: Base URL of the agent (e.g., http://agent.example.com)

        Returns:
            AgentCard if discovery succeeded, None otherwise
        """
        url = base_url.rstrip("/") + A2A_AGENT_CARD_PATH
        try:
            req = urllib.request.Request(
                url,
                headers={"Accept": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
                card = AgentCard.from_dict(data)
                self._discovered_agents[card.name] = card
                self.logger.info("[A2A] Discovered agent: %s at %s", card.name, base_url)
                return card
        except urllib.error.URLError as exc:
            self.logger.warning("[A2A] Discovery failed for %s: %s", base_url, exc)
            return None
        except (json.JSONDecodeError, KeyError) as exc:
            self.logger.warning("[A2A] Invalid agent card from %s: %s", base_url, exc)
            return None

    def delegate_task(self, agent_url: str, message: str,
                      metadata: Optional[Dict[str, Any]] = None) -> A2ATask:
        """
        Delegate a task to an external A2A agent.

        Sends a task creation request to the agent's /tasks endpoint.
        Returns immediately with PENDING status; use poll_task() to check
        completion.

        Args:
            agent_url: Base URL of the target agent
            message: Task message / instruction
            metadata: Optional task metadata

        Returns:
            A2ATask with initial PENDING status
        """
        task_id = str(uuid.uuid4())
        task = A2ATask(
            task_id=task_id,
            agent_name=agent_url,
            message=message,
            metadata=metadata or {}
        )

        payload = json.dumps({
            "id": task_id,
            "message": {
                "role": "user",
                "parts": [{"type": "text", "text": message}]
            },
            "metadata": metadata or {}
        }).encode("utf-8")

        url = agent_url.rstrip("/") + "/tasks"
        try:
            req = urllib.request.Request(
                url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                resp_data = json.loads(response.read().decode("utf-8"))
                task.task_id = resp_data.get("id", task_id)
                task.status = resp_data.get("status", {}).get("state", STATUS_PENDING)
                self.logger.info("[A2A] Task %s submitted to %s", task.task_id, agent_url)
        except urllib.error.URLError as exc:
            task.status = STATUS_FAILED
            task.error = str(exc)
            self.logger.error("[A2A] Task submission failed: %s", exc)

        return task

    def poll_task(self, agent_url: str, task_id: str) -> A2ATask:
        """
        Poll the status of a delegated task.

        Args:
            agent_url: Base URL of the agent that owns the task
            task_id: Task identifier from delegate_task()

        Returns:
            Updated A2ATask with current status
        """
        url = f"{agent_url.rstrip('/')}/tasks/{task_id}"
        task = A2ATask(task_id=task_id, agent_name=agent_url, message="")
        try:
            req = urllib.request.Request(
                url,
                headers={"Accept": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
                task.status = data.get("status", {}).get("state", STATUS_PENDING)
                artifacts = data.get("artifacts", [])
                if artifacts:
                    parts = artifacts[0].get("parts", [])
                    text_parts = [p.get("text", "") for p in parts if p.get("type") == "text"]
                    task.result = "\n".join(text_parts)
        except urllib.error.URLError as exc:
            task.status = STATUS_FAILED
            task.error = str(exc)
            self.logger.error("[A2A] Task poll failed: %s", exc)
        return task

    def get_discovered_agents(self) -> List[AgentCard]:
        """
        Return list of all previously discovered agents.

        Returns:
            List of AgentCard entries from discovery sessions
        """
        return list(self._discovered_agents.values())


# ---------------------------------------------------------------------------
# MCP HTTP Server Adapter
# ---------------------------------------------------------------------------

class MCPHTTPRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for MCP JSON-RPC over HTTP transport."""

    protocol_handler: Optional[MCPProtocol] = None

    def log_message(self, format_str: str, *args: Any) -> None:
        """Suppress default HTTP server logging."""
        pass

    def do_POST(self) -> None:
        """Handle POST requests (MCP JSON-RPC messages)."""
        if self.path != "/mcp":
            self.send_error(404, "Not Found")
            return

        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8")
        except Exception:
            self.send_error(400, "Bad Request")
            return

        handler = self.__class__.protocol_handler
        if not handler:
            self.send_error(500, "Protocol handler not initialized")
            return

        response = handler.handle_request(body)
        if response is None:
            self.send_response(204)
            self.end_headers()
            return

        response_bytes = response.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response_bytes)))
        self.end_headers()
        self.wfile.write(response_bytes)

    def do_GET(self) -> None:
        """Handle GET requests (agent card, health check)."""
        if self.path == "/health":
            body = json.dumps({"status": "ok", "service": "MCPBridge"}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_error(404, "Not Found")


class A2AHTTPRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for A2A protocol endpoints."""

    registry: Optional[CapabilityRegistry] = None
    logger: Optional[logging.Logger] = None

    def log_message(self, format_str: str, *args: Any) -> None:
        """Suppress default HTTP server logging."""
        pass

    def _send_json(self, status: int, data: Dict[str, Any]) -> None:
        """Helper to send JSON response."""
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        """Handle A2A GET requests."""
        reg = self.__class__.registry
        if reg is None:
            self._send_json(500, {"error": "Registry not initialized"})
            return

        # Well-known agent discovery
        if self.path == A2A_AGENT_CARD_PATH:
            agents = reg.list_agents()
            if agents:
                self._send_json(200, agents[0].to_dict())
            else:
                self._send_json(404, {"error": "No agents registered"})
            return

        # Agent-specific card
        if self.path.startswith("/agents/"):
            agent_name = self.path.split("/agents/")[-1].upper()
            card = reg.get_agent(agent_name)
            if card:
                self._send_json(200, card.to_dict())
            else:
                self._send_json(404, {"error": f"Agent not found: {agent_name}"})
            return

        # Task status
        if self.path.startswith("/tasks/"):
            task_id = self.path.split("/tasks/")[-1]
            task = reg.get_task(task_id)
            if task:
                self._send_json(200, task.to_dict())
            else:
                self._send_json(404, {"error": f"Task not found: {task_id}"})
            return

        # All registered agents
        if self.path == "/agents":
            agents = reg.list_agents()
            self._send_json(200, {"agents": [a.to_dict() for a in agents]})
            return

        self._send_json(404, {"error": "Not found"})

    def do_POST(self) -> None:
        """Handle A2A POST requests (task submission)."""
        reg = self.__class__.registry
        log = self.__class__.logger or logging.getLogger("mcpbridge.a2a_server")

        if not self.path.startswith("/tasks"):
            self._send_json(404, {"error": "Not found"})
            return

        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception as exc:
            self._send_json(400, {"error": f"Bad request: {exc}"})
            return

        task_id = body.get("id", str(uuid.uuid4()))
        message_parts = body.get("message", {}).get("parts", [])
        text = " ".join(p.get("text", "") for p in message_parts if p.get("type") == "text")

        task = A2ATask(
            task_id=task_id,
            agent_name="MCPBridge",
            message=text,
            status=STATUS_PENDING,
            metadata=body.get("metadata", {})
        )

        if reg:
            reg.log_task(task)

        log.info("[A2A] Received task %s: %s", task_id, text[:80])
        self._send_json(200, task.to_dict())


# ---------------------------------------------------------------------------
# Protocol Bridge (Main Orchestrator)
# ---------------------------------------------------------------------------

class ProtocolBridge:
    """
    Main orchestrator for MCPBridge.

    Manages the lifecycle of MCP and A2A servers, coordinates agent
    registration, and provides the unified interface for Team Brain
    agents to interact with the Internet of Agents.
    """

    def __init__(self, db_path: Path = DEFAULT_DB_PATH,
                 mcp_port: int = DEFAULT_MCP_PORT,
                 a2a_port: int = DEFAULT_A2A_PORT,
                 log_path: Optional[Path] = DEFAULT_LOG_PATH,
                 verbose: bool = False):
        """
        Initialize the Protocol Bridge.

        Args:
            db_path: Path to capability registry database
            mcp_port: Port for MCP HTTP server
            a2a_port: Port for A2A HTTP server
            log_path: Path for log output
            verbose: Enable debug logging
        """
        self.mcp_port = mcp_port
        self.a2a_port = a2a_port
        self.logger = setup_logging(log_path, verbose)
        self.registry = CapabilityRegistry(db_path)
        self.a2a_client = A2AClientModule(logger=self.logger)
        self._mcp_servers: Dict[str, MCPProtocol] = {}
        self._mcp_http_server: Optional[HTTPServer] = None
        self._a2a_http_server: Optional[HTTPServer] = None
        self._running = False

    def register_bch_agent(self, agent_name: str, description: str,
                           tools: Optional[List[MCPTool]] = None,
                           resources: Optional[List[MCPResource]] = None,
                           prompts: Optional[List[MCPPrompt]] = None,
                           skills: Optional[List[Dict[str, Any]]] = None) -> AgentCard:
        """
        Register a BCH agent with both MCP and A2A protocols.

        Creates an MCP server adapter and A2A agent card for the agent,
        making it discoverable and accessible from external systems.

        Args:
            agent_name: BCH agent identifier (e.g., ATLAS, FORGE)
            description: Agent role and capabilities description
            tools: MCP tools to expose for this agent
            resources: MCP resources to expose
            prompts: MCP prompt templates to expose
            skills: A2A skill definitions

        Returns:
            Generated AgentCard for the agent
        """
        # Create MCP protocol handler
        mcp_proto = MCPProtocol(
            server_name=f"BCH-{agent_name}",
            server_version="1.0.0",
            tools=tools or [],
            resources=resources or [],
            prompts=prompts or []
        )
        self._mcp_servers[agent_name] = mcp_proto

        # Create A2A agent card
        host = "localhost"
        card = AgentCard.for_bch_agent(
            agent_name=agent_name,
            agent_description=description,
            host=host,
            port=self.a2a_port,
            skills=skills
        )

        # Store in registry
        self.registry.register_agent(card)
        for tool in (tools or []):
            self.registry.register_tool(agent_name, tool)

        self.logger.info("[Bridge] Registered BCH agent: %s", agent_name)
        return card

    def get_mcp_handler(self, agent_name: str) -> Optional[MCPProtocol]:
        """
        Get the MCP protocol handler for a registered agent.

        Args:
            agent_name: BCH agent name

        Returns:
            MCPProtocol handler, or None if not registered
        """
        return self._mcp_servers.get(agent_name)

    def start_servers(self) -> None:
        """
        Start MCP and A2A HTTP servers in background threads.

        Servers run until stop_servers() is called. Logs startup
        information for each server.
        """
        self._running = True

        # Start MCP server
        MCPHTTPRequestHandler.protocol_handler = (
            list(self._mcp_servers.values())[0]
            if self._mcp_servers else None
        )
        self._mcp_http_server = HTTPServer(("0.0.0.0", self.mcp_port),
                                           MCPHTTPRequestHandler)
        mcp_thread = threading.Thread(
            target=self._mcp_http_server.serve_forever,
            daemon=True,
            name="mcp-server"
        )
        mcp_thread.start()
        self.logger.info("[Bridge] MCP server started on port %d", self.mcp_port)

        # Start A2A server
        A2AHTTPRequestHandler.registry = self.registry
        A2AHTTPRequestHandler.logger = self.logger
        self._a2a_http_server = HTTPServer(("0.0.0.0", self.a2a_port),
                                           A2AHTTPRequestHandler)
        a2a_thread = threading.Thread(
            target=self._a2a_http_server.serve_forever,
            daemon=True,
            name="a2a-server"
        )
        a2a_thread.start()
        self.logger.info("[Bridge] A2A server started on port %d", self.a2a_port)

    def stop_servers(self) -> None:
        """Stop all running HTTP servers gracefully."""
        self._running = False
        if self._mcp_http_server:
            self._mcp_http_server.shutdown()
            self.logger.info("[Bridge] MCP server stopped")
        if self._a2a_http_server:
            self._a2a_http_server.shutdown()
            self.logger.info("[Bridge] A2A server stopped")

    def discover_external_agent(self, base_url: str) -> Optional[AgentCard]:
        """
        Discover and register an external A2A agent.

        Args:
            base_url: Base URL of the external agent

        Returns:
            AgentCard if discovery succeeded, None otherwise
        """
        card = self.a2a_client.discover_agent(base_url)
        if card:
            self.registry.register_agent(card)
            self.logger.info("[Bridge] External agent discovered and registered: %s", card.name)
        return card

    def delegate_to_external(self, agent_url: str,
                              message: str) -> A2ATask:
        """
        Delegate a task to an external A2A agent.

        Args:
            agent_url: Target agent URL
            message: Task instruction

        Returns:
            A2ATask representing the delegated work
        """
        task = self.a2a_client.delegate_task(agent_url, message)
        self.registry.log_task(task)
        return task

    def status(self) -> Dict[str, Any]:
        """
        Get bridge status summary.

        Returns:
            Dict with counts of registered agents, tools, tasks, server states
        """
        agents = self.registry.list_agents()
        tasks = self.registry.list_tasks(limit=10)

        return {
            "bridge_version": VERSION,
            "mcp_port": self.mcp_port,
            "a2a_port": self.a2a_port,
            "registered_agents": len(agents),
            "agent_names": [a.name for a in agents],
            "mcp_servers": list(self._mcp_servers.keys()),
            "recent_tasks": len(tasks),
            "servers_running": self._running,
            "database": str(self.registry.db_path)
        }


# ---------------------------------------------------------------------------
# Agent Card Generator CLI Helper
# ---------------------------------------------------------------------------

class AgentCardGenerator:
    """
    Auto-generates A2A Agent Cards for all registered BCH agents.

    Provides a quick way to create properly-formatted agent cards
    for publishing to the A2A network.
    """

    BCH_AGENTS = {
        "ATLAS": {
            "description": (
                "Implementation Lead and Quality Assurance Expert. "
                "Builds production-quality tools following Holy Grail Protocol. "
                "Specializes in Python development, testing, and Team Brain tooling."
            ),
            "skills": [
                {
                    "id": "atlas_build",
                    "name": "Build Tool",
                    "description": "Build a Python tool following Holy Grail Protocol",
                    "inputModes": ["text/plain"],
                    "outputModes": ["text/plain", "application/json"]
                },
                {
                    "id": "atlas_test",
                    "name": "Test Code",
                    "description": "Write and run comprehensive test suite",
                    "inputModes": ["text/plain"],
                    "outputModes": ["text/plain"]
                }
            ]
        },
        "FORGE": {
            "description": (
                "Orchestrator #1 and Reviewer. Plans architecture, reviews code, "
                "writes specifications, and coordinates Team Brain operations."
            ),
            "skills": [
                {
                    "id": "forge_review",
                    "name": "Code Review",
                    "description": "Review code and provide architectural guidance",
                    "inputModes": ["text/plain"],
                    "outputModes": ["text/plain"]
                },
                {
                    "id": "forge_spec",
                    "name": "Write Spec",
                    "description": "Write technical specification for a new tool",
                    "inputModes": ["text/plain"],
                    "outputModes": ["text/plain", "text/markdown"]
                }
            ]
        },
        "CLIO": {
            "description": (
                "CLI Agent and Tool Champion. Linux/Ubuntu specialist, "
                "manages Trophy Room, and maintains tool catalog."
            ),
            "skills": [
                {
                    "id": "clio_linux",
                    "name": "Linux Operations",
                    "description": "Execute Linux/shell operations and automation",
                    "inputModes": ["text/plain"],
                    "outputModes": ["text/plain"]
                }
            ]
        },
        "NEXUS": {
            "description": (
                "VS Code Architect and multi-platform specialist. "
                "Handles cross-platform development and GitHub integration."
            ),
            "skills": [
                {
                    "id": "nexus_arch",
                    "name": "Architecture Design",
                    "description": "Design multi-platform system architecture",
                    "inputModes": ["text/plain"],
                    "outputModes": ["text/plain", "text/markdown"]
                }
            ]
        },
        "BOLT": {
            "description": (
                "Free Executor using Cline + Grok. Handles repetitive tasks "
                "and bulk operations without API cost."
            ),
            "skills": [
                {
                    "id": "bolt_execute",
                    "name": "Execute Task",
                    "description": "Execute routine tasks efficiently",
                    "inputModes": ["text/plain"],
                    "outputModes": ["text/plain"]
                }
            ]
        }
    }

    @classmethod
    def generate_all(cls, host: str = "localhost",
                     port: int = DEFAULT_A2A_PORT) -> List[AgentCard]:
        """
        Generate agent cards for all standard BCH agents.

        Args:
            host: Host to embed in agent card URLs
            port: Port to embed in agent card URLs

        Returns:
            List of generated AgentCard objects
        """
        cards = []
        for name, config in cls.BCH_AGENTS.items():
            card = AgentCard.for_bch_agent(
                agent_name=name,
                agent_description=config["description"],
                host=host,
                port=port,
                skills=config["skills"]
            )
            cards.append(card)
        return cards

    @classmethod
    def generate_for_agent(cls, agent_name: str,
                           host: str = "localhost",
                           port: int = DEFAULT_A2A_PORT) -> Optional[AgentCard]:
        """
        Generate agent card for a specific BCH agent.

        Args:
            agent_name: Agent name (ATLAS, FORGE, CLIO, NEXUS, BOLT)
            host: Host to embed in card URL
            port: Port to embed in card URL

        Returns:
            AgentCard if agent recognized, None otherwise
        """
        config = cls.BCH_AGENTS.get(agent_name.upper())
        if not config:
            return None
        return AgentCard.for_bch_agent(
            agent_name=agent_name.upper(),
            agent_description=config["description"],
            host=host,
            port=port,
            skills=config["skills"]
        )


# ---------------------------------------------------------------------------
# MCP Stdio Transport (for local agent integration)
# ---------------------------------------------------------------------------

class MCPStdioAdapter:
    """
    MCP transport over stdin/stdout for local process integration.

    Enables a BCH agent to act as an MCP server by reading JSON-RPC
    requests from stdin and writing responses to stdout. This is the
    standard MCP transport for local tool use by Claude Desktop and
    similar MCP clients.
    """

    def __init__(self, protocol: MCPProtocol,
                 logger: Optional[logging.Logger] = None):
        """
        Initialize stdio adapter.

        Args:
            protocol: MCPProtocol handler to delegate to
            logger: Optional logger instance
        """
        self.protocol = protocol
        self.logger = logger or logging.getLogger("mcpbridge.stdio")

    def run(self) -> None:
        """
        Run the stdio MCP server loop.

        Reads newline-delimited JSON from stdin, processes each message,
        and writes responses to stdout. Exits on EOF.
        """
        self.logger.info("[Stdio] MCP stdio server started for: %s",
                         self.protocol.server_name)
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            response = self.protocol.handle_request(line)
            if response is not None:
                print(response, flush=True)

    def process_message(self, raw_message: str) -> Optional[str]:
        """
        Process a single MCP message (for testing/embedding).

        Args:
            raw_message: Raw JSON-RPC message string

        Returns:
            Response JSON string, or None for notifications
        """
        return self.protocol.handle_request(raw_message)


# ---------------------------------------------------------------------------
# CLI Interface
# ---------------------------------------------------------------------------

def cmd_status(args: argparse.Namespace) -> int:
    """Show bridge status."""
    bridge = ProtocolBridge(
        db_path=Path(args.db),
        mcp_port=args.mcp_port,
        a2a_port=args.a2a_port,
        log_path=None
    )
    status = bridge.status()
    print("\n" + "=" * 60)
    print("  MCPBridge Status")
    print("=" * 60)
    print(f"  Version:          {status['bridge_version']}")
    print(f"  MCP Port:         {status['mcp_port']}")
    print(f"  A2A Port:         {status['a2a_port']}")
    print(f"  Registered Agents:{status['registered_agents']}")
    if status["agent_names"]:
        for name in status["agent_names"]:
            print(f"    - {name}")
    print(f"  Recent Tasks:     {status['recent_tasks']}")
    print(f"  Database:         {status['database']}")
    print("=" * 60 + "\n")
    return 0


def cmd_register(args: argparse.Namespace) -> int:
    """Register BCH agents."""
    bridge = ProtocolBridge(
        db_path=Path(args.db),
        mcp_port=args.mcp_port,
        a2a_port=args.a2a_port,
        log_path=None
    )

    if args.all:
        cards = AgentCardGenerator.generate_all(
            host=args.host, port=args.a2a_port
        )
        for card in cards:
            bridge.registry.register_agent(card)
            print(f"[OK] Registered: {card.name}")
    elif args.agent:
        card = AgentCardGenerator.generate_for_agent(
            args.agent, host=args.host, port=args.a2a_port
        )
        if card:
            bridge.registry.register_agent(card)
            print(f"[OK] Registered: {card.name}")
        else:
            print(f"[X] Unknown agent: {args.agent}")
            return 1
    else:
        print("[!] Specify --agent NAME or --all")
        return 1

    return 0


def cmd_list(args: argparse.Namespace) -> int:
    """List registered agents."""
    bridge = ProtocolBridge(
        db_path=Path(args.db),
        mcp_port=args.mcp_port,
        a2a_port=args.a2a_port,
        log_path=None
    )
    agents = bridge.registry.list_agents()
    if not agents:
        print("[!] No agents registered. Run: mcpbridge register --all")
        return 0

    print(f"\n{'Name':<20} {'URL':<50} {'Skills'}")
    print("-" * 90)
    for agent in agents:
        skill_names = ", ".join(s.get("id", "") for s in agent.skills[:2])
        print(f"{agent.name:<20} {agent.url:<50} {skill_names}")
    print(f"\nTotal: {len(agents)} agents\n")
    return 0


def cmd_discover(args: argparse.Namespace) -> int:
    """Discover an external A2A agent."""
    bridge = ProtocolBridge(
        db_path=Path(args.db),
        mcp_port=args.mcp_port,
        a2a_port=args.a2a_port,
        log_path=None
    )
    print(f"[...] Discovering agent at: {args.url}")
    card = bridge.discover_external_agent(args.url)
    if card:
        print(f"[OK] Discovered: {card.name}")
        print(f"     Description: {card.description[:80]}")
        print(f"     URL:         {card.url}")
        print(f"     Skills:      {len(card.skills)}")
        return 0
    else:
        print(f"[X] Discovery failed for: {args.url}")
        return 1


def cmd_card(args: argparse.Namespace) -> int:
    """Show agent card as JSON."""
    bridge = ProtocolBridge(
        db_path=Path(args.db),
        mcp_port=args.mcp_port,
        a2a_port=args.a2a_port,
        log_path=None
    )
    card = bridge.registry.get_agent(args.agent.upper())
    if not card:
        # Try generating from built-in
        card = AgentCardGenerator.generate_for_agent(
            args.agent, host=args.host, port=args.a2a_port
        )
    if card:
        print(json.dumps(card.to_dict(), indent=2))
        return 0
    else:
        print(f"[X] Agent not found: {args.agent}")
        return 1


def cmd_delegate(args: argparse.Namespace) -> int:
    """Delegate a task to an external agent."""
    bridge = ProtocolBridge(
        db_path=Path(args.db),
        mcp_port=args.mcp_port,
        a2a_port=args.a2a_port,
        log_path=None
    )
    print(f"[...] Delegating task to: {args.url}")
    task = bridge.delegate_to_external(args.url, args.message)
    print(f"[OK] Task ID:  {task.task_id}")
    print(f"     Status:   {task.status}")
    if task.error:
        print(f"     Error:    {task.error}")
    return 0 if task.status != STATUS_FAILED else 1


def cmd_serve(args: argparse.Namespace) -> int:
    """Start MCP and A2A servers."""
    bridge = ProtocolBridge(
        db_path=Path(args.db),
        mcp_port=args.mcp_port,
        a2a_port=args.a2a_port,
        log_path=Path(args.log) if args.log else DEFAULT_LOG_PATH,
        verbose=args.verbose
    )

    # Auto-register all agents if none registered
    if not bridge.registry.list_agents():
        cards = AgentCardGenerator.generate_all(
            host=args.host, port=args.a2a_port
        )
        for card in cards:
            bridge.registry.register_agent(card)
        bridge.logger.info("[Serve] Auto-registered %d BCH agents", len(cards))

    bridge.start_servers()
    print(f"[OK] MCPBridge running")
    print(f"     MCP server:  http://localhost:{args.mcp_port}/mcp")
    print(f"     A2A server:  http://localhost:{args.a2a_port}")
    print(f"     Agent cards: http://localhost:{args.a2a_port}/.well-known/agent.json")
    print(f"     Press Ctrl+C to stop")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[...] Shutting down...")
        bridge.stop_servers()
        print("[OK] Stopped")
    return 0


def cmd_tasks(args: argparse.Namespace) -> int:
    """List recent tasks."""
    bridge = ProtocolBridge(
        db_path=Path(args.db),
        mcp_port=args.mcp_port,
        a2a_port=args.a2a_port,
        log_path=None
    )
    tasks = bridge.registry.list_tasks(
        agent_name=args.agent if hasattr(args, "agent") and args.agent else None,
        limit=args.limit if hasattr(args, "limit") else 20
    )
    if not tasks:
        print("[!] No tasks found")
        return 0

    print(f"\n{'Task ID':<38} {'Agent':<20} {'Status':<12} {'Message'}")
    print("-" * 100)
    for task in tasks:
        msg = task.message[:35] + "..." if len(task.message) > 35 else task.message
        print(f"{task.task_id:<38} {task.agent_name:<20} {task.status:<12} {msg}")
    print(f"\nShowing {len(tasks)} tasks\n")
    return 0


def main() -> int:
    """CLI entry point for MCPBridge."""
    # Fix Windows console encoding
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except AttributeError:
            pass

    parser = argparse.ArgumentParser(
        prog="mcpbridge",
        description="MCPBridge v1.0 - MCP/A2A Protocol Interoperability for BCH",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  status    Show bridge status and registered agents
  register  Register BCH agents (--all or --agent NAME)
  list      List all registered agents
  discover  Discover an external A2A agent
  card      Show agent card JSON
  delegate  Delegate a task to an external agent
  serve     Start MCP and A2A servers
  tasks     List recent tasks

Examples:
  mcpbridge status
  mcpbridge register --all
  mcpbridge list
  mcpbridge card --agent ATLAS
  mcpbridge serve --mcp-port 8765 --a2a-port 8766
  mcpbridge discover --url http://external-agent.example.com
  mcpbridge delegate --url http://agent.example.com --message "Analyze this code"

GitHub: https://github.com/DonkRonk17/MCPBridge
        """
    )

    parser.add_argument("--version", action="version",
                        version=f"MCPBridge v{VERSION}")

    # Global options
    global_opts = argparse.ArgumentParser(add_help=False)
    global_opts.add_argument("--db", default=str(DEFAULT_DB_PATH),
                              help="Path to registry database")
    global_opts.add_argument("--mcp-port", type=int, default=DEFAULT_MCP_PORT,
                              dest="mcp_port", help="MCP server port")
    global_opts.add_argument("--a2a-port", type=int, default=DEFAULT_A2A_PORT,
                              dest="a2a_port", help="A2A server port")
    global_opts.add_argument("--host", default="localhost",
                              help="Host for agent card URLs")
    global_opts.add_argument("--verbose", "-v", action="store_true",
                              help="Enable debug logging")

    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")

    # status
    subparsers.add_parser("status", parents=[global_opts],
                          help="Show bridge status")

    # register
    p_reg = subparsers.add_parser("register", parents=[global_opts],
                                   help="Register BCH agents")
    p_reg.add_argument("--all", action="store_true",
                       help="Register all standard BCH agents")
    p_reg.add_argument("--agent", metavar="NAME",
                       help="Register a specific agent (ATLAS, FORGE, etc.)")

    # list
    subparsers.add_parser("list", parents=[global_opts],
                          help="List registered agents")

    # discover
    p_disc = subparsers.add_parser("discover", parents=[global_opts],
                                    help="Discover external A2A agent")
    p_disc.add_argument("--url", required=True,
                        help="Base URL of external agent")

    # card
    p_card = subparsers.add_parser("card", parents=[global_opts],
                                    help="Show agent card JSON")
    p_card.add_argument("--agent", required=True, metavar="NAME",
                        help="Agent name (ATLAS, FORGE, CLIO, NEXUS, BOLT)")

    # delegate
    p_del = subparsers.add_parser("delegate", parents=[global_opts],
                                   help="Delegate task to external agent")
    p_del.add_argument("--url", required=True, help="Target agent URL")
    p_del.add_argument("--message", required=True, help="Task message")

    # serve
    p_serve = subparsers.add_parser("serve", parents=[global_opts],
                                     help="Start MCP and A2A servers")
    p_serve.add_argument("--log", default=str(DEFAULT_LOG_PATH),
                         help="Log file path")

    # tasks
    p_tasks = subparsers.add_parser("tasks", parents=[global_opts],
                                     help="List recent tasks")
    p_tasks.add_argument("--agent", metavar="NAME",
                         help="Filter by agent name")
    p_tasks.add_argument("--limit", type=int, default=20,
                         help="Max tasks to show")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    command_map = {
        "status": cmd_status,
        "register": cmd_register,
        "list": cmd_list,
        "discover": cmd_discover,
        "card": cmd_card,
        "delegate": cmd_delegate,
        "serve": cmd_serve,
        "tasks": cmd_tasks,
    }

    handler = command_map.get(args.command)
    if not handler:
        print(f"[X] Unknown command: {args.command}")
        return 1

    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
