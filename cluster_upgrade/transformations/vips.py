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


class VipsTransformation70(object):
    version = '7.0'

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
        renamed_vips = collections.defaultdict(dict)
        for ng_name, vips_obj in data.items():

            ng_vip_rules = rename_vip_rules[ng_name]
            for vip_name, vip_addr in vips_obj.items():
                if vip_name not in ng_vip_rules:
                    continue

                new_vip_name = ng_vip_rules[vip_name]
                renamed_vips[ng_name][new_vip_name] = vip_addr

        return renamed_vips
