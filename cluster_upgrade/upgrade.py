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

import collections
import six

from nailgun import consts
from nailgun.extensions.network_manager.objects.serializers import \
    network_configuration
from nailgun import objects
from nailgun import utils

from . import transformations  # That's weird, but that's how hacking likes
from .objects import adapters
from .transformations import cluster as cluster_trs
from .transformations import vip
from .transformations import volumes as volumes_trs


def merge_attributes(a, b):
    """Merge values of editable attributes.

    The values of the b attributes have precedence over the values
    of the a attributes.
    """
    attrs = copy.deepcopy(b)
    for section, pairs in six.iteritems(attrs):
        if section == "repo_setup" or section not in a:
            continue
        a_values = a[section]
        for key, values in six.iteritems(pairs):
            if key != "metadata" and key in a_values:
                values["value"] = a_values[key]["value"]
    return attrs


def get_net_key(net):
    group_name = None
    if net["group_id"]:
        group_name = objects.NodeGroup.get_by_uid(net["group_id"]).name
    return (net["name"], group_name)


def merge_nets(a, b):
    new_settings = copy.deepcopy(b)
    source_networks = dict((get_net_key(net), net) for net in a["networks"])

    for net in new_settings["networks"]:
        net_key = get_net_key(net)
        if net_key not in source_networks:
            continue
        source_net = source_networks[net_key]
        for key, value in six.iteritems(net):
            if (key not in ("cluster_id", "id", "meta", "group_id") and
                    key in source_net):
                net[key] = source_net[key]
    networking_params = new_settings["networking_parameters"]
    source_params = a["networking_parameters"]
    for key, value in six.iteritems(networking_params):
        if key not in source_params:
            continue
        networking_params[key] = source_params[key]
    return new_settings


