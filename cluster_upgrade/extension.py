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

import os

from nailgun import extensions

from cluster_upgrade import handlers


class UpgradePipeline(extensions.BasePipeline):
    @classmethod
    def process_deployment_for_cluster(cls, cluster, cluster_data):
        from cluster_upgrade.objects.relations import UpgradeRelationObject

        relation = UpgradeRelationObject.get_cluster_relation(cluster.id)
        cluster_data['upgrade'] = {
            'relation_info': {
                'orig_cluster_id': relation.orig_cluster_id,
                'seed_cluster_id': relation.seed_cluster_id,
            }
        }


class ClusterUpgradeExtension(extensions.BaseExtension):
    name = 'cluster_upgrade'
    version = '0.0.1'
    description = "Cluster Upgrade Extension"

    data_pipelines = [
        UpgradePipeline,
    ]

    urls = [
        {'uri': r'/clusters/(?P<cluster_id>\d+)/upgrade/clone/?$',
         'handler': handlers.ClusterUpgradeCloneHandler},
        {'uri': r'/clusters/(?P<cluster_id>\d+)/upgrade/assign/?$',
         'handler': handlers.NodeReassignHandler},
        {'uri': r'/clusters/(?P<cluster_id>\d+)/upgrade/vips/?$',
         'handler': handlers.CopyVIPsHandler},
        {'uri': r'/clusters/(?P<cluster_id>\d+)/upgrade/clone_release/'
                r'(?P<release_id>\d+)/?$',
         'handler': handlers.CreateUpgradeReleaseHandler},
    ]

    @classmethod
    def alembic_migrations_path(cls):
        return os.path.join(os.path.dirname(__file__),
                            'alembic_migrations', 'migrations')

    @classmethod
    def on_cluster_delete(cls, cluster):
        from .objects import relations

        relations.UpgradeRelationObject.delete_relation(cluster.id)
