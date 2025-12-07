# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""gRPC server creation and lifecycle management."""

from __future__ import annotations

import logging
from concurrent import futures
from typing import Optional

import grpc
from google.adk.runners import Runner
from google.adk.a2a.experimental import a2a_experimental
from google.adk.a2a.grpc.generated import a2a_pb2_grpc
from google.adk.a2a.grpc.server.grpc_agent_executor import GrpcAgentExecutor

logger = logging.getLogger('google_adk.' + __name__)


@a2a_experimental
def create_grpc_server(
    runner: Runner,
    port: int = 50051,
    max_workers: int = 10,
    credentials: Optional[grpc.ServerCredentials] = None,
) -> grpc.Server:
  """Create and configure a gRPC server for A2A protocol.
  
  Args:
    runner: ADK Runner instance to execute agents.
    port: Port number for the server (default: 50051).
    max_workers: Maximum number of worker threads (default: 10).
    credentials: Optional server credentials for TLS/SSL.
    
  Returns:
    Configured gRPC server instance (not started).
    
  Example:
    ```python
    from google.adk.agents import Agent
    from google.adk.runners import Runner
    from google.adk.a2a.grpc.server import create_grpc_server
    
    agent = Agent(name="my_agent", model="gemini-2.0-flash")
    runner = Runner(agent=agent)
    
    server = create_grpc_server(runner, port=50051)
    server.start()
    server.wait_for_termination()
    ```
  """
  # Create thread pool executor
  server = grpc.server(futures.ThreadPoolExecutor(max_workers=max_workers))
  
  # Create and register servicer
  servicer = GrpcAgentExecutor(runner)
  a2a_pb2_grpc.add_A2AServiceServicer_to_server(servicer, server)
  
  # Add port (secure or insecure)
  if credentials:
    server.add_secure_port(f'[::]:{port}', credentials)
    logger.info('gRPC server configured with TLS on port %d', port)
  else:
    server.add_insecure_port(f'[::]:{port}')
    logger.info('gRPC server configured (insecure) on port %d', port)
  
  return server


@a2a_experimental
def serve(
    runner: Runner,
    port: int = 50051,
    max_workers: int = 10,
    credentials: Optional[grpc.ServerCredentials] = None,
) -> None:
  """Create, start, and run a gRPC server (blocking).
  
  This is a convenience function that creates a server and blocks
  until termination (e.g., Ctrl+C).
  
  Args:
    runner: ADK Runner instance to execute agents.
    port: Port number for the server (default: 50051).
    max_workers: Maximum number of worker threads (default: 10).
    credentials: Optional server credentials for TLS/SSL.
    
  Example:
    ```python
    from google.adk.agents import Agent
    from google.adk.runners import Runner
    from google.adk.a2a.grpc.server import serve
    
    agent = Agent(name="my_agent", model="gemini-2.0-flash")
    runner = Runner(agent=agent)
    
    # This will block until Ctrl+C
    serve(runner, port=50051)
    ```
  """
  server = create_grpc_server(runner, port, max_workers, credentials)
  server.start()
  logger.info('gRPC server started, listening on port %d', port)
  try:
    server.wait_for_termination()
  except KeyboardInterrupt:
    logger.info('gRPC server shutting down...')
    server.stop(grace=5)
