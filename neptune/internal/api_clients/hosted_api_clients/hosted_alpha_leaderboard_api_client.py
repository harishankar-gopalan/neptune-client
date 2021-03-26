#
# Copyright (c) 2021, Neptune Labs Sp. z o.o.
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
import logging
import os
import uuid
from collections import namedtuple
from io import StringIO
from itertools import groupby
from pathlib import Path
from typing import List, Dict

import six
from bravado.exception import HTTPNotFound
from neptune.new.internal.backends.api_model import AttributeType

from neptune.new import exceptions as alpha_exceptions
from neptune.new.attributes import constants as alpha_consts
from neptune.new.internal import operation as alpha_operation
from neptune.new.internal.backends import hosted_file_operations as alpha_hosted_file_operations
from neptune.new.internal.backends.operation_api_name_visitor import \
    OperationApiNameVisitor as AlphaOperationApiNameVisitor
from neptune.new.internal.backends.operation_api_object_converter import \
    OperationApiObjectConverter as AlphaOperationApiObjectConverter
from neptune.new.internal.operation import ConfigFloatSeries, LogFloats, AssignString
from neptune.new.internal.utils import paths as alpha_path_utils, base64_encode, base64_decode
from neptune.new.internal.utils.paths import parse_path
from neptune.api_exceptions import (
    ExperimentOperationErrors,
    ExperimentNotFound,
    ProjectNotFound,
)
from neptune.exceptions import NeptuneException, FileNotFound
from neptune.experiments import Experiment
from neptune.internal.api_clients.hosted_api_clients.hosted_leaderboard_api_client import \
    HostedNeptuneLeaderboardApiClient
from neptune.internal.channels.channels import ChannelType, ChannelValueType
from neptune.internal.storage.storage_utils import normalize_file_name
from neptune.internal.utils.alpha_integration import (
    AlphaChannelDTO,
    AlphaChannelWithValueDTO,
    AlphaParameterDTO,
    AlphaPropertyDTO,
    channel_type_to_operation,
    channel_value_type_to_operation,
    deprecated_img_to_alpha_image, channel_type_to_clear_operation,
)
from neptune.model import ChannelWithLastValue, LeaderboardEntry
from neptune.utils import with_api_exceptions_handler

_logger = logging.getLogger(__name__)

LegacyExperiment = namedtuple(
    'LegacyExperiment',
    'shortId '
    'name '
    'timeOfCreation '
    'timeOfCompletion '
    'runningTime '
    'owner '
    'storageSize '
    'channelsSize '
    'tags '
    'description '
    'hostname '
    'state '
    'properties '
    'parameters')

LegacyLeaderboardEntry = namedtuple(
    'LegacyExperiment',
    'id '
    'organizationName '
    'projectName '
    'shortId '
    'name '
    'state '
    'timeOfCreation '
    'timeOfCompletion '
    'runningTime '
    'owner '
    'size '
    'tags '
    'description '
    'channelsLastValues '
    'parameters '
    'properties'
)


