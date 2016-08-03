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


class VolumesTransformation61(object):
    version = '6.1'

    def transform_node_volumes(self, volumes):
        try:
            os_vg = next(vol for vol in volumes
                         if 'id' in vol and vol['id'] == 'os')
        except StopIteration:
            return volumes

        other_volumes = [vol for vol in volumes
                         if 'id' not in vol or vol['id'] != 'os']

        for disk in other_volumes:
            disk_volumes = disk['volumes']
            disk['volumes'] = []

            for v in disk_volumes:
                if v['type'] == 'pv' and v['vg'] == 'os' and v['size'] > 0:
                    for vv in os_vg['volumes']:
                        partition = {'name': vv['name'],
                                     'size': vv['size'],
                                     'type': 'partition',
                                     'mount': vv['mount'],
                                     'file_system': vv['file_system']}
                        disk['volumes'].append(partition)
                else:
                    if v['type'] == 'lvm_meta_pool' or v['type'] == 'boot':
                        v['size'] = 0
                    disk['volumes'].append(v)

        return volumes