class UpgradeHelper(object):
    network_serializers = {
        consts.CLUSTER_NET_PROVIDERS.neutron:
        network_configuration.NeutronNetworkConfigurationSerializer,
        consts.CLUSTER_NET_PROVIDERS.nova_network:
        network_configuration.NovaNetworkConfigurationSerializer,
    }
    cluster_transformations = transformations.Lazy(cluster_trs.Manager)
    vip_transformations = transformations.Lazy(vip.Manager)
    volumes_transformations = transformations.Lazy(volumes_trs.Manager)

    @classmethod
    def clone_cluster(cls, orig_cluster, data):
        from .objects import relations

        new_cluster = cls.create_cluster_clone(orig_cluster, data)
        cls.copy_attributes(orig_cluster, new_cluster)
        cls.copy_node_groups(orig_cluster, new_cluster)
        cls.copy_network_config(orig_cluster, new_cluster)
        relations.UpgradeRelationObject.create_relation(orig_cluster.id,
                                                        new_cluster.id)
        cls.change_env_settings(orig_cluster, new_cluster)
        return new_cluster

    @classmethod
    def create_cluster_clone(cls, orig_cluster, data):
        create_data = orig_cluster.get_create_data()
        create_data["name"] = data["name"]
        create_data["release_id"] = data["release_id"]
        new_cluster = adapters.NailgunClusterAdapter.create(create_data)
        return new_cluster

    @classmethod
    def copy_attributes(cls, orig_cluster, new_cluster):
        attrs = cls.cluster_transformations.apply(
            orig_cluster.release.environment_version,
            new_cluster.release.environment_version,
            {
                'editable': orig_cluster.editable_attrs,
                'generated': orig_cluster.generated_attrs,
            },
        )

        new_cluster.generated_attrs = utils.dict_merge(
            new_cluster.generated_attrs,
            attrs['generated'],
        )

        new_cluster.editable_attrs = merge_attributes(
            attrs['editable'],
            new_cluster.editable_attrs,
        )

    @classmethod
    def change_env_settings(cls, orig_cluster, new_cluster):
        attrs = new_cluster.attributes
        attrs['editable']['provision']['method']['value'] = 'image'

    @classmethod
    def copy_node_groups(cls, orig_cluster, new_cluster):
        for ng in orig_cluster.node_groups:
            if getattr(ng, 'is_default', False) or ng.name == 'default':
                continue

            data = {
                'name': ng.name,
                'cluster_id': new_cluster.id
            }
            objects.NodeGroup.create(data)

    @classmethod
    def copy_network_config(cls, orig_cluster, new_cluster):
        nets_serializer = cls.network_serializers[orig_cluster.net_provider]
        nets = merge_nets(
            nets_serializer.serialize_for_cluster(orig_cluster.cluster),
            nets_serializer.serialize_for_cluster(new_cluster.cluster))

        new_net_manager = new_cluster.get_network_manager()

        new_net_manager.update(nets)

    @classmethod
    def copy_vips(cls, orig_cluster, new_cluster):
        orig_net_manager = orig_cluster.get_network_manager()
        new_net_manager = new_cluster.get_network_manager()

        vips = orig_net_manager.get_assigned_vips(
            include=(consts.NETWORKS.public, consts.NETWORKS.management))

        netgroups_id_mapping = cls.get_netgroups_id_mapping(orig_cluster,
                                                            new_cluster)
        new_vips = cls.reassociate_vips(vips, netgroups_id_mapping)

        new_vips = cls.vip_transformations.apply(
            orig_cluster.release.environment_version,
            new_cluster.release.environment_version,
            new_vips
        )
        new_net_manager.assign_given_vips_for_net_groups(new_vips)
        new_net_manager.assign_vips_for_net_groups()

    @classmethod
    def reassociate_vips(cls, vips, netgroups_id_mapping):
        new_vips = collections.defaultdict(dict)
        for orig_net_id, net_vips in vips.items():
            new_net_id = netgroups_id_mapping[orig_net_id]
            new_vips[new_net_id] = net_vips
        return new_vips

    @classmethod
    def get_node_roles(cls, reprovision, current_roles, given_roles):
        """Return roles depending on the reprovisioning status.

        In case the node should be re-provisioned, only pending roles
        should be set, otherwise for an already provisioned and deployed
        node only actual roles should be set. In the both case the
        given roles will have precedence over the existing.

        :param reprovision: boolean, if set to True then the node should
                            be re-provisioned
        :param current_roles: a list of current roles of the node
        :param given_roles: a list of roles that should be assigned to
                            the node
        :returns: a tuple of a list of roles and a list of pending roles
                  that will be assigned to the node
        """
        roles_to_assign = given_roles if given_roles else current_roles
        if reprovision:
            roles, pending_roles = [], roles_to_assign
        else:
            roles, pending_roles = roles_to_assign, []
        return roles, pending_roles

    @classmethod
    def assign_node_to_cluster(cls, node, seed_cluster, roles, pending_roles):
        orig_cluster = adapters.NailgunClusterAdapter.get_by_uid(
            node.cluster_id)

        volumes = cls.volumes_transformations.apply(
            orig_cluster.release.environment_version,
            seed_cluster.release.environment_version,
            node.get_volumes(),
        )
        node.set_volumes(volumes)

        orig_manager = orig_cluster.get_network_manager()

        netgroups_id_mapping = cls.get_netgroups_id_mapping(
            orig_cluster, seed_cluster)

        node.update_cluster_assignment(seed_cluster, roles, pending_roles)
        objects.Node.set_netgroups_ids(node, netgroups_id_mapping)

        if not seed_cluster.network_template:
            orig_manager.set_nic_assignment_netgroups_ids(
                node, netgroups_id_mapping)
            orig_manager.set_bond_assignment_netgroups_ids(
                node, netgroups_id_mapping)

        node.add_pending_change(consts.CLUSTER_CHANGES.interfaces)

    @classmethod
    def get_netgroups_id_mapping(self, orig_cluster, seed_cluster):
        orig_ng = orig_cluster.get_network_groups()
        seed_ng = seed_cluster.get_network_groups()

        seed_ng_dict = dict(((ng.name, ng.nodegroup.name), ng.id)
                            for ng in seed_ng)
        mapping = dict((ng.id, seed_ng_dict[(ng.name, ng.nodegroup.name)])
                       for ng in orig_ng)
        mapping[orig_cluster.get_admin_network_group().id] = \
            seed_cluster.get_admin_network_group().id
        return mapping
