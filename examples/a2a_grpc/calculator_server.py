#!/usr/bin/env python3
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

"""Example gRPC server exposing a calculator agent via A2A protocol.

This example demonstrates how to:
1. Create a simple ADK agent (calculator)
2. Expose it via gRPC using the A2A protocol
3. Run a gRPC server that handles A2A requests

Usage:
    python examples/a2a_grpc/calculator_server.py
    
The server will start on port 50051 and wait for gRPC requests.
"""

import logging

from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.adk.a2a.grpc.server import serve

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def main():
  """Run the calculator gRPC server."""
  # Create a simple calculator agent
  calculator = Agent(
      name='calculator',
      model='gemini-2.0-flash-exp',
      instruction="""You are a helpful calculator assistant.
      Perform mathematical calculations accurately and explain your work.
      Always show the calculation steps.""",
  )
  
  # Create session service
  session_service = InMemorySessionService()
  
  # Create runner
  runner = Runner(
      agent=calculator,
      session_service=session_service,
      app_name='calculator_grpc_server'
  )
  
  logger.info('Starting calculator gRPC server on port 50051...')
  logger.info('Press Ctrl+C to stop')
  
  # Start gRPC server (blocking)
  try:
    serve(runner, port=50051)
  except KeyboardInterrupt:
    logger.info('Server stopped by user')


if __name__ == '__main__':
  main()
