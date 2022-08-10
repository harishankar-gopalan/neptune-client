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
from typing import Dict

import pytest

from e2e_tests.base import BaseE2ETest, fake
from e2e_tests.utils import Environment, a_project_name
from neptune.management import (
    add_project_member,
    add_project_service_account,
    create_project,
    delete_project,
    get_project_list,
    get_project_member_list,
    get_project_service_account_list,
    get_workspace_member_list,
    get_workspace_service_account_list,
    remove_project_member,
    remove_project_service_account,
)
from neptune.management.exceptions import UserNotExistsOrWithoutAccess
from neptune.management.internal.utils import normalize_project_name


@pytest.mark.management
class TestManagement(BaseE2ETest):
    @staticmethod
    def _assure_presence_and_role(
        *, username: str, expected_role: str, member_list: Dict[str, str]
    ):
        assert username in member_list
        assert member_list.get(username) == expected_role

    def test_standard_scenario(self, environment: Environment):
        project_name = a_project_name(project_slug=f"{fake.slug()}-mgmt")
        project_identifier = normalize_project_name(
            name=project_name, workspace=environment.workspace
        )

        assert project_identifier not in get_project_list(api_token=environment.admin_token)
        assert project_identifier not in get_project_list(api_token=environment.user_token)

        self._assure_presence_and_role(
            username=environment.user,
            expected_role="member",
            member_list=get_workspace_member_list(
                name=environment.workspace, api_token=environment.admin_token
            ),
        )
        self._assure_presence_and_role(
            username=environment.user,
            expected_role="member",
            member_list=get_workspace_member_list(
                name=environment.workspace, api_token=environment.user_token
            ),
        )
        self._assure_presence_and_role(
            username=environment.service_account,
            expected_role="member",
            member_list=get_workspace_service_account_list(
                name=environment.workspace, api_token=environment.user_token
            ),
        )

        created_project_identifier = create_project(
            name=project_name,
            visibility="priv",
            workspace=environment.workspace,
            api_token=environment.admin_token,
        )

        assert created_project_identifier == project_identifier
        assert created_project_identifier in get_project_list(api_token=environment.admin_token)
        assert created_project_identifier not in get_project_list(api_token=environment.user_token)

        assert environment.user not in get_project_member_list(
            name=created_project_identifier, api_token=environment.admin_token
        )
        assert environment.service_account not in get_project_service_account_list(
            name=created_project_identifier, api_token=environment.admin_token
        )

        add_project_service_account(
            name=created_project_identifier,
            service_account_name=environment.service_account,
            role="contributor",
            api_token=environment.admin_token,
        )
        add_project_member(
            name=created_project_identifier,
            username=environment.user,
            role="contributor",
            api_token=environment.admin_token,
        )

        project_members = get_project_member_list(
            name=created_project_identifier, api_token=environment.admin_token
        )
        assert environment.user in project_members
        assert project_members.get(environment.user) == "contributor"

        project_members = get_project_member_list(
            name=created_project_identifier, api_token=environment.user_token
        )
        assert environment.user in project_members
        assert project_members.get(environment.user) == "contributor"
        assert environment.service_account not in project_members

        assert created_project_identifier in get_project_list(api_token=environment.user_token)

        remove_project_member(
            name=created_project_identifier,
            username=environment.user,
            api_token=environment.admin_token,
        )
        remove_project_service_account(
            name=created_project_identifier,
            service_account_name=environment.service_account,
            api_token=environment.admin_token,
        )

        assert created_project_identifier not in get_project_list(api_token=environment.user_token)
        assert environment.user not in get_project_member_list(
            name=created_project_identifier, api_token=environment.admin_token
        )
        assert environment.service_account not in get_project_service_account_list(
            name=created_project_identifier, api_token=environment.admin_token
        )

        delete_project(name=created_project_identifier, api_token=environment.admin_token)

        assert created_project_identifier not in get_project_list(api_token=environment.admin_token)

    def test_visibility_workspace(self, environment: "Environment"):
        project_name = a_project_name(project_slug=f"{fake.slug()}-workspace")
        project_identifier = normalize_project_name(
            name=project_name, workspace=environment.workspace
        )

        assert project_identifier not in get_project_list(api_token=environment.admin_token)
        assert project_identifier not in get_project_list(api_token=environment.user_token)

        self._assure_presence_and_role(
            username=environment.user,
            expected_role="member",
            member_list=get_workspace_member_list(
                name=environment.workspace, api_token=environment.admin_token
            ),
        )

        created_project_identifier = create_project(
            name=project_name,
            visibility="workspace",
            workspace=environment.workspace,
            api_token=environment.admin_token,
        )

        assert created_project_identifier == project_identifier
        assert created_project_identifier in get_project_list(api_token=environment.admin_token)

        self._assure_presence_and_role(
            username=environment.user,
            expected_role="owner",
            member_list=get_project_member_list(
                name=created_project_identifier, api_token=environment.admin_token
            ),
        )
        assert environment.service_account not in get_project_service_account_list(
            name=created_project_identifier, api_token=environment.admin_token
        )

        add_project_service_account(
            name=created_project_identifier,
            service_account_name=environment.service_account,
            role="contributor",
            api_token=environment.admin_token,
        )

        self._assure_presence_and_role(
            username=environment.service_account,
            expected_role="contributor",
            member_list=get_project_service_account_list(
                name=created_project_identifier, api_token=environment.admin_token
            ),
        )

        with pytest.raises(UserNotExistsOrWithoutAccess):
            remove_project_member(
                name=created_project_identifier,
                username=environment.user,
                api_token=environment.admin_token,
            )

        remove_project_service_account(
            name=created_project_identifier,
            service_account_name=environment.service_account,
            api_token=environment.admin_token,
        )

        self._assure_presence_and_role(
            username=environment.user,
            expected_role="owner",
            member_list=get_project_member_list(
                name=created_project_identifier, api_token=environment.admin_token
            ),
        )
        assert environment.service_account not in get_project_service_account_list(
            name=created_project_identifier, api_token=environment.admin_token
        )

        delete_project(name=created_project_identifier, api_token=environment.admin_token)

        assert project_identifier not in get_project_list(api_token=environment.admin_token)

    def test_create_project(self, environment: "Environment"):
        project_name = a_project_name(project_slug=f"{fake.slug()}-create")
        project_identifier = normalize_project_name(
            name=project_name, workspace=environment.workspace
        )

        assert project_identifier not in get_project_list(api_token=environment.user_token)
        self._assure_presence_and_role(
            username=environment.user,
            expected_role="member",
            member_list=get_workspace_member_list(
                name=environment.workspace, api_token=environment.user_token
            ),
        )

        created_project_identifier = create_project(
            name=project_name,
            workspace=environment.workspace,
            api_token=environment.user_token,
        )

        assert created_project_identifier == project_identifier
        assert created_project_identifier in get_project_list(api_token=environment.user_token)

        delete_project(name=created_project_identifier, api_token=environment.admin_token)

        assert project_identifier not in get_project_list(api_token=environment.user_token)

    def _test_add_sa_to_project_as_owner(
        self, created_project_identifier: str, environment: "Environment"
    ):
        self._assure_presence_and_role(
            username=environment.user,
            expected_role="owner",
            member_list=get_project_member_list(
                name=created_project_identifier, api_token=environment.user_token
            ),
        )

        assert environment.service_account not in get_project_service_account_list(
            name=created_project_identifier, api_token=environment.user_token
        )

        add_project_service_account(
            name=created_project_identifier,
            service_account_name=environment.service_account,
            role="contributor",
            api_token=environment.user_token,
        )
        self._assure_presence_and_role(
            username=environment.service_account,
            expected_role="contributor",
            member_list=get_project_service_account_list(
                name=created_project_identifier, api_token=environment.user_token
            ),
        )

        remove_project_service_account(
            name=created_project_identifier,
            service_account_name=environment.service_account,
            api_token=environment.user_token,
        )
        assert environment.service_account not in get_project_service_account_list(
            name=created_project_identifier, api_token=environment.admin_token
        )

    def _test_add_user_to_project_as_sa(
        self, created_project_identifier: str, environment: "Environment"
    ):
        self._assure_presence_and_role(
            username=environment.service_account,
            expected_role="owner",
            member_list=get_project_service_account_list(
                name=created_project_identifier, api_token=environment.user_token
            ),
        )

        assert environment.user not in get_project_member_list(
            name=created_project_identifier, api_token=environment.user_token
        )

        add_project_member(
            name=created_project_identifier,
            username=environment.user,
            role="contributor",
            api_token=environment.admin_token,
        )
        self._assure_presence_and_role(
            username=environment.user,
            expected_role="contributor",
            member_list=get_project_member_list(
                name=created_project_identifier, api_token=environment.user_token
            ),
        )

        remove_project_member(
            name=created_project_identifier,
            username=environment.user,
            api_token=environment.admin_token,
        )
        assert environment.user not in get_project_member_list(
            name=created_project_identifier, api_token=environment.user_token
        )

    def test_invite_as_non_admin(self, environment: "Environment"):
        project_name = a_project_name(project_slug=f"{fake.slug()}-invitation")
        project_identifier = normalize_project_name(
            name=project_name, workspace=environment.workspace
        )

        created_project_identifier = create_project(
            name=project_name,
            workspace=environment.workspace,
            api_token=environment.user_token,
        )

        assert created_project_identifier == project_identifier
        assert created_project_identifier in get_project_list(api_token=environment.user_token)

        # user who created a project (`user_token` owner) will be automatically project owner
        sa_is_project_owner = (
            get_project_service_account_list(
                name=created_project_identifier, api_token=environment.user_token
            ).get(environment.service_account)
            == "owner"
        )
        user_is_project_owner = (
            get_project_member_list(
                name=created_project_identifier, api_token=environment.user_token
            ).get(environment.user)
            == "owner"
        )
        if sa_is_project_owner and not user_is_project_owner:
            # SA has access to project, so tests are run as SA
            self._test_add_user_to_project_as_sa(created_project_identifier, environment)
        elif user_is_project_owner and not sa_is_project_owner:
            # SA doesn't have access to project, so tests are run as user
            self._test_add_sa_to_project_as_owner(created_project_identifier, environment)
        else:
            raise AssertionError(
                "Expected to only SA or user to be owner of newly created project."
            )

        delete_project(name=created_project_identifier, api_token=environment.admin_token)

        assert project_identifier not in get_project_list(api_token=environment.user_token)
