# A2A gRPC Examples

This directory contains examples demonstrating how to use gRPC transport with the A2A protocol in ADK.

## Examples

### Calculator Server & Client

A simple example showing bidirectional gRPC communication between ADK agents.

**Server** (`calculator_server.py`):
- Exposes a calculator agent via gRPC on port 50051
- Uses the A2A protocol over gRPC transport
- Handles mathematical calculations

**Client** (`calculator_client.py`):
- Connects to the calculator server via gRPC
- Sends calculation requests
- Receives and displays responses

## Running the Examples

### Prerequisites

Install ADK with gRPC support:
```bash
pip install -e ".[a2a-grpc]"
```

### Start the Server

In one terminal:
```bash
python examples/a2a_grpc/calculator_server.py
```

You should see:
```
Starting calculator gRPC server on port 50051...
Press Ctrl+C to stop
```

### Run the Client

In another terminal:
```bash
python examples/a2a_grpc/calculator_client.py
```

You should see the client send questions and receive answers from the remote calculator agent.

## How It Works

1. **Server Side**:
   - Creates an ADK `Agent` (calculator)
   - Wraps it in a `Runner`
   - Exposes via `serve()` which creates a gRPC server
   - Implements the A2A gRPC service

2. **Client Side**:
   - Creates a `RemoteA2aGrpcAgent` pointing to the server
   - Uses it like any other ADK agent
   - Communication happens via gRPC instead of HTTP

## Key Features Demonstrated

- ✅ gRPC server creation and lifecycle
- ✅ Remote agent communication via gRPC
- ✅ Protocol Buffer message conversion
- ✅ Async streaming responses
- ✅ Proper resource cleanup

## Next Steps

Try modifying the examples:
- Change the agent's instruction or model
- Add more complex calculations
- Implement secure channels with TLS
- Create multi-agent systems with gRPC communication
