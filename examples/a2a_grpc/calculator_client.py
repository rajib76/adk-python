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

"""Example gRPC client connecting to a remote calculator agent.

This example demonstrates how to:
1. Create a RemoteA2aGrpcAgent to connect to a remote gRPC server
2. Send requests and receive responses via gRPC
3. Use the remote agent like any other ADK agent

Prerequisites:
    Start the calculator server first:
    python examples/a2a_grpc/calculator_server.py

Usage:
    python examples/a2a_grpc/calculator_client.py
"""

import asyncio
import logging

from google.adk.a2a.grpc.client import RemoteA2aGrpcAgent
from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def main():
  """Run the calculator gRPC client."""
  # Create remote agent pointing to gRPC server
  remote_calc = RemoteA2aGrpcAgent(
      name='remote_calculator',
      grpc_endpoint='localhost:50051',
      description='Remote calculator agent via gRPC',
  )
  
  # Create session service
  session_service = InMemorySessionService()
  
  # Create runner
  runner = Runner(
      agent=remote_calc,
      session_service=session_service,
      app_name='calculator_grpc_client'
  )
  
  # Example calculations
  questions = [
      'What is 25 * 4?',
      'Calculate the square root of 144',
      'What is (15 + 27) / 3?',
  ]
  
  logger.info('Connecting to calculator server at localhost:50051...')
  
  from google.genai import types
  
  user_id = 'test_user'
  session_id = 'test_session'
  
  # Ensure session exists
  await session_service.create_session(
      app_name='calculator_grpc_client',
      user_id=user_id,
      session_id=session_id
  )

  try:
    for question in questions:
      logger.info('Question: %s', question)
      
      # Create content object
      content = types.Content(role='user', parts=[types.Part(text=question)])
      
      # Run the agent (returns async generator of events)
      async for event in runner.run_async(
          user_id=user_id,
          session_id=session_id,
          new_message=content
      ):
        # We only care about the final content from the model
        if event.content and event.content.parts:
          # Only print content from the model (ignore echoed user messages)
          if event.content.role == 'model':
            for part in event.content.parts:
              if part.text:
                 logger.info('Answer: %s', part.text)
      
      print('-' * 60)
  
  finally:
    # Cleanup
    await remote_calc.close()
    logger.info('Connection closed')


if __name__ == '__main__':
  asyncio.run(main())
