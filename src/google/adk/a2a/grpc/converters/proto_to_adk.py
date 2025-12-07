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

"""Converters from A2A Protocol Buffer messages to ADK types."""

from __future__ import annotations

import base64
import logging
from typing import Optional

from google.adk.a2a.grpc.generated import a2a_pb2
from google.genai import types as genai_types
from google.adk.events.event import Event
from google.adk.agents.invocation_context import InvocationContext
from google.adk.a2a.experimental import a2a_experimental
from google.protobuf import struct_pb2
import uuid

logger = logging.getLogger('google_adk.' + __name__)


@a2a_experimental
class ProtoToAdkConverter:
  """Converts A2A Protocol Buffer messages to ADK types."""

  def convert_part(self, proto_part: a2a_pb2.Part) -> Optional[genai_types.Part]:
    """Convert proto Part to GenAI Part.
    
    Args:
      proto_part: The protocol buffer Part to convert.
      
    Returns:
      A GenAI Part or None if conversion fails.
    """
    try:
      # Handle text part
      if proto_part.HasField('text'):
        return genai_types.Part(text=proto_part.text)
      
      # Handle file part
      if proto_part.HasField('file'):
        file_part = proto_part.file
        
        # File with URI
        if file_part.HasField('file_with_uri'):
          return genai_types.Part(
              file_data=genai_types.FileData(
                  file_uri=file_part.file_with_uri,
                  mime_type=file_part.media_type,
              )
          )
        
        # File with bytes
        if file_part.HasField('file_with_bytes'):
          return genai_types.Part(
              inline_data=genai_types.Blob(
                  data=file_part.file_with_bytes,
                  mime_type=file_part.media_type,
              )
          )
      
      # Handle data part (structured data)
      if proto_part.HasField('data'):
        data_part = proto_part.data
        # Convert protobuf Struct to dict
        data_dict = self._struct_to_dict(data_part.data)
        
        # Check metadata for special types (function_call, function_response, etc.)
        if proto_part.metadata:
          metadata_dict = self._struct_to_dict(proto_part.metadata)
          part_type = metadata_dict.get('adk:type')
          
          if part_type == 'function_call':
            return genai_types.Part(
                function_call=genai_types.FunctionCall.model_validate(
                    data_dict, by_alias=True
                )
            )
          elif part_type == 'function_response':
            return genai_types.Part(
                function_response=genai_types.FunctionResponse.model_validate(
                    data_dict, by_alias=True
                )
            )
          elif part_type == 'code_execution_result':
            return genai_types.Part(
                code_execution_result=genai_types.CodeExecutionResult.model_validate(
                    data_dict, by_alias=True
                )
            )
          elif part_type == 'executable_code':
            return genai_types.Part(
                executable_code=genai_types.ExecutableCode.model_validate(
                    data_dict, by_alias=True
                )
            )
        
        # Default: return as text
        import json
        return genai_types.Part(text=json.dumps(data_dict))
      
      logger.warning('Cannot convert unsupported proto part: %s', proto_part)
      return None
      
    except Exception as e:
      logger.error('Failed to convert proto part: %s', e)
      return None

  def convert_message(
      self, 
      proto_msg: a2a_pb2.Message,
      author: Optional[str] = None,
      invocation_context: Optional[InvocationContext] = None,
  ) -> Event:
    """Convert proto Message to ADK Event.
    
    Args:
      proto_msg: The protocol buffer Message to convert.
      author: The author of the event.
      invocation_context: The invocation context.
      
    Returns:
      An ADK Event object.
    """
    if not proto_msg.parts:
      logger.warning('Proto message has no parts, creating event with empty content')
      return Event(
          invocation_id=(
              invocation_context.invocation_id
              if invocation_context
              else str(uuid.uuid4())
          ),
          author=author or 'a2a agent',
          branch=invocation_context.branch if invocation_context else None,
          content=genai_types.Content(role='model', parts=[]),
      )
    
    output_parts = []
    long_running_tool_ids = set()
    
    for proto_part in proto_msg.parts:
      part = self.convert_part(proto_part)
      if part:
        output_parts.append(part)
        
        # Check for long-running tools
        if proto_part.metadata:
          metadata_dict = self._struct_to_dict(proto_part.metadata)
          if metadata_dict.get('adk:is_long_running') is True and part.function_call:
            long_running_tool_ids.add(part.function_call.id)
    
    return Event(
        invocation_id=(
            invocation_context.invocation_id
            if invocation_context
            else str(uuid.uuid4())
        ),
        author=author or 'a2a agent',
        branch=invocation_context.branch if invocation_context else None,
        long_running_tool_ids=long_running_tool_ids if long_running_tool_ids else None,
        content=genai_types.Content(
            role='model',
            parts=output_parts,
        ),
    )

  def convert_task(self, proto_task: a2a_pb2.Task) -> dict:
    """Convert proto Task to ADK task representation.
    
    Args:
      proto_task: The protocol buffer Task to convert.
      
    Returns:
      A dictionary representing the task.
    """
    return {
        'id': proto_task.id,
        'context_id': proto_task.context_id,
        'status': {
            'state': a2a_pb2.TaskState.Name(proto_task.status.state),
            'timestamp': proto_task.status.timestamp.ToJsonString() if proto_task.status.timestamp else None,
        },
        'metadata': self._struct_to_dict(proto_task.metadata) if proto_task.metadata else {},
    }

  def _struct_to_dict(self, struct: struct_pb2.Struct) -> dict:
    """Convert protobuf Struct to Python dict.
    
    Args:
      struct: The protobuf Struct to convert.
      
    Returns:
      A Python dictionary.
    """
    from google.protobuf.json_format import MessageToDict
    return MessageToDict(struct)
