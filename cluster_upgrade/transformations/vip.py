# coding: utf-8

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

import collections

from cluster_upgrade import transformations


def transform_vips(data):
    """Rename or remove types of VIPs for 7.0 network groups.

    This method renames types of VIPs from older releases (<7.0) to
    be compatible with network groups of the 7.0 release according
    to the rules:

        management: haproxy -> management
        public: haproxy -> public
        public: vrouter -> vrouter_pub

    Note, that in the result VIPs are present only those IPs that
    correspond to the given rules.
    """
    rename_vip_rules = {
        "management": {
            "haproxy": "management",
            "vrouter": "vrouter",
        },
        "public": {
            "haproxy": "public",
            "vrouter": "vrouter_pub",
        },
    }
    vip_ns_rules = {
        "vrouter": "vrouter",
        "vrouter_pub": "vrouter",
        "public": "haproxy",
        "management": "haproxy",
    }
    renamed_vips = collections.defaultdict(dict)
    vips, id_name_mapping = data
    for ng_id, vips_obj in vips.items():
        ng_vip_rules = rename_vip_rules[id_name_mapping[ng_id]]
        for vip_name, vip_addr in vips_obj.items():
            if vip_name not in ng_vip_rules:
                continue

            new_vip_name = ng_vip_rules[vip_name]
            renamed_vips[ng_id][new_vip_name] = vip_addr
            # When migrating from 6.x, vip_namespace key is not set for
            # public/management vips
            if 'vip_namespace' not in renamed_vips[ng_id][new_vip_name] and \:
                new_vip_name in vip_ns_rules:
                vip_ns = vip_ns_rules[new_vip_name]
                renamed_vips[ng_id][new_vip_name]['vip_namespace'] = vip_ns

    return renamed_vips, id_name_mapping


class Manager(transformations.Manager):
    default_config = {
        '7.0': ['transform_vips']
    }
    name = 'vip'
