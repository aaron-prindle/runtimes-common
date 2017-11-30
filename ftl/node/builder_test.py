# Copyright 2017 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import unittest
import tempfile
import mock

from ftl.common import context
from ftl.node import builder

_PACKAGE_JSON = json.loads("""
{
  "name": "hello-world-express",
  "description": "Hello World test app",
  "version": "0.0.1",
  "private": true,
  "dependencies": {
    "express": "3.x"
  }
}
""")
_PACKAGE_JSON_TEXT = json.dumps(_PACKAGE_JSON)

_APP = """
var express = require('express');
var app = express();

// Routes
app.get('/', function(req, res) {
  res.send('Hello World!');
});

// Listen
var port = process.env.PORT || 3000;
app.listen(port);
console.log('Listening on localhost:'+ port);
"""


class NodeTest(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self.ctx = context.Memory()
        self.ctx.AddFile("app.js", _APP)
        self.builder = builder.From(self.ctx)

        # Mock out the calls to package managers for speed.
        self.builder.PackageLayer._gen_package_tar = mock.Mock()
        self.builder.PackageLayer._gen_package_tar.return_value = ('layer',
                                                                   'sha')

    def test_create_package_base_no_descriptor(self):
        self.assertFalse(self.ctx.Contains('package.json'))
        self.assertFalse(self.ctx.Contains('package-lock.json'))

        layer, sha, overrides = self.builder.PackageLayer(
            self.builder._ctx, None,
            self.builder.descriptor_files, "/app").BuildLayer()

        self.assertIsInstance(layer, str)
        self.assertEqual(overrides.entrypoint, ['sh', '-c', 'node server.js'])

    def test_package_layer_entrypoint(self):
        pj = _PACKAGE_JSON.copy()
        pj['scripts'] = {'start': 'foo bar'}
        self.ctx.AddFile('package.json', json.dumps(pj))

        layer, sha, overrides = self.builder.PackageLayer(
            self.builder._ctx, None,
            self.builder.descriptor_files, "/app").BuildLayer()
        self.assertEqual(overrides.entrypoint, ['sh', '-c', 'foo bar'])

    def test_create_package_base_no_entrypoint(self):
        self.ctx.AddFile('package.json', _PACKAGE_JSON_TEXT)

        layer, sha, overrides = self.builder.PackageLayer(
            self.builder._ctx, None,
            self.builder.descriptor_files, "/app").BuildLayer()
        self.assertEqual(overrides.entrypoint, ['sh', '-c', 'node server.js'])

    def test_create_package_base_prestart(self):
        pj = _PACKAGE_JSON.copy()
        pj['scripts'] = {'prestart': 'foo bar', 'start': 'baz'}
        self.ctx.AddFile('package.json', json.dumps(pj))

        layer, sha, overrides = self.builder.PackageLayer(
            self.builder._ctx, None,
            self.builder.descriptor_files, "/app").BuildLayer()
        self.assertEqual(overrides.entrypoint, ['sh', '-c', 'foo bar && baz'])


if __name__ == '__main__':
    unittest.main()
