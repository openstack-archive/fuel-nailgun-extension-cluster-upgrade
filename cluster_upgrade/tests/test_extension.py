# -*- coding: utf-8 -*-

#    Copyright 2015 Mirantis, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import mock
from oslo_serialization import jsonutils

from nailgun.orchestrator.deployment_serializers import DeploymentLCMSerializer
from nailgun.test.base import BaseTestCase
from nailgun import objects
from nailgun.utils import reverse

from cluster_upgrade.tests import base
from cluster_upgrade import extension
from cluster_upgrade.objects import relations


class TestExtension(BaseTestCase):
    @mock.patch.object(relations.UpgradeRelationObject, "delete_relation")
    def test_on_cluster_delete(self, mock_on_cluster_delete):
        cluster = mock.Mock(id=42)
        extension.ClusterUpgradeExtension.on_cluster_delete(cluster)
        mock_on_cluster_delete.assert_called_once_with(42)


class TestPipeline(base.BaseCloneClusterTest):
    def setUp(self):
        super(TestPipeline, self).setUp()

        resp = self.app.post(
            reverse("ClusterUpgradeCloneHandler",
                    kwargs={"cluster_id": self.src_cluster_db.id}),
            jsonutils.dumps(self.data),
            headers=self.default_headers
        ).json_body

        self.dst_cluster_db = objects.Cluster.get_by_uid(resp['id'])

    def test_upgrade_info(self):
        deployment_info = DeploymentLCMSerializer().serialize(
            self.dst_cluster_db, []
        )

        expected = {
            'relation_info': {
                'orig_cluster_id': self.src_cluster_db.id,
                'seed_cluster_id': self.dst_cluster_db.id,
            }
        }

        self.assertEqual(
            deployment_info['common']['upgrade'],
            expected,
        )
