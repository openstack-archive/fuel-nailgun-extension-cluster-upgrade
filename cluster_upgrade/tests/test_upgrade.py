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
import unittest

import six

from nailgun import consts
from nailgun.extensions.network_manager.objects.serializers import \
    network_configuration
from nailgun import objects
from nailgun.test.base import fake_tasks

from .. import upgrade
from . import base as base_tests
from ..objects import adapters
from ..objects import relations


class TestUpgradeHelperCloneCluster(base_tests.BaseCloneClusterTest):

    def setUp(self):
        super(TestUpgradeHelperCloneCluster, self).setUp()

        self.orig_net_manager = self.src_cluster.get_network_manager()

        self.serialize_nets = network_configuration.\
            NeutronNetworkConfigurationSerializer.\
            serialize_for_cluster

        self.public_net_data = {
            "cidr": "192.168.42.0/24",
            "gateway": "192.168.42.1",
            "ip_ranges": [["192.168.42.5", "192.168.42.11"]],
        }

    def test_merge_attributes(self):
        src_editable_attrs = {
            "test":
                {"metadata": "src_fake",
                 "key":
                     {"type": "text",
                      "value": "fake"},
                 "src_key": "src_data"
                 },
            "repo_setup": "src_data"
        }

        new_editable_attrs = {
            "test":
                {"metadata": "new_fake",
                 "key":
                     {"type": "text_list",
                      "value": "fake"},
                 "new_key": "new_data"
                 },
            "repo_setup": "new_data"
        }
        result = upgrade.merge_attributes(
            src_editable_attrs, new_editable_attrs
        )
        self.assertEqual(result, new_editable_attrs)

    def test_create_cluster_clone(self):
        new_cluster = self.helper.create_cluster_clone(self.src_cluster,
                                                       self.data)
        src_cluster_data = self.src_cluster.get_create_data()
        new_cluster_data = new_cluster.get_create_data()
        for key, value in src_cluster_data.items():
            if key in ("name", "release_id"):
                continue
            self.assertEqual(value, new_cluster_data[key])

    def test_copy_attributes(self):
        new_cluster = self.helper.create_cluster_clone(self.src_cluster,
                                                       self.data)
        self.assertNotEqual(self.src_cluster.generated_attrs,
                            new_cluster.generated_attrs)

        # Do some unordinary changes
        attrs = copy.deepcopy(self.src_cluster.editable_attrs)
        attrs["access"]["user"]["value"] = "operator"
        attrs["access"]["password"]["value"] = "secrete"
        self.src_cluster.editable_attrs = attrs

        self.helper.copy_attributes(self.src_cluster, new_cluster)

        self.assertNotEqual(new_cluster.generated_attrs.get('provision'),
                            self.src_cluster.generated_attrs.get('provision'))

        # We make image_data in src_cluster and in new_cluster the same
        # to validate that all other generated attributes are equal
        generated_attrs = copy.deepcopy(self.src_cluster.generated_attrs)
        generated_attrs['provision']['image_data'] = \
            new_cluster.generated_attrs['provision']['image_data']

        self.assertEqual(generated_attrs, new_cluster.generated_attrs)
        editable_attrs = self.src_cluster.editable_attrs
        for section, params in six.iteritems(new_cluster.editable_attrs):
            if section == "repo_setup":
                continue
            for key, value in six.iteritems(params):
                if key == "metadata":
                    continue
                self.assertEqual(editable_attrs[section][key]["value"],
                                 value["value"])

    def update_public_net_params(self, networks):
        pub_net = self._get_pub_net(networks)
        pub_net.update(self.public_net_data)
        self.orig_net_manager.update(networks)

    def _get_pub_net(self, networks):
        return next(net for net in networks['networks'] if
                    net['name'] == consts.NETWORKS.public)

    def test_copy_network_config(self):
        new_cluster = self.helper.create_cluster_clone(self.src_cluster,
                                                       self.data)
        # Do some unordinary changes to public network
        nets = self.serialize_nets(self.src_cluster.cluster)
        self.update_public_net_params(nets)

        self.helper.copy_network_config(self.src_cluster, new_cluster)

        new_nets = self.serialize_nets(new_cluster.cluster)

        public_net = self._get_pub_net(new_nets)

        self.assertEqual(public_net['cidr'], self.public_net_data['cidr'])
        self.assertEqual(public_net['gateway'],
                         self.public_net_data['gateway'])
        self.assertEqual(public_net['ip_ranges'],
                         self.public_net_data['ip_ranges'])

    def test_copy_vips(self):
        # save network information before node reassignment to seed cluster
        # as after that no VIP will be allocated/serialized due to
        # absence of assigned nodes for the source cluster
        orig_nets = self.serialize_nets(self.src_cluster.cluster)

        new_cluster = self.helper.clone_cluster(self.src_cluster, self.data)

        # we have to move node to new cluster before VIP assignment
        # because there is no point in the operation for a cluster
        # w/o nodes
        node = adapters.NailgunNodeAdapter(self.src_cluster.cluster.nodes[0])
        self.helper.assign_node_to_cluster(node, new_cluster, node.roles, [])

        self.helper.copy_vips(self.src_cluster, new_cluster)

        new_nets = self.serialize_nets(new_cluster.cluster)

        self.assertEqual(orig_nets["management_vip"],
                         new_nets["management_vip"])
        self.assertEqual(orig_nets["management_vrouter_vip"],
                         new_nets["management_vrouter_vip"])
        self.assertEqual(orig_nets["public_vip"],
                         new_nets["public_vip"])
        self.assertEqual(orig_nets["public_vrouter_vip"],
                         new_nets["public_vrouter_vip"])

    def test_clone_cluster(self):
        self.orig_net_manager.assign_vips_for_net_groups()
        new_cluster = self.helper.clone_cluster(self.src_cluster, self.data)
        relation = relations.UpgradeRelationObject.get_cluster_relation(
            self.src_cluster.id)
        self.assertEqual(relation.orig_cluster_id, self.src_cluster.id)
        self.assertEqual(relation.seed_cluster_id, new_cluster.id)

    def _check_dns_and_ntp_list_values(self, new_cluster, dns_list, ntp_list):
        self.assertEqual(
            new_cluster.editable_attrs["external_ntp"]["ntp_list"]["value"],
            ntp_list)
        self.assertEqual(
            new_cluster.editable_attrs["external_dns"]["dns_list"]["value"],
            dns_list)
        self.assertEqual(
            new_cluster.editable_attrs["external_ntp"]["ntp_list"]["type"],
            "text_list")
        self.assertEqual(
            new_cluster.editable_attrs["external_dns"]["dns_list"]["type"],
            "text_list")

    def test_cluster_copy_attrs_with_different_types_dns_and_ntp_lists(self):
        attrs = copy.deepcopy(self.src_cluster.editable_attrs)
        attrs["external_ntp"]["ntp_list"]["type"] = "text"
        attrs["external_ntp"]["ntp_list"]["value"] = "1,2,3"
        attrs["external_dns"]["dns_list"]["type"] = "text"
        attrs["external_dns"]["dns_list"]["value"] = "4,5,6"
        self.src_cluster.editable_attrs = attrs
        new_cluster = self.helper.create_cluster_clone(
            self.src_cluster, self.data)
        self.helper.copy_attributes(self.src_cluster, new_cluster)
        self._check_dns_and_ntp_list_values(
            new_cluster, ["4", "5", "6"], ["1", "2", "3"])

    def test_cluster_copy_attrs_with_same_types_dns_and_ntp_lists(self):
        attrs = copy.deepcopy(self.src_cluster.editable_attrs)
        attrs["external_ntp"]["ntp_list"]["type"] = "text_list"
        attrs["external_ntp"]["ntp_list"]["value"] = ["1", "2", "3"]
        attrs["external_dns"]["dns_list"]["type"] = "text_list"
        attrs["external_dns"]["dns_list"]["value"] = ["4", "5", "6"]
        self.src_cluster.editable_attrs = attrs
        new_cluster = self.helper.create_cluster_clone(
            self.src_cluster, self.data)
        self.helper.copy_attributes(self.src_cluster, new_cluster)
        self._check_dns_and_ntp_list_values(
            new_cluster, ["4", "5", "6"], ["1", "2", "3"])

    def test_change_env_settings(self):
        new_cluster = self.helper.create_cluster_clone(self.src_cluster,
                                                       self.data)
        self.helper.copy_attributes(self.src_cluster, new_cluster)
        attrs = new_cluster.attributes
        self.helper.change_env_settings(self.src_cluster, new_cluster)
        self.assertEqual('image',
                         attrs['editable']['provision']['method']['value'])

    def check_different_attributes(self, orig_cluster, new_cluster):
        release = new_cluster.release.id
        nodegroups_id_maping = self.helper.get_nodegroups_id_mapping(
            orig_cluster, new_cluster
        )
        orig_ngs = self.serialize_nets(orig_cluster.cluster)['networks']
        seed_ngs = self.serialize_nets(new_cluster.cluster)['networks']
        for seed_ng in seed_ngs:
            for orig_ng in orig_ngs:
                if orig_ng['name'] == seed_ng['name'] \
                        and orig_ng['name'] != "fuelweb_admin":

                    self.assertEqual(seed_ng['group_id'],
                                     nodegroups_id_maping[orig_ng['group_id']])

                    if seed_ng.get('release'):
                        self.assertEqual(seed_ng['release'], release)

    def skip_different_attributes(self, orig_cluster, new_cluster):
        orig_ngs = self.serialize_nets(orig_cluster.cluster)['networks']
        seed_ngs = self.serialize_nets(new_cluster.cluster)['networks']
        keys = ['release', 'id', 'group_id']
        orig_ngs_names = {ng['name']: ng for ng in orig_ngs}
        for seed_ng in seed_ngs:
            if seed_ng['name'] == 'fuelweb_admin':
                continue
            orig_ng = orig_ngs_names.get(seed_ng['name'])
            if not orig_ng:
                continue
            for key in keys:
                orig_ng.pop(key, None)
                seed_ng.pop(key, None)
        return orig_ngs, seed_ngs

    def test_sync_network_groups(self):
        new_cluster = self.helper.create_cluster_clone(self.src_cluster,
                                                       self.data)
        self.helper.sync_network_groups(self.src_cluster, new_cluster)
        self.check_different_attributes(self.src_cluster, new_cluster)
        orig_ngs, seed_ngs = self.skip_different_attributes(self.src_cluster,
                                                            new_cluster)
        self.assertEqual(orig_ngs, seed_ngs)

    def test_remove_network_groups(self):
        new_cluster = self.helper.create_cluster_clone(self.src_cluster,
                                                       self.data)
        self.helper.remove_network_groups(new_cluster)
        seed_ngs = self.serialize_nets(new_cluster.cluster)['networks']
        self.assertEqual(len(seed_ngs), 1)
        self.assertEqual(seed_ngs[0]['name'], 'fuelweb_admin')

    def test_copy_network_groups(self):
        new_cluster = self.helper.create_cluster_clone(self.src_cluster,
                                                       self.data)
        nodegroups_id_maping = self.helper.get_nodegroups_id_mapping(
            self.src_cluster, new_cluster
        )
        release = new_cluster.release.id
        self.helper.remove_network_groups(new_cluster)
        self.helper.copy_network_groups(self.src_cluster, nodegroups_id_maping,
                                        release)
        self.check_different_attributes(self.src_cluster, new_cluster)
        orig_ngs, seed_ngs = self.skip_different_attributes(self.src_cluster,
                                                            new_cluster)
        self.assertEqual(orig_ngs, seed_ngs)

    def test_change_env_settings_no_editable_provision(self):
        new_cluster = self.helper.create_cluster_clone(self.src_cluster,
                                                       self.data)
        self.helper.copy_attributes(self.src_cluster, new_cluster)
        attrs = new_cluster.attributes
        attrs['editable']['provision']['method']['value'] = 'cobbler'
        self.helper.change_env_settings(self.src_cluster, new_cluster)
        self.assertEqual('image',
                         attrs['editable']['provision']['method']['value'])

    def get_assigned_nets(self, node):
        assigned_nets = {}
        for iface in node.nic_interfaces:
            nets = [net.name for net in iface.assigned_networks_list]
            assigned_nets[iface.name] = nets
        return assigned_nets

    @fake_tasks()
    def assign_node_to_cluster(self, template=None):
        new_cluster = self.helper.clone_cluster(self.src_cluster, self.data)
        node = adapters.NailgunNodeAdapter(self.src_cluster.cluster.nodes[0])

        orig_assigned_nets = self.get_assigned_nets(node)

        if template:
            net_template = self.env.read_fixtures(['network_template_80'])[0]
            new_cluster.network_template = net_template

            orig_assigned_nets = {
                'eth0': ['fuelweb_admin'], 'eth1': ['public', 'management']
            }

        self.db.refresh(node.node)
        self.db.refresh(new_cluster.cluster)
        self.helper.assign_node_to_cluster(node, new_cluster, node.roles, [])
        self.db.refresh(new_cluster.cluster)

        self.assertEqual(node.cluster_id, new_cluster.id)

        self.env.clusters.append(new_cluster.cluster)
        task = self.env.launch_provisioning_selected(cluster_id=new_cluster.id)
        self.assertEqual(task.status, consts.TASK_STATUSES.ready)
        for n in new_cluster.cluster.nodes:
            self.assertEqual(consts.NODE_STATUSES.provisioned, n.status)

        new_assigned_nets = self.get_assigned_nets(node)
        self.assertEqual(orig_assigned_nets, new_assigned_nets)

    def test_assign_node_to_cluster(self):
        self.assign_node_to_cluster()

    @unittest.skip("Test is not correct")
    def test_assign_node_to_cluster_with_template(self):
        self.assign_node_to_cluster(template=True)
