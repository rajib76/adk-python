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

"""Converters from ADK types to A2A Protocol Buffer messages."""

from __future__ import annotations

import base64
import logging
from typing import Optional
from datetime import datetime, timezone
import uuid

from google.adk.a2a.grpc.generated import a2a_pb2
from google.genai import types as genai_types
from google.adk.events.event import Event
from google.adk.agents.invocation_context import InvocationContext
from google.adk.a2a.experimental import a2a_experimental
from google.protobuf import struct_pb2
from google.protobuf.json_format import ParseDict

logger = logging.getLogger('google_adk.' + __name__)


@a2a_experimental
class AdkToProtoConverter:
  """Converts ADK types to A2A Protocol Buffer messages."""

  def convert_part(self, part: genai_types.Part) -> Optional[a2a_pb2.Part]:
    """Convert GenAI Part to proto Part.
    
    Args:
      part: The GenAI Part to convert.
      
    Returns:
      A protocol buffer Part or None if conversion fails.
    """
    try:
      proto_part = a2a_pb2.Part()
      
      # Handle text part
      if part.text:
        proto_part.text = part.text
        
        # Add thought metadata if present
        if part.thought is not None:
          metadata = struct_pb2.Struct()
          metadata['adk:thought'] = part.thought
          proto_part.metadata.CopyFrom(metadata)
        
        return proto_part
      
      # Handle file data (URI)
      if part.file_data:
        file_part = a2a_pb2.FilePart()
        file_part.file_with_uri = part.file_data.file_uri
        file_part.media_type = part.file_data.mime_type
        proto_part.file.CopyFrom(file_part)
        return proto_part
      
      # Handle inline data (bytes)
      if part.inline_data:
        file_part = a2a_pb2.FilePart()
        file_part.file_with_bytes = part.inline_data.data
        file_part.media_type = part.inline_data.mime_type
        proto_part.file.CopyFrom(file_part)
        
        # Add video metadata if present
        if part.video_metadata:
          metadata = struct_pb2.Struct()
          metadata_dict = part.video_metadata.model_dump(by_alias=True, exclude_none=True)
          ParseDict(metadata_dict, metadata)
          proto_part.metadata.CopyFrom(metadata)
        
        return proto_part
      
      # Handle function call
      if part.function_call:
        data_part = a2a_pb2.DataPart()
        func_call_dict = part.function_call.model_dump(by_alias=True, exclude_none=True)
        ParseDict(func_call_dict, data_part.data)
        proto_part.data.CopyFrom(data_part)
        
        # Add metadata to indicate this is a function call
        metadata = struct_pb2.Struct()
        metadata['adk:type'] = 'function_call'
        proto_part.metadata.CopyFrom(metadata)
        
        return proto_part
      
      # Handle function response
      if part.function_response:
        data_part = a2a_pb2.DataPart()
        func_resp_dict = part.function_response.model_dump(by_alias=True, exclude_none=True)
        ParseDict(func_resp_dict, data_part.data)
        proto_part.data.CopyFrom(data_part)
        
        # Add metadata to indicate this is a function response
        metadata = struct_pb2.Struct()
        metadata['adk:type'] = 'function_response'
        proto_part.metadata.CopyFrom(metadata)
        
        return proto_part
      
      # Handle code execution result
      if part.code_execution_result:
        data_part = a2a_pb2.DataPart()
        code_result_dict = part.code_execution_result.model_dump(by_alias=True, exclude_none=True)
        ParseDict(code_result_dict, data_part.data)
        proto_part.data.CopyFrom(data_part)
        
        # Add metadata
        metadata = struct_pb2.Struct()
        metadata['adk:type'] = 'code_execution_result'
        proto_part.metadata.CopyFrom(metadata)
        
        return proto_part
      
      # Handle executable code
      if part.executable_code:
        data_part = a2a_pb2.DataPart()
        exec_code_dict = part.executable_code.model_dump(by_alias=True, exclude_none=True)
        ParseDict(exec_code_dict, data_part.data)
        proto_part.data.CopyFrom(data_part)
        
        # Add metadata
        metadata = struct_pb2.Struct()
        metadata['adk:type'] = 'executable_code'
        proto_part.metadata.CopyFrom(metadata)
        
        return proto_part
      
      logger.warning('Cannot convert unsupported GenAI part: %s', part)
      return None
      
    except Exception as e:
      logger.error('Failed to convert GenAI part to proto: %s', e)
      return None

  def convert_event(
      self,
      event: Event,
      invocation_context: InvocationContext,
      role: a2a_pb2.Role = a2a_pb2.ROLE_AGENT,
  ) -> Optional[a2a_pb2.Message]:
    """Convert ADK Event to proto Message.
    
    Args:
      event: The ADK Event to convert.
      invocation_context: The invocation context.
      role: The role of the message.
      
    Returns:
      A protocol buffer Message or None if event has no content.
    """
    if not event or not event.content or not event.content.parts:
      return None
    
    proto_msg = a2a_pb2.Message()
    proto_msg.message_id = str(uuid.uuid4())
    proto_msg.role = role
    
    for part in event.content.parts:
      proto_part = self.convert_part(part)
      if proto_part:
        # Mark long-running tools
        if event.long_running_tool_ids and part.function_call:
          if part.function_call.id in event.long_running_tool_ids:
            if not proto_part.HasField('metadata'):
              proto_part.metadata.CopyFrom(struct_pb2.Struct())
            proto_part.metadata['adk:is_long_running'] = True
        
        proto_msg.parts.append(proto_part)
    
    # Add context metadata
    if invocation_context:
      metadata = struct_pb2.Struct()
      metadata['adk:app_name'] = invocation_context.app_name
      metadata['adk:user_id'] = invocation_context.user_id
      metadata['adk:session_id'] = invocation_context.session.id
      metadata['adk:invocation_id'] = event.invocation_id
      metadata['adk:author'] = event.author
      proto_msg.metadata.CopyFrom(metadata)
    
    return proto_msg if proto_msg.parts else None

  def convert_task_state(self, state_str: str) -> a2a_pb2.TaskState:
    """Convert string task state to proto TaskState enum.
    
    Args:
      state_str: String representation of task state.
      
    Returns:
      Protocol buffer TaskState enum value.
    """
    state_map = {
        'submitted': a2a_pb2.TASK_STATE_SUBMITTED,
        'working': a2a_pb2.TASK_STATE_WORKING,
        'completed': a2a_pb2.TASK_STATE_COMPLETED,
        'failed': a2a_pb2.TASK_STATE_FAILED,
        'cancelled': a2a_pb2.TASK_STATE_CANCELLED,
        'input_required': a2a_pb2.TASK_STATE_INPUT_REQUIRED,
        'rejected': a2a_pb2.TASK_STATE_REJECTED,
        'auth_required': a2a_pb2.TASK_STATE_AUTH_REQUIRED,
    }
    return state_map.get(state_str.lower(), a2a_pb2.TASK_STATE_UNSPECIFIED)
