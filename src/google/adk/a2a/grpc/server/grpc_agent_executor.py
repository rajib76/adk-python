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

"""gRPC servicer implementation for A2A protocol."""

from __future__ import annotations

from datetime import datetime, timezone
import inspect
import logging
from typing import Awaitable, Callable, Optional
import uuid
import asyncio

from google.adk.a2a.grpc.generated import a2a_pb2
from google.adk.a2a.grpc.generated import a2a_pb2_grpc
from google.adk.a2a.grpc.converters.proto_to_adk import ProtoToAdkConverter
from google.adk.a2a.grpc.converters.adk_to_proto import AdkToProtoConverter
from google.adk.runners import Runner
from google.adk.a2a.experimental import a2a_experimental
from google.protobuf.timestamp_pb2 import Timestamp
import grpc

logger = logging.getLogger('google_adk.' + __name__)


@a2a_experimental
class GrpcAgentExecutor(a2a_pb2_grpc.A2AServiceServicer):
  """gRPC servicer that executes ADK agents for A2A protocol."""

  def __init__(
      self,
      runner: Runner | Callable[..., Runner | Awaitable[Runner]],
  ):
    """Initialize the gRPC agent executor.
    
    Args:
      runner: ADK Runner instance or callable that returns a Runner.
    """
    super().__init__()
    self._runner = runner
    self._proto_to_adk = ProtoToAdkConverter()
    self._adk_to_proto = AdkToProtoConverter()
    self._tasks = {}  # In-memory task storage (task_id -> Task)

  async def _resolve_runner(self) -> Runner:
    """Resolve the runner, handling cases where it's a callable."""
    if isinstance(self._runner, Runner):
      return self._runner
    if callable(self._runner):
      result = self._runner()
      if inspect.iscoroutine(result):
        resolved_runner = await result
      else:
        resolved_runner = result
      self._runner = resolved_runner
      return resolved_runner
    raise TypeError(
        f'Runner must be a Runner instance or callable, got {type(self._runner)}'
    )

  def SendMessage(self, request, context):
    """Handle unary SendMessage RPC.
    
    Args:
      request: SendMessageRequest proto.
      context: gRPC context.
      
    Returns:
      SendMessageResponse proto.
    """
    # Run async handler in event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
      return loop.run_until_complete(self._send_message_async(request, context))
    finally:
      loop.close()

  async def _send_message_async(self, request, context):
    """Async implementation of SendMessage."""
    try:
      # Create task
      task_id = str(uuid.uuid4())
      context_id = request.message.context_id or str(uuid.uuid4())
      
      # Create initial task
      task = a2a_pb2.Task()
      task.id = task_id
      task.context_id = context_id
      
      # Set initial status
      status = a2a_pb2.TaskStatus()
      status.state = a2a_pb2.TASK_STATE_SUBMITTED
      status.message.CopyFrom(request.message)
      timestamp = Timestamp()
      timestamp.GetCurrentTime()
      status.timestamp.CopyFrom(timestamp)
      task.status.CopyFrom(status)
      
      # Store task
      self._tasks[task_id] = task
      
      # Execute agent
      await self._execute_agent(task, request, context)
      
      # Return response
      response = a2a_pb2.SendMessageResponse()
      response.task.CopyFrom(self._tasks[task_id])
      return response
      
    except Exception as e:
      logger.error('Error in SendMessage: %s', e, exc_info=True)
      context.abort(grpc.StatusCode.INTERNAL, str(e))

  def SendStreamingMessage(self, request, context):
    """Handle streaming SendStreamingMessage RPC.
    
    Args:
      request: SendMessageRequest proto.
      context: gRPC context.
      
    Yields:
      StreamResponse protos with task updates.
    """
    # Run async handler in event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
      async_gen = self._send_streaming_message_async(request, context)
      while True:
        try:
          response = loop.run_until_complete(async_gen.__anext__())
          yield response
        except StopAsyncIteration:
          break
    finally:
      loop.close()

  async def _send_streaming_message_async(self, request, context):
    """Async implementation of SendStreamingMessage."""
    try:
      # Create task
      task_id = str(uuid.uuid4())
      context_id = request.message.context_id or str(uuid.uuid4())
      
      # Create initial task
      task = a2a_pb2.Task()
      task.id = task_id
      task.context_id = context_id
      
      # Set initial status
      status = a2a_pb2.TaskStatus()
      status.state = a2a_pb2.TASK_STATE_SUBMITTED
      status.message.CopyFrom(request.message)
      timestamp = Timestamp()
      timestamp.GetCurrentTime()
      status.timestamp.CopyFrom(timestamp)
      task.status.CopyFrom(status)
      
      # Store task
      self._tasks[task_id] = task
      
      # Yield initial status
      response = a2a_pb2.StreamResponse()
      response.task_status_update.task_id = task_id
      response.task_status_update.context_id = context_id
      response.task_status_update.status.CopyFrom(status)
      response.task_status_update.final = False
      yield response
      
      # Execute agent and stream updates
      async for update in self._execute_agent_streaming(task, request, context):
        yield update
        
    except Exception as e:
      logger.error('Error in SendStreamingMessage: %s', e, exc_info=True)
      context.abort(grpc.StatusCode.INTERNAL, str(e))

  async def _execute_agent(self, task, request, grpc_context):
    """Execute the agent for a task (non-streaming)."""
    try:
      runner = await self._resolve_runner()
      
      # Convert proto message to ADK event
      invocation_context = runner._new_invocation_context(
          session=await self._get_or_create_session(runner, request),
          new_message=None,  # Will be set from proto message
          run_config=None,
      )
      
      # Update task status to working
      task.status.state = a2a_pb2.TASK_STATE_WORKING
      timestamp = Timestamp()
      timestamp.GetCurrentTime()
      task.status.timestamp.CopyFrom(timestamp)
      
      # Convert message and run agent
      adk_event = self._proto_to_adk.convert_message(
          request.message,
          author='user',
          invocation_context=invocation_context,
      )
      
      # Run agent (simplified - full implementation would stream events)
      # For now, just mark as completed
      task.status.state = a2a_pb2.TASK_STATE_COMPLETED
      timestamp.GetCurrentTime()
      task.status.timestamp.CopyFrom(timestamp)
      
    except Exception as e:
      logger.error('Error executing agent: %s', e, exc_info=True)
      task.status.state = a2a_pb2.TASK_STATE_FAILED
      error_msg = a2a_pb2.Message()
      error_msg.message_id = str(uuid.uuid4())
      error_msg.role = a2a_pb2.ROLE_AGENT
      error_part = a2a_pb2.Part()
      error_part.text = str(e)
      error_msg.parts.append(error_part)
      task.status.message.CopyFrom(error_msg)

  async def _execute_agent_streaming(self, task, request, grpc_context):
    """Execute the agent for a task (streaming)."""
    try:
      runner = await self._resolve_runner()
      
      # Update to working
      response = a2a_pb2.StreamResponse()
      response.task_status_update.task_id = task.id
      response.task_status_update.context_id = task.context_id
      response.task_status_update.status.state = a2a_pb2.TASK_STATE_WORKING
      timestamp = Timestamp()
      timestamp.GetCurrentTime()
      response.task_status_update.status.timestamp.CopyFrom(timestamp)
      response.task_status_update.final = False
      yield response
      
      # Execute and stream (simplified)
      # Full implementation would stream ADK events
      
      # Final completion
      response = a2a_pb2.StreamResponse()
      response.task_status_update.task_id = task.id
      response.task_status_update.context_id = task.context_id
      response.task_status_update.status.state = a2a_pb2.TASK_STATE_COMPLETED
      timestamp.GetCurrentTime()
      response.task_status_update.status.timestamp.CopyFrom(timestamp)
      response.task_status_update.final = True
      yield response
      
    except Exception as e:
      logger.error('Error in streaming execution: %s', e, exc_info=True)
      # Yield error response
      response = a2a_pb2.StreamResponse()
      response.task_status_update.task_id = task.id
      response.task_status_update.context_id = task.context_id
      response.task_status_update.status.state = a2a_pb2.TASK_STATE_FAILED
      error_msg = a2a_pb2.Message()
      error_msg.message_id = str(uuid.uuid4())
      error_msg.role = a2a_pb2.ROLE_AGENT
      error_part = a2a_pb2.Part()
      error_part.text = str(e)
      error_msg.parts.append(error_part)
      response.task_status_update.status.message.CopyFrom(error_msg)
      response.task_status_update.final = True
      yield response

  def GetTask(self, request, context):
    """Get task by ID."""
    task_id = request.name.split('/')[-1]  # Extract ID from resource name
    if task_id in self._tasks:
      return self._tasks[task_id]
    context.abort(grpc.StatusCode.NOT_FOUND, f'Task {task_id} not found')

  def ListTasks(self, request, context):
    """List all tasks."""
    response = a2a_pb2.ListTasksResponse()
    for task in self._tasks.values():
      response.tasks.append(task)
    return response

  def CancelTask(self, request, context):
    """Cancel a task."""
    task_id = request.name.split('/')[-1]
    if task_id in self._tasks:
      task = self._tasks[task_id]
      task.status.state = a2a_pb2.TASK_STATE_CANCELLED
      timestamp = Timestamp()
      timestamp.GetCurrentTime()
      task.status.timestamp.CopyFrom(timestamp)
      return task
    context.abort(grpc.StatusCode.NOT_FOUND, f'Task {task_id} not found')

  async def _get_or_create_session(self, runner, request):
    """Get or create a session for the request."""
    # Extract session info from metadata
    session_id = str(uuid.uuid4())
    user_id = 'default_user'
    
    session = await runner.session_service.get_session(
        app_name=runner.app_name,
        user_id=user_id,
        session_id=session_id,
    )
    if session is None:
      session = await runner.session_service.create_session(
          app_name=runner.app_name,
          user_id=user_id,
          state={},
          session_id=session_id,
      )
    return session
