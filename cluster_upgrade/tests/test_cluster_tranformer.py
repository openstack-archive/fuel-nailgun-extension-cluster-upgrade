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

from unittest import case

import six

from .. import transformations


class ClusterTransformationTestCase(case.TestCase):
    def _check_type_and_value(self, old, new):
        self.assertTrue(
            old['type'] == 'text' and
            new['type'] == 'text_list' and
            isinstance(old['value'], six.string_types) and
            isinstance(new['value'], list)
        )

    def test_dns_transform(self):
        data = {'external_dns':
                {'dns_list': {'type': 'text', 'value': '8.8.8.8, 8.8.4.4'}}}
        tr = transformations.ClusterTransformer('8.9', '9.0')
        res = tr._transform_dns_list(data)
        self._check_type_and_value(data['external_dns']['dns_list'],
                                   res['external_dns']['dns_list'])
        self.assertEqual(res['external_dns']['dns_list']['value'],
                         ['8.8.8.8', '8.8.4.4'])

    def test_ntp_transform(self):
        data = {'external_ntp':
                {'ntp_list': {'type': 'text',
                              'value': 'ntp.example.com, time.nist.gov'}}}
        tr = transformations.ClusterTransformer('8.9', '9.0')
        res = tr._transform_ntp_list(data)
        self._check_type_and_value(data['external_ntp']['ntp_list'],
                                   res['external_ntp']['ntp_list'])
        self.assertEqual(
            res['external_ntp']['ntp_list']['value'],
            ['ntp.example.com', 'time.nist.gov'],
        )
