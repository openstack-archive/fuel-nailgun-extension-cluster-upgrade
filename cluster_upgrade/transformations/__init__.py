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

import copy
import distutils.version
import logging
import threading

import six

import stevedore

LOG = logging.getLogger(__name__)


def reraise_endpoint_load_failure(manager, endpoint, exc):
    LOG.error('Failed to load %s: %s', endpoint.name, exc)
    raise  # Avoid unexpectedly skipped steps


class Manager(object):
    default_config = None
    name = None

    def __init__(self):
        self.config = self.get_config(self.name)
        self.transformers = self.load_transformers(self.name, self.config)

    @classmethod
    def get_config(cls, name):
        # TODO(yorik-sar): merge actual config with defaults
        return cls.default_config

    @staticmethod
    def load_transformers(name, config):
        transformers = []
        for version, names in six.iteritems(config):
            extension_manager = stevedore.ExtensionManager(
                'nailgun.cluster_upgrade.transformations.{}.{}'.format(
                    name, version),
                on_load_failure_callback=reraise_endpoint_load_failure,
            )
            try:
                sorted_extensions = [extension_manager[n].plugin
                                     for n in names]
            except KeyError as exc:
                LOG.error('%s transformer %s not found for version %s',
                          name, exc, version)
                raise
            strict_version = distutils.version.StrictVersion(version)
            transformers.append((strict_version, sorted_extensions))
        transformers.sort()
        return transformers

    def apply(self, from_version, to_version, data):
        strict_from = distutils.version.StrictVersion(from_version)
        strict_to = distutils.version.StrictVersion(to_version)
        assert strict_from <= strict_to, \
            "from_version must not be greater than to_version"
        data = copy.deepcopy(data)
        for version, transformers in self.transformers:
            if version <= strict_from:
                continue
            if version > strict_to:
                break
            for transformer in transformers:
                LOG.debug("Applying %s transformer %s",
                          self.name, transformer)
                data = transformer(data)
        return data


class Lazy(object):
    def __init__(self, mgr_cls):
        self.mgr_cls = mgr_cls
        self.mgr = None
        self.lock = threading.Lock()

    def apply(self, *args, **kwargs):
        if self.mgr is None:
            with self.lock:
                if self.mgr is None:
                    self.mgr = self.mgr_cls()
                    self.apply = self.mgr.apply
        return self.mgr.apply(*args, **kwargs)
