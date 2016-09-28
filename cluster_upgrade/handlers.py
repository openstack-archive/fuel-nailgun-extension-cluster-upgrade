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

import copy
import six

from nailgun.api.v1.handlers import base
from nailgun import errors
from nailgun.extensions import manager as ext_manager
from nailgun import objects
from nailgun.task import manager

from . import upgrade
from . import validators
from .objects import adapters


class ClusterUpgradeCloneHandler(base.BaseHandler):
    single = objects.Cluster
    validator = validators.ClusterUpgradeValidator

    @base.handle_errors
    @base.validate
    @base.serialize
    def POST(self, cluster_id):
        """Initialize the upgrade of the cluster.

        Creates a new cluster with specified name and release_id. The
        new cluster is created with parameters that are copied from the
        cluster with the given cluster_id. The values of the generated
        and editable attributes are just copied from one to the other.

        :param cluster_id: ID of the cluster from which parameters would
                           be copied
        :returns: JSON representation of the created cluster
        :http: * 200 (OK)
               * 400 (upgrade parameters are invalid)
               * 404 (node or release not found in db)
        """
        orig_cluster = adapters.NailgunClusterAdapter(
            self.get_object_or_404(self.single, cluster_id))
        request_data = self.checked_data(cluster=orig_cluster)
        new_cluster = upgrade.UpgradeHelper.clone_cluster(orig_cluster,
                                                          request_data)
        valid = upgrade.UpgradeHelper.validate_network_roles(
            orig_cluster, new_cluster,
        )
        if not valid:
            raise errors.InvalidData("Network changes during upgrade"
                                     " is not supported.")

        ext_manager.update_extensions_for_object(
            new_cluster.cluster, ['cluster_upgrade']
        )
        return new_cluster.to_dict()


class NodeReassignHandler(base.BaseHandler):
    single = objects.Cluster
    validator = validators.NodeReassignValidator
    task_manager = manager.ProvisioningTaskManager

    def handle_task(self, cluster_id, nodes):
        try:
            task_manager = self.task_manager(cluster_id=cluster_id)
            task = task_manager.execute(nodes)
        except Exception as exc:
            raise self.http(400, msg=six.text_type(exc))

        self.raise_task(task)

    @base.handle_errors
    @base.validate
    def POST(self, cluster_id):
        """Reassign nodes to the given cluster.

        The given nodes will be assigned from the current cluster to the
        given cluster, by default it involves the reprovisioning of the
        nodes. If the 'reprovision' flag is set to False, then the nodes
        will be just reassigned. If the 'roles' list is specified, then
        the given roles will be used as 'pending_roles' in case of
        the reprovisioning or otherwise as 'roles'.

        :param cluster_id: ID of the cluster nodes should be assigned to.
        :returns: None
        :http: * 202 (OK)
               * 400 (Incorrect node state, problem with task execution,
                      conflicting or incorrect roles)
               * 404 (Cluster or node not found)
        """
        cluster = adapters.NailgunClusterAdapter(
            self.get_object_or_404(self.single, cluster_id))

        data = self.checked_data(cluster=cluster)
        reprovision = data.get('reprovision', True)
        given_roles = data.get('roles', [])

        nodes_to_provision = []
        for node_id in data['nodes_ids']:
            node = adapters.NailgunNodeAdapter(
                self.get_object_or_404(objects.Node, node_id))
            nodes_to_provision.append(node.node)

            roles, pending_roles = upgrade.UpgradeHelper.get_node_roles(
                reprovision, node.roles, given_roles)
            upgrade.UpgradeHelper.assign_node_to_cluster(
                node, cluster, roles, pending_roles)

        if reprovision:
            self.handle_task(cluster_id, nodes_to_provision)


class CopyVIPsHandler(base.BaseHandler):
    single = objects.Cluster
    validator = validators.CopyVIPsValidator

    @base.handle_errors
    @base.validate
    @base.serialize
    def POST(self, cluster_id):
        """Copy VIPs from original cluster to new one

        Original cluster object is obtained from existing relation between
        clusters that is created on cluster clone operation

        :param cluster_id: id of cluster that VIPs must be copied to
        :returns: Collection of JSON-serialised VIPs.

        :http: * 200 (OK)
               * 400 (validation failed)
               * 404 (seed cluster is not found)
        """
        from .objects import relations

        cluster = self.get_object_or_404(self.single, cluster_id)
        relation = relations.UpgradeRelationObject.get_cluster_relation(
            cluster.id)

        self.checked_data(cluster=cluster, relation=relation)

        # get original cluster object and create adapter with it
        orig_cluster_adapter = adapters.NailgunClusterAdapter.get_by_uid(
            relation.orig_cluster_id)

        seed_cluster_adapter = adapters.NailgunClusterAdapter(cluster)

        upgrade.UpgradeHelper.copy_vips(orig_cluster_adapter,
                                        seed_cluster_adapter)
        cluster_vips = objects.IPAddrCollection.get_vips_by_cluster_id(
            cluster.id)
        return objects.IPAddrCollection.to_list(cluster_vips)


class CreateUpgradeReleaseHandler(base.BaseHandler):
    @staticmethod
    def merge_network_roles(base_nets, orig_nets):
        """Create network metadata based on two releases.

        Overwrite base default_mapping by orig default_maping values.
        """
        base_nets = copy.deepcopy(base_nets)
        orig_nets = copy.deepcopy(orig_nets)
        orig_network_dict = {n['id']: n for n in orig_nets}
        for base_net in base_nets:
            orig_net = orig_network_dict.get(base_net['id'])
            if orig_net is not None:
                base_net['default_mapping'] = orig_net['default_mapping']
        return base_nets

    @base.serialize
    def POST(self, cluster_id, release_id):
        """Create release for upgrade purposes.

        Creates a new release with network_roles_metadata based the given
        release and re-use network parameters from the given cluster.

        :returns: JSON representation of the created cluster
        :http: * 200 (OK)
               * 404 (Cluster or release not found.)
        """
        base_release = self.get_object_or_404(objects.Release, release_id)
        orig_cluster = self.get_object_or_404(objects.Cluster, cluster_id)
        orig_release = orig_cluster.release
        network_metadata = self.merge_network_roles(
            base_release.network_roles_metadata,
            orig_release.network_roles_metadata)
        data = dict(base_release)
        data['network_roles_metadata'] = network_metadata
        data['name'] = '{0} Upgrade ({1})'.format(
            base_release.name, orig_release.id)
        deployment_tasks = objects.Release.get_deployment_tasks(base_release)
        data['deployment_tasks'] = deployment_tasks
        del data['id']
        new_release = objects.Release.create(data)
        return objects.Release.to_dict(new_release)


class CleanupHandler(base.BaseHandler):
    @base.handle_errors
    def POST(self, cluster_id):
        cluster = self.get_object_or_404(objects.Cluster, cluster_id)
        ext_manager.remove_extensions_from_object(cluster, ['cluster_upgrade'])
