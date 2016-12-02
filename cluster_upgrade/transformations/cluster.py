# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from cluster_upgrade import transformations

# NOTE: In the mitaka-9.0 release types of values dns_list and
# ntp_list were changed from 'text'
# (a string of comma-separated IP-addresses)
# to 'text_list' (a list of strings of IP-addresses).


def transform_to_text_list(data):
    if data['type'] == 'text':
        data['type'] = 'text_list'
        data['value'] = [
            part.strip() for part in data['value'].split(',')
        ]

    return data


def transform_dns_list(data):
    dns_list = data['editable']['external_dns']['dns_list']
    transform_to_text_list(dns_list)
    return data


def transform_ntp_list(data):
    ntp_list = data['editable']['external_ntp']['ntp_list']
    transform_to_text_list(ntp_list)
    return data


def drop_generated_provision(data):
    data['generated'].pop('provision', None)
    return data


def enable_ibp(data):
    data['editable']['provision']['method']['value'] = 'image'


class Manager(transformations.Manager):
    default_config = {
        '9.0': ['dns_list', 'ntp_list', 'drop_provision'],
        '6.1': ['image_provision'],
    }
    name = 'cluster'
