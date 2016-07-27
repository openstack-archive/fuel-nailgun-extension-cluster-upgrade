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

import copy

from distutils.version import StrictVersion

from . import cluster


def create_transformer(cls_name, *classes):
    transformers = sorted(classes, key=lambda x: StrictVersion(x.version))

    class Transformer(object):
        def __init__(self, from_version='0.0', to_version='999999.0'):
            from_version = StrictVersion(from_version)
            to_version = StrictVersion(to_version)

            self.to_apply = [
                tr() for tr in transformers
                if from_version < StrictVersion(tr.version) <= to_version
            ]

        def __getattr__(self, name):
            def inner(data, *args, **kwargs):
                data = copy.deepcopy(data)

                called = False
                for tr in self.to_apply:
                    if hasattr(tr, name):
                        called = True
                        data = getattr(tr, name)(data, *args, **kwargs)

                if not called:
                    raise AttributeError(
                        "{} has no attribute '{}'".format(cls_name, name)
                    )
                return data
            return inner
    return Transformer


ClusterTransformer = create_transformer(
    'ClusterTransformer',
    cluster.ClusterTransformation90,
)
