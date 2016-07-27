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

from distutils import version
from unittest import case

from .. import transformations


def create_transformation(**kwargs):
    return type('Transformation', (object,), kwargs)


class BaseTransformerTestCase(case.TestCase):

    @classmethod
    def setUpClass(self):
        def method(self, data):
            hist = data.setdefault('history', [])
            hist.append(self)
            return data

        class TestTransformer(transformations.Transformer):
            transformers = (
                create_transformation(version='0.1', foo=method),
                create_transformation(version='1.0', foo=method),
                create_transformation(version='0.4', foo=method),
            )

        self.Transformer = TestTransformer

    def test_transform_order(self):
        transformer = self.Transformer()
        result = transformer.foo({})

        self.assertEqual(
            result['history'],
            sorted(result['history'],
                   key=lambda x: version.StrictVersion(x.version)))

    def test_transform_chain(self):
        transformer = self.Transformer()
        result = transformer.foo({})

        self.assertEqual(len(result['history']), len(transformer.to_apply))

    def _check_version(self, from_version, to_version, result_versions):
        transformer = self.Transformer(from_version=from_version,
                                       to_version=to_version)
        result = transformer.foo({})
        versions = [record.version for record in result.get('history', [])]

        self.assertEqual(versions, result_versions)

    def test_versioning(self):
        self._check_version('0.5', '999.0', ['1.0'])
        self._check_version('0.0', '0.5', ['0.1', '0.4'])
        self._check_version('0.0', '999.0', ['0.1', '0.4', '1.0'])
        self._check_version('998.0', '999.0', [])
        self._check_version('0.0', '0.0.1', [])

    def test_original_data_not_changed(self):
        data = {}
        transformer = self.Transformer()
        result = transformer.foo(data)

        self.assertIsNot(data, result)
        self.assertEqual(data, {})