class HostedAlphaLeaderboardApiClient(HostedNeptuneLeaderboardApiClient):

    @with_api_exceptions_handler
    def create_experiment(self,
                          project,
                          name,
                          description,
                          params,
                          properties,
                          tags,
                          abortable,  # deprecated in alpha
                          monitored,  # deprecated in alpha
                          git_info,
                          hostname,
                          entrypoint,
                          notebook_id,
                          checkpoint_id):
        if not isinstance(name, six.string_types):
            raise ValueError("Invalid name {}, should be a string.".format(name))
        if not isinstance(description, six.string_types):
            raise ValueError("Invalid description {}, should be a string.".format(description))
        if not isinstance(params, dict):
            raise ValueError("Invalid params {}, should be a dict.".format(params))
        if not isinstance(properties, dict):
            raise ValueError("Invalid properties {}, should be a dict.".format(properties))
        if hostname is not None and not isinstance(hostname, six.string_types):
            raise ValueError("Invalid hostname {}, should be a string.".format(hostname))
        if entrypoint is not None and not isinstance(entrypoint, six.string_types):
            raise ValueError("Invalid entrypoint {}, should be a string.".format(entrypoint))

        git_info = {
            "commit": {
                "commitId": git_info.commit_id,
                "message": git_info.message,
                "authorName": git_info.author_name,
                "authorEmail": git_info.author_email,
                "commitDate": git_info.commit_date
            },
            "repositoryDirty": git_info.repository_dirty,
            "currentBranch": git_info.active_branch,
            "remotes": git_info.remote_urls
        } if git_info else None

        api_params = {
            "notebookId": notebook_id,
            "checkpointId": checkpoint_id,
            "projectIdentifier": str(project.internal_id),
            "cliVersion": self.client_lib_version,
            "gitInfo": git_info,
            "customId": None,
        }

        kwargs = {
            'experimentCreationParams': api_params,
            'X-Neptune-CliVersion': self.client_lib_version,
        }

        try:
            api_experiment = self.leaderboard_swagger_client.api.createExperiment(**kwargs).response().result
        except HTTPNotFound:
            raise ProjectNotFound(project_identifier=project.full_id)

        experiment = self._convert_to_experiment(api_experiment, project)
        # Initialize new experiment
        init_experiment_operations = self._get_init_experiment_operations(name,
                                                                          description,
                                                                          params,
                                                                          properties,
                                                                          tags,
                                                                          hostname,
                                                                          entrypoint)
        self._execute_operations(
            experiment=experiment,
            operations=init_experiment_operations,
        )
        return experiment

    def upload_source_code(self, experiment, source_target_pairs):
        dest_path = alpha_path_utils.parse_path(alpha_consts.SOURCE_CODE_FILES_ATTRIBUTE_PATH)
        file_globs = [source_path for source_path, target_path in source_target_pairs]
        upload_files_operation = alpha_operation.UploadFileSet(
            path=dest_path,
            file_globs=file_globs,
            reset=True,
        )
        self._execute_upload_operation(experiment, upload_files_operation)

    @with_api_exceptions_handler
    def get_experiment(self, experiment_id):
        api_attributes = self._get_api_experiment_attributes(experiment_id)
        attributes = api_attributes.attributes
        system_attributes = api_attributes.systemAttributes

        return LegacyExperiment(
            shortId=system_attributes.shortId.value,
            name=system_attributes.name.value,
            timeOfCreation=system_attributes.creationTime.value,
            timeOfCompletion=None,
            runningTime=system_attributes.runningTime.value,
            owner=system_attributes.owner.value,
            storageSize=system_attributes.size.value,
            channelsSize=0,
            tags=system_attributes.tags.values,
            description=system_attributes.description.value,
            hostname=system_attributes.hostname.value if system_attributes.hostname else None,
            state="running" if system_attributes.state.value == "running" else "succeeded",
            properties=[
                AlphaPropertyDTO(attr) for attr in attributes
                if AlphaPropertyDTO.is_valid_attribute(attr)
            ],
            parameters=[
                AlphaParameterDTO(attr) for attr in attributes
                if AlphaParameterDTO.is_valid_attribute(attr)
            ]
        )

    def update_experiment(self, experiment, properties):
        raise NeptuneException("`update_experiment` shouldn't be called.")

    @with_api_exceptions_handler
    def set_property(self, experiment, key, value):
        """Save attribute casted to string under `alpha_consts.PROPERTIES_ATTRIBUTE_SPACE` namespace"""
        self._execute_operations(
            experiment=experiment,
            operations=[alpha_operation.AssignString(
                path=alpha_path_utils.parse_path(f'{alpha_consts.PROPERTIES_ATTRIBUTE_SPACE}{key}'),
                value=str(value),
            )],
        )

    @with_api_exceptions_handler
    def remove_property(self, experiment, key):
        self._remove_attribute(experiment, str_path=f'{alpha_consts.PROPERTIES_ATTRIBUTE_SPACE}{key}')

    @with_api_exceptions_handler
    def update_tags(self, experiment, tags_to_add, tags_to_delete):
        operations = [
            alpha_operation.AddStrings(
                path=alpha_path_utils.parse_path(alpha_consts.SYSTEM_TAGS_ATTRIBUTE_PATH),
                values=tags_to_add,
            ),
            alpha_operation.RemoveStrings(
                path=alpha_path_utils.parse_path(alpha_consts.SYSTEM_TAGS_ATTRIBUTE_PATH),
                values=tags_to_delete,
            )
        ]
        self._execute_operations(
            experiment=experiment,
            operations=operations,
        )

    def upload_experiment_source(self, experiment, data, progress_indicator):
        # TODO: handle `FileChunkStream` or update `neptune.experiments.Experiment._start`
        pass

    def _create_channel(self, experiment: Experiment, channel_id: str, channel_name: str, channel_type: str):
        """This function is responsible for creating 'fake' channels in alpha projects.

        Since channels are abandoned in alpha api, we're mocking them using empty logging operation."""

        operation = channel_type_to_operation(ChannelType(channel_type))

        log_empty_operation = operation(
            path=alpha_path_utils.parse_path(channel_id),
            values=[],
        )  # this operation is used to create empty attribute
        self._execute_operations(
            experiment=experiment,
            operations=[log_empty_operation],
        )
        return ChannelWithLastValue(
            AlphaChannelWithValueDTO(
                channelId=channel_id,
                channelName=channel_name,
                channelType=channel_type,
                x=None,
                y=None
            )
        )

    @with_api_exceptions_handler
    def create_channel(self, experiment, name, channel_type) -> ChannelWithLastValue:
        channel_id = f'{alpha_consts.LOG_ATTRIBUTE_SPACE}{name}'
        return self._create_channel(experiment, channel_id,
                                    channel_name=name,
                                    channel_type=channel_type)

    def _get_channels(self, experiment) -> List[AlphaChannelDTO]:
        try:
            return [
                AlphaChannelDTO(attr) for attr in self._get_attributes(experiment.internal_id)
                if AlphaChannelDTO.is_valid_attribute(attr)
            ]
        except HTTPNotFound:
            # pylint: disable=protected-access
            raise ExperimentNotFound(
                experiment_short_id=experiment.id, project_qualified_name=experiment._project.full_id)

    @with_api_exceptions_handler
    def get_channels(self, experiment) -> Dict[str, AlphaChannelDTO]:
        api_channels = [
            channel for channel in self._get_channels(experiment)
            # return channels from LOG_ATTRIBUTE_SPACE namespace only
            if channel.id.startswith(alpha_consts.LOG_ATTRIBUTE_SPACE)
        ]
        return {ch.name: ch for ch in api_channels}

    @with_api_exceptions_handler
    def create_system_channel(self, experiment, name, channel_type) -> ChannelWithLastValue:
        channel_id = f'{alpha_consts.MONITORING_ATTRIBUTE_SPACE}{name}'
        return self._create_channel(experiment, channel_id,
                                    channel_name=name,
                                    channel_type=ChannelType.TEXT.value)

    @with_api_exceptions_handler
    def get_system_channels(self, experiment) -> Dict[str, AlphaChannelDTO]:
        return {
            channel.name: channel
            for channel in self._get_channels(experiment)
            if (channel.channelType == ChannelType.TEXT.value
                and channel.id.startswith(alpha_consts.MONITORING_ATTRIBUTE_SPACE))
        }

    @with_api_exceptions_handler
    def send_channels_values(self, experiment, channels_with_values):
        send_operations = []
        for channel_with_values in channels_with_values:
            channel_value_type = channel_with_values.channel_type
            operation = channel_value_type_to_operation(channel_value_type)

            if channel_value_type == ChannelValueType.IMAGE_VALUE:
                # IMAGE_VALUE requires minor data modification before it's sent
                data_transformer = deprecated_img_to_alpha_image
            else:
                # otherwise use identity function as transformer
                data_transformer = lambda e: e

            ch_values = [
                alpha_operation.LogSeriesValue(
                    value=data_transformer(ch_value.value),
                    step=ch_value.x,
                    ts=ch_value.ts,
                )
                for ch_value in channel_with_values.channel_values
            ]
            send_operations.append(operation(
                path=alpha_path_utils.parse_path(channel_with_values.channel_id),
                values=ch_values,
            ))

        self._execute_operations(experiment, send_operations)

    def mark_succeeded(self, experiment):
        pass

    def mark_failed(self, experiment, traceback):
        pass

    def ping_experiment(self, experiment):
        try:
            self.leaderboard_swagger_client.api.ping(experimentId=str(experiment.internal_id)).response().result
        except HTTPNotFound:
            # pylint: disable=protected-access
            raise ExperimentNotFound(
                experiment_short_id=experiment.id, project_qualified_name=experiment._project.full_id)

    @staticmethod
    def _get_attribute_name_for_metric(resource_type, gauge_name, gauges_count) -> str:
        if gauges_count > 1:
            return "monitoring/{}_{}".format(resource_type, gauge_name).lower()
        return "monitoring/{}".format(resource_type).lower()

    @with_api_exceptions_handler
    def create_hardware_metric(self, experiment, metric):
        operations = []
        gauges_count = len(metric.gauges)
        for gauge in metric.gauges:
            path = parse_path(self._get_attribute_name_for_metric(metric.resource_type, gauge.name(), gauges_count))
            operations.append(ConfigFloatSeries(path, min=metric.min_value, max=metric.max_value, unit=metric.unit))
        self._execute_operations(experiment, operations)

    @with_api_exceptions_handler
    def send_hardware_metric_reports(self, experiment, metrics, metric_reports):
        operations = []
        metrics_by_name = {metric.name: metric for metric in metrics}
        for report in metric_reports:
            metric = metrics_by_name.get(report.metric.name)
            gauges_count = len(metric.gauges)
            for gauge_name, metric_values in groupby(report.values, lambda value: value.gauge_name):
                metric_values = list(metric_values)
                path = parse_path(self._get_attribute_name_for_metric(metric.resource_type, gauge_name, gauges_count))
                operations.append(LogFloats(
                    path,
                    [LogFloats.ValueType(value.value, step=None, ts=value.timestamp) for value in metric_values]))
        self._execute_operations(experiment, operations)

    def log_artifact(self, experiment, artifact, destination=None):
        if isinstance(artifact, str):
            if os.path.isfile(artifact):
                target_name = os.path.basename(artifact) if destination is None else destination
                dest_path, ext = self._get_dest_and_ext(target_name)
                operation = alpha_operation.UploadFile(
                    path=dest_path,
                    ext=ext,
                    file_path=os.path.abspath(artifact),
                )
            elif os.path.isdir(artifact):
                for path, file_destination in self._log_dir_artifacts(artifact, destination):
                    self.log_artifact(experiment, path, file_destination)
                return
            else:
                raise FileNotFound(artifact)
        elif hasattr(artifact, 'read'):
            if not destination:
                raise ValueError("destination is required for IO streams")
            dest_path, ext = self._get_dest_and_ext(destination)
            data = artifact.read()
            content = data.encode('utf-8') if isinstance(data, str) else data
            operation = alpha_operation.UploadFileContent(
                path=dest_path,
                ext=ext,
                file_content=base64_encode(content)
            )
        else:
            raise ValueError("Artifact must be a local path or an IO object")

        self._execute_upload_operation(experiment, operation)

    @staticmethod
    def _get_dest_and_ext(target_name):
        qualified_target_name = f'{alpha_consts.ARTIFACT_ATTRIBUTE_SPACE}{target_name}'
        dest_path = alpha_path_utils.parse_path(normalize_file_name(qualified_target_name))
        ext = os.path.splitext(target_name)[1]
        return dest_path, ext

    def _log_dir_artifacts(self, directory_path, destination):
        directory_path = Path(directory_path)
        prefix = directory_path.name if destination is None else destination
        for path in directory_path.glob('**/*'):
            if path.is_file():
                relative_path = path.relative_to(directory_path)
                file_destination = prefix + '/' + str(relative_path)
                yield str(path), file_destination

    def delete_artifacts(self, experiment, path):
        self._remove_attribute(experiment, str_path=f'{alpha_consts.ARTIFACT_ATTRIBUTE_SPACE}{path}')

    def _get_attributes(self, experiment_id) -> list:
        return self._get_api_experiment_attributes(experiment_id).attributes

    def _get_api_experiment_attributes(self, experiment_id):
        params = {
            'experimentId': experiment_id,
        }
        return self.leaderboard_swagger_client.api.getExperimentAttributes(**params).response().result

    def _remove_attribute(self, experiment, str_path: str):
        """Removes given attribute"""
        self._execute_operations(
            experiment=experiment,
            operations=[alpha_operation.DeleteAttribute(
                path=alpha_path_utils.parse_path(str_path),
            )],
        )

    @staticmethod
    def _get_client_config_args(api_token):
        return dict(
            X_Neptune_Api_Token=api_token,
            alpha="true",
        )

    def _execute_upload_operation(self,
                                  experiment: Experiment,
                                  upload_operation: alpha_operation.Operation):
        experiment_uuid = uuid.UUID(experiment.internal_id)
        try:
            if isinstance(upload_operation, alpha_operation.UploadFile):
                alpha_hosted_file_operations.upload_file_attribute(
                    swagger_client=self.leaderboard_swagger_client,
                    run_uuid=experiment_uuid,
                    attribute=alpha_path_utils.path_to_str(upload_operation.path),
                    source=upload_operation.file_path,
                    ext=upload_operation.ext)
            elif isinstance(upload_operation, alpha_operation.UploadFileContent):
                alpha_hosted_file_operations.upload_file_attribute(
                    swagger_client=self.leaderboard_swagger_client,
                    run_uuid=experiment_uuid,
                    attribute=alpha_path_utils.path_to_str(upload_operation.path),
                    source=base64_decode(upload_operation.file_content),
                    ext=upload_operation.ext)
            elif isinstance(upload_operation, alpha_operation.UploadFileSet):
                alpha_hosted_file_operations.upload_file_set_attribute(
                    swagger_client=self.leaderboard_swagger_client,
                    run_uuid=experiment_uuid,
                    attribute=alpha_path_utils.path_to_str(upload_operation.path),
                    file_globs=upload_operation.file_globs,
                    reset=upload_operation.reset)
            else:
                raise NeptuneException("Upload operation in neither File or FileSet")
        except alpha_exceptions.NeptuneException as e:
            raise NeptuneException(e) from e

        return None

    @with_api_exceptions_handler
    def _execute_operations(self, experiment: Experiment, operations: List[alpha_operation.Operation]):
        experiment_uuid = uuid.UUID(experiment.internal_id)
        file_operations = (
            alpha_operation.UploadFile,
            alpha_operation.UploadFileContent,
            alpha_operation.UploadFileSet
        )
        if any(isinstance(op, file_operations) for op in operations):
            raise NeptuneException("File operations must be handled directly by `_execute_upload_operation`,"
                                   " not by `_execute_operations` function call.")

        kwargs = {
            'experimentId': str(experiment_uuid),
            'operations': [
                {
                    'path': alpha_path_utils.path_to_str(op.path),
                    AlphaOperationApiNameVisitor().visit(op): AlphaOperationApiObjectConverter().convert(op)
                }
                for op in operations
            ]
        }
        try:
            result = self.leaderboard_swagger_client.api.executeOperations(**kwargs).response().result
            errors = [
                alpha_exceptions.MetadataInconsistency(err.errorDescription)
                for err in result
            ]
            if errors:
                raise ExperimentOperationErrors(errors=errors)
            return None
        except HTTPNotFound as e:
            # pylint: disable=protected-access
            raise ExperimentNotFound(
                experiment_short_id=experiment.id,
                project_qualified_name=experiment._project.full_id
            ) from e

    def _get_init_experiment_operations(self,
                                        name,
                                        description,
                                        params,
                                        properties,
                                        tags,
                                        hostname,
                                        entrypoint) -> List[alpha_operation.Operation]:
        """Returns operations required to initialize newly created experiment"""
        init_operations = list()

        # Assign experiment name
        init_operations.append(alpha_operation.AssignString(
            path=alpha_path_utils.parse_path(alpha_consts.SYSTEM_NAME_ATTRIBUTE_PATH),
            value=name,
        ))
        # Assign experiment description
        init_operations.append(alpha_operation.AssignString(
            path=alpha_path_utils.parse_path(alpha_consts.SYSTEM_DESCRIPTION_ATTRIBUTE_PATH),
            value=description,
        ))
        # Assign experiment parameters
        for p_name, p_val in params.items():
            parameter_type, string_value = self._get_parameter_with_type(p_val)
            operation_cls = alpha_operation.AssignFloat if parameter_type == 'double' else alpha_operation.AssignString
            init_operations.append(operation_cls(
                path=alpha_path_utils.parse_path(f'{alpha_consts.PARAMETERS_ATTRIBUTE_SPACE}{p_name}'),
                value=string_value,
            ))
        # Assign experiment properties
        for p_key, p_val in properties.items():
            init_operations.append(AssignString(
                path=alpha_path_utils.parse_path(f'{alpha_consts.PROPERTIES_ATTRIBUTE_SPACE}{p_key}'),
                value=str(p_val),
            ))
        # Assign tags
        if tags:
            init_operations.append(alpha_operation.AddStrings(
                path=alpha_path_utils.parse_path(alpha_consts.SYSTEM_TAGS_ATTRIBUTE_PATH),
                values=set(tags),
            ))
        # Assign source hostname
        if hostname:
            init_operations.append(alpha_operation.AssignString(
                path=alpha_path_utils.parse_path(alpha_consts.SYSTEM_HOSTNAME_ATTRIBUTE_PATH),
                value=hostname,
            ))
        # Assign source entrypoint
        if entrypoint:
            init_operations.append(alpha_operation.AssignString(
                path=alpha_path_utils.parse_path(alpha_consts.SOURCE_CODE_ENTRYPOINT_ATTRIBUTE_PATH),
                value=entrypoint,
            ))

        return init_operations

    @with_api_exceptions_handler
    def reset_channel(self, experiment, channel_id, channel_type):
        op = channel_type_to_clear_operation(ChannelType(channel_type))
        self._execute_operations(
            experiment=experiment,
            operations=[op(path=alpha_path_utils.parse_path(channel_id))],
        )

    @with_api_exceptions_handler
    def _get_channel_tuples_from_csv(self, experiment, channel_internal_id):
        try:
            csv = self.leaderboard_swagger_client.api.getFloatSeriesValuesCSV(
                experimentId=experiment.internal_id, attribute=channel_internal_id
            ).response().incoming_response.text
            lines = csv.split('\n')[:-1]
            return [line.split(',') for line in lines]
        except HTTPNotFound:
            # pylint: disable=protected-access
            raise ExperimentNotFound(
                experiment_short_id=experiment.id, project_qualified_name=experiment._project.full_id)

    @with_api_exceptions_handler
    def get_channel_points_csv(self, experiment, channel_internal_id):
        try:
            values = self._get_channel_tuples_from_csv(experiment, channel_internal_id)
            step_and_value = [val[0] + ',' + val[2] for val in values]
            csv = StringIO()
            for line in step_and_value:
                csv.write(line + "\n")
            csv.seek(0)
            return csv
        except HTTPNotFound:
            # pylint: disable=protected-access
            raise ExperimentNotFound(
                experiment_short_id=experiment.id, project_qualified_name=experiment._project.full_id)

    @with_api_exceptions_handler
    def get_metrics_csv(self, experiment):
        metric_channels = [
            channel for channel in self._get_channels(experiment)
            if (channel.channelType == ChannelType.NUMERIC.value
                and channel.id.startswith(alpha_consts.MONITORING_ATTRIBUTE_SPACE))
        ]
        data = {
            # val[1] + ',' + val[2] is timestamp,value
            ch.name: [val[1] + ',' + val[2] for val in self._get_channel_tuples_from_csv(experiment, ch.id)]
            for ch in metric_channels
        }
        values_count = max(len(values) for values in data.values())
        csv = StringIO()
        csv.write(','.join(["x_{name},y_{name}".format(name=ch.name) for ch in metric_channels]))
        csv.write("\n")
        for i in range(0, values_count):
            csv.write(','.join([data[ch.name][i] if i < len(data[ch.name]) else "," for ch in metric_channels]))
            csv.write("\n")
        csv.seek(0)
        return csv

    @with_api_exceptions_handler
    def get_leaderboard_entries(self, project,
                                entry_types=None,  # deprecated
                                ids=None,
                                states=None,
                                owners=None,
                                tags=None,
                                min_running_time=None):
        if states is not None:
            states = [state if state == "running" else "idle" for state in states]
        try:
            def get_portion(limit, offset):
                return self.leaderboard_swagger_client.api.getLeaderboard(
                    projectIdentifier=project.full_id,
                    shortId=ids, state=states, owner=owners, tags=tags,
                    tagsMode='and', minRunningTimeSeconds=min_running_time,
                    sortBy=['sys/id'], sortFieldType=['string'], sortDirection=['ascending'],
                    limit=limit, offset=offset
                ).response().result.entries
            return [LeaderboardEntry(self._to_leaderboard_entry_dto(e))
                    for e in self._get_all_items(get_portion, step=100)]
        except HTTPNotFound:
            raise ProjectNotFound(project_identifier=project.full_id)

    @staticmethod
    def _to_leaderboard_entry_dto(experiment_attributes):
        attributes = experiment_attributes.attributes
        system_attributes = experiment_attributes.systemAttributes

        def is_channel_namespace(name):
            return name.startswith(alpha_consts.LOG_ATTRIBUTE_SPACE)\
                   or name.startswith(alpha_consts.MONITORING_ATTRIBUTE_SPACE)

        numeric_channels = [
            HostedAlphaLeaderboardApiClient._float_series_to_channel_last_value_dto(attr)
            for attr in attributes
            if attr.type == AttributeType.FLOAT_SERIES.value
            and is_channel_namespace(attr.name)
            and attr.floatSeriesProperties.last is not None
        ]
        text_channels = [
            HostedAlphaLeaderboardApiClient._string_series_to_channel_last_value_dto(attr)
            for attr in attributes
            if attr.type == AttributeType.STRING_SERIES.value
            and is_channel_namespace(attr.name)
            and attr.stringSeriesProperties.last is not None
        ]

        return LegacyLeaderboardEntry(
            id=experiment_attributes.id,
            organizationName=experiment_attributes.organizationName,
            projectName=experiment_attributes.projectName,
            shortId=system_attributes.shortId.value,
            name=system_attributes.name.value,
            state="running" if system_attributes.state.value == "running" else "succeeded",
            timeOfCreation=system_attributes.creationTime.value,
            timeOfCompletion=None,
            runningTime=system_attributes.runningTime.value,
            owner=system_attributes.owner.value,
            size=system_attributes.size.value,
            tags=system_attributes.tags.values,
            description=system_attributes.description.value,
            channelsLastValues=numeric_channels + text_channels,
            parameters=[
                AlphaParameterDTO(attr) for attr in attributes
                if AlphaParameterDTO.is_valid_attribute(attr)
            ],
            properties=[
                AlphaPropertyDTO(attr) for attr in attributes
                if AlphaPropertyDTO.is_valid_attribute(attr)
            ]
        )

    @staticmethod
    def _float_series_to_channel_last_value_dto(attribute):
        return AlphaChannelWithValueDTO(
            channelId=attribute.name,
            channelName=attribute.name.split('/', 1)[-1],
            channelType="numeric",
            x=attribute.floatSeriesProperties.lastStep,
            y=attribute.floatSeriesProperties.last
        )

    @staticmethod
    def _string_series_to_channel_last_value_dto(attribute):
        return AlphaChannelWithValueDTO(
            channelId=attribute.name,
            channelName=attribute.name.split('/', 1)[-1],
            channelType="text",
            x=attribute.stringSeriesProperties.lastStep,
            y=attribute.stringSeriesProperties.last
        )
