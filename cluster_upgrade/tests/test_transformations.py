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
from distutils import version

import mock
from nailgun.test import base as nailgun_test_base
import six

from .. import transformations
from ..transformations import cluster
from ..transformations import vip


class TestTransformations(nailgun_test_base.BaseUnitTest):
    def test_get_config(self):
        config = object()

        class Manager(transformations.Manager):
            default_config = config

        self.assertIs(config, Manager.get_config('testname'))

    def setup_extension_manager(self, extensions):
        p = mock.patch("stevedore.ExtensionManager", spec=['__call__'])
        mock_extman = p.start()
        self.addCleanup(p.stop)

        def extman(namespace, *args, **kwargs):
            instance = mock.MagicMock(name=namespace)
            ext_results = {}
            for ver, exts in six.iteritems(extensions):
                if namespace.endswith(ver):
                    ext_results = {name: mock.Mock(name=name, plugin=ext)
                                   for name, ext in six.iteritems(exts)}
                    break
            else:
                self.fail("Called with unexpected version in namespace: {}, "
                          "expected versions: {}".format(
                              namespace, list(extensions)))
            instance.__getitem__.side_effect = ext_results.__getitem__
            return instance

        mock_extman.side_effect = extman
        return mock_extman

    def test_load_transformers(self):
        config = {'9.0': ['a', 'b']}
        extensions = {'9.0': {
            'a': mock.Mock(name='a'),
            'b': mock.Mock(name='b'),
        }}
        mock_extman = self.setup_extension_manager(extensions)

        res = transformations.Manager.load_transformers('testname', config)

        self.assertEqual(res, [(version.StrictVersion('9.0'), [
            extensions['9.0']['a'],
            extensions['9.0']['b'],
        ])])
        callback = transformations.reraise_endpoint_load_failure
        self.assertEqual(mock_extman.mock_calls, [
            mock.call(
                'nailgun.cluster_upgrade.transformations.testname.9.0',
                on_load_failure_callback=callback,
            ),
        ])

    def test_load_transformers_empty(self):
        config = {}
        extensions = {'9.0': {
            'a': mock.Mock(name='a'),
            'b': mock.Mock(name='b'),
        }}
        mock_extman = self.setup_extension_manager(extensions)

        res = transformations.Manager.load_transformers('testname', config)

        self.assertEqual(res, [])
        self.assertEqual(mock_extman.mock_calls, [])

    def test_load_transformers_sorted(self):
        config = {'9.0': ['a', 'b'], '8.0': ['c']}
        extensions = {
            '9.0': {
                'a': mock.Mock(name='a'),
                'b': mock.Mock(name='b'),
            },
            '8.0': {
                'c': mock.Mock(name='c'),
                'd': mock.Mock(name='d'),
            },
        }
        mock_extman = self.setup_extension_manager(extensions)

        orig_iteritems = six.iteritems
        iteritems_patch = mock.patch('six.iteritems')
        mock_iteritems = iteritems_patch.start()
        self.addCleanup(iteritems_patch.stop)

        def sorted_iteritems(d):
            return sorted(orig_iteritems(d), reverse=True)

        mock_iteritems.side_effect = sorted_iteritems

        res = transformations.Manager.load_transformers('testname', config)

        self.assertEqual(res, [
            (version.StrictVersion('8.0'), [
                extensions['8.0']['c'],
            ]),
            (version.StrictVersion('9.0'), [
                extensions['9.0']['a'],
                extensions['9.0']['b'],
            ]),
        ])
        callback = transformations.reraise_endpoint_load_failure
        self.assertItemsEqual(mock_extman.mock_calls, [
            mock.call(
                'nailgun.cluster_upgrade.transformations.testname.9.0',
                on_load_failure_callback=callback,
            ),
            mock.call(
                'nailgun.cluster_upgrade.transformations.testname.8.0',
                on_load_failure_callback=callback,
            ),
        ])

    def test_load_transformers_keyerror(self):
        config = {'9.0': ['a', 'b', 'c']}
        extensions = {'9.0': {
            'a': mock.Mock(name='a'),
            'b': mock.Mock(name='b'),
        }}
        mock_extman = self.setup_extension_manager(extensions)

        with self.assertRaisesRegexp(KeyError, 'c'):
            transformations.Manager.load_transformers('testname', config)

        callback = transformations.reraise_endpoint_load_failure
        self.assertEqual(mock_extman.mock_calls, [
            mock.call(
                'nailgun.cluster_upgrade.transformations.testname.9.0',
                on_load_failure_callback=callback,
            ),
        ])

    @mock.patch.object(transformations.Manager, 'load_transformers')
    def test_apply(self, mock_load):
        mock_trans = mock.Mock()
        mock_load.return_value = [
            (version.StrictVersion('7.0'), [mock_trans.a, mock_trans.b]),
            (version.StrictVersion('8.0'), [mock_trans.c, mock_trans.d]),
            (version.StrictVersion('9.0'), [mock_trans.e, mock_trans.f]),
        ]
        man = transformations.Manager()
        res = man.apply('7.0', '9.0', {})
        self.assertEqual(res, mock_trans.f.return_value)
        self.assertEqual(mock_trans.mock_calls, [
            mock.call.c({}),
            mock.call.d(mock_trans.c.return_value),
            mock.call.e(mock_trans.d.return_value),
            mock.call.f(mock_trans.e.return_value),
        ])


