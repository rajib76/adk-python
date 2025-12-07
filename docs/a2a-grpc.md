# gRPC Transport for A2A Protocol

This document describes the gRPC transport implementation for the A2A (Agent-to-Agent) protocol in Google ADK.

## Overview

The A2A protocol supports multiple transport protocols. While ADK previously used JSON-RPC over HTTP, this implementation adds **gRPC** as a high-performance alternative transport option.

### Benefits of gRPC Transport

- **Performance**: HTTP/2 multiplexing, binary Protocol Buffers serialization
- **Streaming**: Native support for server-side streaming responses
- **Type Safety**: Strongly-typed Protocol Buffer schemas
- **Efficiency**: Reduced payload size compared to JSON
- **Standards**: Uses official A2A Protocol Buffer definitions

## Architecture

```
┌─────────────────┐         gRPC          ┌─────────────────┐
│   ADK Agent     │ ◄──────────────────► │  Remote Agent   │
│   (Client)      │   Protocol Buffers   │   (Server)      │
└─────────────────┘                       └─────────────────┘
        │                                         │
        │                                         │
   RemoteA2aGrpcAgent                    GrpcAgentExecutor
        │                                         │
        ▼                                         ▼
   Proto → ADK                               ADK → Proto
    Converters                                Converters
```

## Components

### Server Side

**GrpcAgentExecutor** (`src/google/adk/a2a/grpc/server/grpc_agent_executor.py`)
- Implements the A2A gRPC service (`A2AServiceServicer`)
- Handles unary and streaming RPCs
- Manages task lifecycle and state

**Server Helpers** (`src/google/adk/a2a/grpc/server/grpc_server.py`)
- `create_grpc_server()` - Factory for server creation
- `serve()` - Convenience function for running servers

### Client Side

**RemoteA2aGrpcAgent** (`src/google/adk/a2a/grpc/client/remote_grpc_agent.py`)
- ADK agent that communicates via gRPC
- Manages gRPC channel lifecycle
- Handles streaming responses

### Converters

**ProtoToAdkConverter** (`src/google/adk/a2a/grpc/converters/proto_to_adk.py`)
- Converts Protocol Buffer messages → ADK types
- Handles all A2A part types (text, files, data, function calls)

**AdkToProtoConverter** (`src/google/adk/a2a/grpc/converters/adk_to_proto.py`)
- Converts ADK types → Protocol Buffer messages
- Preserves metadata and long-running tool markers

## Installation

Install ADK with gRPC support:

```bash
pip install google-adk[a2a-grpc]
```

Or for development:

```bash
pip install -e ".[a2a-grpc]"
```

## Usage

### Creating a gRPC Server

```python
from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.a2a.grpc.server import serve

# Create your agent
agent = Agent(
    name="my_agent",
    model="gemini-2.0-flash-exp",
    instruction="You are a helpful assistant."
)

# Create runner
runner = Runner(agent=agent)

# Start gRPC server (blocking)
serve(runner, port=50051)
```

### Connecting to a gRPC Server

```python
from google.adk.a2a.grpc.client import RemoteA2aGrpcAgent
from google.adk.runners import Runner

# Create remote agent
remote_agent = RemoteA2aGrpcAgent(
    name="remote_agent",
    grpc_endpoint="localhost:50051"
)

# Use like any other ADK agent
runner = Runner(agent=remote_agent)
result = await runner.run_async("Hello!")
```

### Secure Connections (TLS)

```python
import grpc

# Server with TLS
credentials = grpc.ssl_server_credentials([
    (private_key, certificate_chain)
])
serve(runner, port=50051, credentials=credentials)

# Client with TLS
credentials = grpc.ssl_channel_credentials(
    root_certificates=ca_cert
)
remote_agent = RemoteA2aGrpcAgent(
    name="remote_agent",
    grpc_endpoint="example.com:50051",
    credentials=credentials
)
```

## Protocol Details

### Supported RPCs

The gRPC implementation supports all A2A protocol operations:

- **SendMessage** - Unary RPC for single request/response
- **SendStreamingMessage** - Server streaming for real-time updates
- **GetTask** - Retrieve task by ID
- **ListTasks** - List all tasks
- **CancelTask** - Cancel a running task

### Message Format

Messages use Protocol Buffers as defined in the [A2A specification](https://github.com/a2aproject/A2A/blob/main/specification/grpc/a2a.proto):

```protobuf
message Message {
  string message_id = 1;
  string context_id = 2;
  string task_id = 3;
  Role role = 4;
  repeated Part parts = 5;
  google.protobuf.Struct metadata = 6;
}
```

### Part Types

All A2A part types are supported:
- **TextPart** - Plain text content
- **FilePart** - Files (URI or bytes)
- **DataPart** - Structured JSON data (function calls, responses, etc.)

## Examples

See `examples/a2a_grpc/` for complete working examples:
- `calculator_server.py` - gRPC server example
- `calculator_client.py` - gRPC client example

## Comparison: gRPC vs JSON-RPC

| Feature | gRPC | JSON-RPC |
|---------|------|----------|
| Protocol | HTTP/2 | HTTP/1.1 |
| Serialization | Protocol Buffers (binary) | JSON (text) |
| Streaming | Native server streaming | Polling required |
| Type Safety | Strong (proto schemas) | Weak (JSON) |
| Payload Size | Smaller | Larger |
| Browser Support | Limited (requires grpc-web) | Full |
| Debugging | Requires tools | Easy (human-readable) |

**When to use gRPC:**
- High-throughput agent communication
- Low-latency requirements
- Server-to-server communication
- Streaming responses needed

**When to use JSON-RPC:**
- Browser-based clients
- Simple debugging requirements
- HTTP/1.1 infrastructure

## Troubleshooting

### Import Errors

If you see `ModuleNotFoundError: No module named 'grpc'`:
```bash
pip install google-adk[a2a-grpc]
```

### Connection Refused

Ensure the server is running:
```bash
python examples/a2a_grpc/calculator_server.py
```

Check the endpoint matches:
```python
RemoteA2aGrpcAgent(grpc_endpoint="localhost:50051")  # Must match server port
```

### SSL/TLS Errors

For development, use insecure channels:
```python
# Server
serve(runner, port=50051)  # No credentials = insecure

# Client
RemoteA2aGrpcAgent(grpc_endpoint="localhost:50051")  # No credentials = insecure
```

## Contributing

This implementation follows ADK coding standards:
- Code style: `pyink` formatter
- Linting: `pylint`
- Type hints: Complete annotations
- Documentation: Google docstring style
- Experimental: `@a2a_experimental` decorator

## References

- [A2A Protocol Specification](https://github.com/a2aproject/A2A)
- [A2A gRPC Proto Definition](https://github.com/a2aproject/A2A/blob/main/specification/grpc/a2a.proto)
- [gRPC Python Documentation](https://grpc.io/docs/languages/python/)
- [Protocol Buffers Guide](https://protobuf.dev/)
