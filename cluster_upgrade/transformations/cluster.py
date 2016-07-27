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


class ClusterTransformation90(object):
    version = '9.0'

    def transform_attributes(self, data):
        editable = self.transform_editable_attributes(
            data['editable'],
        )
        return dict(data, editable=editable)

    def transform_editable_attributes(self, data):
        data = self._transform_dns_list(data)
        data = self._transform_ntp_list(data)
        return data

    def _transform_to_text_list(self, data):
        if data['type'] == 'text':
            data['type'] = 'text_list'
            data['value'] = [
                part.strip() for part in data['value'].split(',')
            ]

        return data

    def _transform_dns_list(self, data):
        dns_list = data['external_dns']['dns_list']
        self._transform_to_text_list(dns_list)
        return data

    def _transform_ntp_list(self, data):
        ntp_list = data['external_ntp']['ntp_list']
        self._transform_to_text_list(ntp_list)
        return data