class TestLazy(nailgun_test_base.BaseUnitTest):
    def test_lazy(self):
        mgr_cls_mock = mock.Mock()
        lazy_obj = transformations.Lazy(mgr_cls_mock)
        lazy_obj.apply()
        self.assertEqual(lazy_obj.apply, mgr_cls_mock.return_value.apply)


class TestClusterTransformers(nailgun_test_base.BaseUnitTest):
    def setUp(self):
        self.data = {
            'editable': {
                'external_dns': {
                    'dns_list': {'type': 'text', 'value': 'a,b,\nc, d'}},
                'external_ntp': {
                    'ntp_list': {'type': 'text', 'value': 'a,b,\nc, d'}},
            },
            'generated': {
                'provision': {},
            },
        }

    def test_dns_list(self):
        res = cluster.transform_dns_list(self.data)
        self.assertEqual(
            res['editable']['external_dns']['dns_list'],
            {'type': 'text_list', 'value': ['a', 'b', 'c', 'd']},
        )

    def test_ntp_list(self):
        res = cluster.transform_ntp_list(self.data)
        self.assertEqual(
            res['editable']['external_ntp']['ntp_list'],
            {'type': 'text_list', 'value': ['a', 'b', 'c', 'd']},
        )

    def test_provision(self):
        res = cluster.drop_generated_provision(self.data)
        self.assertNotIn('provision', res['generated'])

    def test_manager(self):
        man = cluster.Manager()  # verify default config and entry points
        self.assertEqual(man.transformers, [(version.StrictVersion('9.0'), [
            cluster.transform_dns_list,
            cluster.transform_ntp_list,
            cluster.drop_generated_provision,
        ])])


class TestVipTransformers(nailgun_test_base.BaseUnitTest):
    def setUp(self):
        ip = '0.0.0.0'
        self.data = {
            1: {
                'haproxy': ip,
                'vrouter': ip,
                'test': ip,
            },
            2: {
                'haproxy': ip,
                'vrouter': ip,
                'test': ip,
            }
        }
        self.mapping = {1: 'management', 2: 'public'}

    def test_vip_transform(self):
        ip = '0.0.0.0'

        data = vip.transform_vips((self.data, self.mapping))
        self.assertEqual(
            data, ({
                1: {
                    'management': ip,
                    'vrouter': ip,
                },
                2: {
                    'public': ip,
                    'vrouter_pub': ip,
                }}, {1: 'management', 2: 'public'})
        )
