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

"""gRPC client for communicating with remote A2A agents."""

from __future__ import annotations

import logging
from typing import Any, AsyncGenerator, Optional
import uuid

import grpc
from pydantic import Field, PrivateAttr
from google.adk.agents.base_agent import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events.event import Event
from google.adk.a2a.grpc.generated import a2a_pb2
from google.adk.a2a.grpc.generated import a2a_pb2_grpc
from google.adk.a2a.grpc.converters.proto_to_adk import ProtoToAdkConverter
from google.adk.a2a.grpc.converters.adk_to_proto import AdkToProtoConverter
from google.adk.a2a.experimental import a2a_experimental
from google.genai import types as genai_types

logger = logging.getLogger('google_adk.' + __name__)

DEFAULT_TIMEOUT = 600.0


@a2a_experimental
class RemoteA2aGrpcAgent(BaseAgent):
  """Agent that communicates with remote agents via gRPC A2A protocol.
  
  Similar to RemoteA2aAgent but uses gRPC transport instead of HTTP/JSON-RPC.
  
  Example:
    ```python
    from google.adk.a2a.grpc.client import RemoteA2aGrpcAgent
    from google.adk.runners import Runner
    
    # Connect to remote gRPC agent
    remote_agent = RemoteA2aGrpcAgent(
        name="remote_calculator",
        grpc_endpoint="localhost:50051"
    )
    
    runner = Runner(agent=remote_agent)
    result = runner.run("What is 25 * 4?")
    ```
  """

  # Public fields (Pydantic)
  grpc_endpoint: str = Field(..., description="gRPC server endpoint (e.g., 'localhost:50051')")
  credentials: Optional[grpc.ChannelCredentials] = Field(default=None, description="Optional gRPC channel credentials")
  timeout: float = Field(default=DEFAULT_TIMEOUT, description="gRPC call timeout in seconds")
  
  # Private attributes (not part of Pydantic model)
  _proto_to_adk: ProtoToAdkConverter = PrivateAttr(default_factory=ProtoToAdkConverter)
  _adk_to_proto: AdkToProtoConverter = PrivateAttr(default_factory=AdkToProtoConverter)
  _channel: Optional[grpc.aio.Channel] = PrivateAttr(default=None)
  _stub: Optional[a2a_pb2_grpc.A2AServiceStub] = PrivateAttr(default=None)
  _channel_needs_cleanup: bool = PrivateAttr(default=False)

  def __init__(
      self,
      name: str,
      grpc_endpoint: str,
      *,
      description: str = "",
      credentials: Optional[grpc.ChannelCredentials] = None,
      timeout: float = DEFAULT_TIMEOUT,
      **kwargs: Any,
  ) -> None:
    """Initialize RemoteA2aGrpcAgent.
    
    Args:
      name: Agent name (must be unique identifier).
      grpc_endpoint: gRPC server endpoint (e.g., "localhost:50051").
      description: Agent description.
      credentials: Optional gRPC channel credentials for TLS/SSL.
      timeout: gRPC call timeout in seconds (default: 600).
      **kwargs: Additional arguments passed to BaseAgent.
      
    Raises:
      ValueError: If name or grpc_endpoint is invalid.
    """
    if not name:
      raise ValueError('Agent name cannot be empty')
    if not grpc_endpoint:
      raise ValueError('gRPC endpoint cannot be empty')
    
    super().__init__(
        name=name,
        description=description,
        grpc_endpoint=grpc_endpoint,
        credentials=credentials,
        timeout=timeout,
        **kwargs
    )

  async def _ensure_channel(self) -> grpc.aio.Channel:
    """Ensure gRPC channel is available and properly configured."""
    if not self._channel:
      if self.credentials:
        self._channel = grpc.aio.secure_channel(
            self.grpc_endpoint,
            self.credentials,
        )
      else:
        self._channel = grpc.aio.insecure_channel(self.grpc_endpoint)
      
      self._stub = a2a_pb2_grpc.A2AServiceStub(self._channel)
      self._channel_needs_cleanup = True
      logger.info('Created gRPC channel to %s', self.grpc_endpoint)
    
    return self._channel

  async def _cleanup_channel(self) -> None:
    """Clean up gRPC channel if we created it."""
    if self._channel and self._channel_needs_cleanup:
      await self._channel.close()
      self._channel = None
      self._stub = None
      self._channel_needs_cleanup = False
      logger.info('Closed gRPC channel to %s', self.grpc_endpoint)

  async def _run_async_impl(
      self, ctx: InvocationContext
  ) -> AsyncGenerator[Event, None]:
    """Execute the agent by sending request to remote gRPC server.
    
    Args:
      ctx: Invocation context containing the request.
      
    Yields:
      Events from the remote agent.
    """
    try:
      # Ensure channel is ready
      await self._ensure_channel()
      
      # Convert ADK event to proto message
      proto_message = self._create_proto_message(ctx)
      
      # Create SendMessage request
      request = a2a_pb2.SendMessageRequest()
      request.request.CopyFrom(proto_message)
      
      # Call remote agent (streaming)
      try:
        async for response in self._stub.SendStreamingMessage(
            request,
            timeout=self.timeout,
        ):
          # Convert proto response to ADK event
          if response.HasField('task_status_update'):
            event = self._convert_status_update(response.task_status_update, ctx)
            if event:
              yield event
          
          elif response.HasField('task_artifact_update'):
            event = self._convert_artifact_update(response.task_artifact_update, ctx)
            if event:
              yield event
              
      except grpc.RpcError as e:
        logger.error('gRPC call failed: %s', e, exc_info=True)
        # Yield error event
        yield Event(
            invocation_id=ctx.invocation_id,
            author=self.name,
            error_code=e.code().name,
            error_message=e.details(),
        )
    
    finally:
      # Note: We don't cleanup channel here to allow reuse
      # Cleanup happens in __del__ or explicit close()
      pass

  def _create_proto_message(self, ctx: InvocationContext) -> a2a_pb2.Message:
    """Create proto Message from invocation context."""
    proto_msg = a2a_pb2.Message()
    proto_msg.message_id = str(uuid.uuid4())
    proto_msg.role = a2a_pb2.ROLE_USER
    
    # Convert content parts
    if ctx.user_content and ctx.user_content.parts:
      for part in ctx.user_content.parts:
        proto_part = self._adk_to_proto.convert_part(part)
        if proto_part:
          proto_msg.parts.append(proto_part)
    
    return proto_msg

  def _convert_status_update(
      self,
      status_update: a2a_pb2.TaskStatusUpdateEvent,
      ctx: InvocationContext,
  ) -> Optional[Event]:
    """Convert proto TaskStatusUpdateEvent to ADK Event."""
    if not status_update.status.message or not status_update.status.message.parts:
      return None
    
    # Convert message to event
    event = self._proto_to_adk.convert_message(
        status_update.status.message,
        author=self.name,
        invocation_context=ctx,
    )
    
    return event

  def _convert_artifact_update(
      self,
      artifact_update: a2a_pb2.TaskArtifactUpdateEvent,
      ctx: InvocationContext,
  ) -> Optional[Event]:
    """Convert proto TaskArtifactUpdateEvent to ADK Event."""
    if not artifact_update.artifact or not artifact_update.artifact.parts:
      return None
    
    # Convert artifact parts to GenAI parts
    output_parts = []
    for proto_part in artifact_update.artifact.parts:
      part = self._proto_to_adk.convert_part(proto_part)
      if part:
        output_parts.append(part)
    
    if not output_parts:
      return None
    
    return Event(
        invocation_id=ctx.invocation_id,
        author=self.name,
        content=genai_types.Content(
            role='model',
            parts=output_parts,
        ),
    )

  async def close(self) -> None:
    """Close the gRPC channel and cleanup resources."""
    await self._cleanup_channel()

  def __del__(self):
    """Cleanup on deletion."""
    if self._channel and self._channel_needs_cleanup:
      # Note: Can't use async in __del__, so we just log
      logger.warning(
          'RemoteA2aGrpcAgent deleted without calling close(). '
          'Channel may not be properly closed.'
      )
