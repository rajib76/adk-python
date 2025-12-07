# Pull Request: Add gRPC Transport Support for A2A Protocol

## Summary

This PR adds gRPC transport support to ADK's A2A (Agent-to-Agent) protocol implementation, providing a high-performance alternative to the existing JSON-RPC transport.

## Motivation

The A2A protocol specification includes gRPC as a supported transport protocol. This implementation enables:
- **Higher performance** through HTTP/2 and binary Protocol Buffers
- **Native streaming** for real-time agent responses
- **Type safety** via Protocol Buffer schemas
- **Reduced payload sizes** compared to JSON

## Changes

### Core Implementation (~1,300 lines)

**Server Components** (`src/google/adk/a2a/grpc/server/`)
- `GrpcAgentExecutor` - gRPC servicer implementing A2AService
- Unary RPC: `SendMessage()`
- Streaming RPC: `SendStreamingMessage()`
- Task management: `GetTask()`, `ListTasks()`, `CancelTask()`
- Server helpers: `create_grpc_server()`, `serve()`

**Client Components** (`src/google/adk/a2a/grpc/client/`)
- `RemoteA2aGrpcAgent` - ADK agent for gRPC communication
- Async channel management
- Streaming response handling
- TLS/SSL support

**Converters** (`src/google/adk/a2a/grpc/converters/`)
- `ProtoToAdkConverter` - Protocol Buffers → ADK types
- `AdkToProtoConverter` - ADK types → Protocol Buffers
- Support for all A2A part types

**Protocol Definitions** (`src/google/adk/a2a/grpc/proto/`)
- A2A Protocol Buffer definitions from official spec
- Generated Python gRPC stubs (~2,500 lines)

### Examples & Documentation

**Examples** (`examples/a2a_grpc/`)
- `calculator_server.py` - Working gRPC server example
- `calculator_client.py` - Working gRPC client example
- `README.md` - Usage instructions

**Documentation** (`docs/`)
- `a2a-grpc.md` - Comprehensive gRPC transport guide

### Dependencies

**pyproject.toml**
- Added `a2a-grpc` optional dependency group
- Includes: `grpcio`, `grpcio-tools`, `protobuf`

## Testing

### Manual Testing
- ✅ Server starts and accepts connections
- ✅ Client connects and sends messages
- ✅ Streaming responses work correctly
- ✅ Examples run successfully

### Example Usage
```bash
# Terminal 1
python examples/a2a_grpc/calculator_server.py

# Terminal 2
python examples/a2a_grpc/calculator_client.py
```

## Breaking Changes

None. This is a purely additive feature.

## Compatibility

- **Backward compatible**: Existing JSON-RPC transport unaffected
- **Python**: Requires Python 3.10+
- **Dependencies**: Optional `a2a-grpc` group

## Future Work

Potential enhancements (not included in this PR):
- CLI integration (`adk serve --grpc`)
- Bidirectional streaming support
- gRPC interceptors for logging/metrics
- Integration tests with pytest
- Performance benchmarks vs JSON-RPC

## Checklist

- [x] Code follows ADK style guidelines (`pyink`, `pylint`)
- [x] Type hints added throughout
- [x] Documentation created
- [x] Examples provided
- [x] Marked with `@a2a_experimental` decorator
- [x] No breaking changes
- [ ] Tests added (manual testing completed)

## Files Changed

**Created** (25 files):
- `src/google/adk/a2a/grpc/` - Complete gRPC implementation
- `examples/a2a_grpc/` - Working examples
- `docs/a2a-grpc.md` - Documentation

**Modified** (1 file):
- `pyproject.toml` - Added `a2a-grpc` dependencies

## Related Issues

Implements gRPC transport as specified in the [A2A Protocol](https://github.com/a2aproject/A2A).

## Screenshots

N/A (server/client communication)

## Additional Notes

This implementation follows the official A2A Protocol Buffer specification and reuses existing ADK patterns from the JSON-RPC implementation. The code is marked as experimental (`@a2a_experimental`) to allow for iteration based on user feedback.
