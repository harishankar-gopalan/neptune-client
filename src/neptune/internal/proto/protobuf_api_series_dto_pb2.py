#
# Copyright (c) 2024, Neptune Labs Sp. z o.o.
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
#
"""Generated protocol buffer code."""

from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder

# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(
    b'\n\x1dprotobuf_api_series_dto.proto\x12\x39ml.neptune.leaderboard.api.model.channels.proto.generated"\x8a\x01\n\x1aProtobufFloatPointValueDto\x12\x1d\n\x10timestamp_millis\x18\x01 \x01(\x03H\x00\x88\x01\x01\x12\x11\n\x04step\x18\x02 \x01(\x01H\x01\x88\x01\x01\x12\x12\n\x05value\x18\x03 \x01(\x01H\x02\x88\x01\x01\x42\x13\n\x11_timestamp_millisB\x07\n\x05_stepB\x08\n\x06_value"\xb3\x01\n\x16ProtobufFloatSeriesDto\x12\x65\n\x06values\x18\x01 \x03(\x0b\x32U.ml.neptune.leaderboard.api.model.channels.proto.generated.ProtobufFloatPointValueDto\x12\x1d\n\x10total_item_count\x18\x02 \x01(\x05H\x00\x88\x01\x01\x42\x13\n\x11_total_item_count"\x8b\x01\n\x1bProtobufStringPointValueDto\x12\x1d\n\x10timestamp_millis\x18\x01 \x01(\x03H\x00\x88\x01\x01\x12\x11\n\x04step\x18\x02 \x01(\x01H\x01\x88\x01\x01\x12\x12\n\x05value\x18\x03 \x01(\tH\x02\x88\x01\x01\x42\x13\n\x11_timestamp_millisB\x07\n\x05_stepB\x08\n\x06_value"\xb5\x01\n\x17ProtobufStringSeriesDto\x12\x66\n\x06values\x18\x01 \x03(\x0b\x32V.ml.neptune.leaderboard.api.model.channels.proto.generated.ProtobufStringPointValueDto\x12\x1d\n\x10total_item_count\x18\x02 \x01(\x05H\x00\x88\x01\x01\x42\x13\n\x11_total_item_countB=\n9ml.neptune.leaderboard.api.model.channels.proto.generatedP\x01\x62\x06proto3'
)

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, "protobuf_api_series_dto_pb2", _globals)
if _descriptor._USE_C_DESCRIPTORS == False:
    _globals["DESCRIPTOR"]._options = None
    _globals["DESCRIPTOR"]._serialized_options = b"\n9ml.neptune.leaderboard.api.model.channels.proto.generatedP\001"
    _globals["_PROTOBUFFLOATPOINTVALUEDTO"]._serialized_start = 93
    _globals["_PROTOBUFFLOATPOINTVALUEDTO"]._serialized_end = 231
    _globals["_PROTOBUFFLOATSERIESDTO"]._serialized_start = 234
    _globals["_PROTOBUFFLOATSERIESDTO"]._serialized_end = 413
    _globals["_PROTOBUFSTRINGPOINTVALUEDTO"]._serialized_start = 416
    _globals["_PROTOBUFSTRINGPOINTVALUEDTO"]._serialized_end = 555
    _globals["_PROTOBUFSTRINGSERIESDTO"]._serialized_start = 558
    _globals["_PROTOBUFSTRINGSERIESDTO"]._serialized_end = 739
# @@protoc_insertion_point(module_scope)
