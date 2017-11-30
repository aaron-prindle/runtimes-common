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
import os
import unittest
import tempfile
import mock

from ftl.common import context
from ftl.common import test_util
from ftl.php import builder

_COMPOSER_JSON = json.loads("""
{
  "name": "hello-world",
  "require": {
    "php": ">=5.5",
    "silex/silex": "^1.3"
  },
  "require-dev": {
    "behat/mink": "^1.7",
    "behat/mink-goutte-driver": "^1.2",
    "phpunit/phpunit": "~4",
    "symfony/browser-kit": "^3.0",
    "symfony/http-kernel": "^3.0",
    "google/cloud-tools": "^0.6"
  }
}
""")

_COMPOSER_JSON_TEXT = json.dumps(_COMPOSER_JSON)

_APP = """
require_once __DIR__ . '/../vendor/autoload.php';
$app = new Silex\Application();

$app->get('/', function () {
    return 'Hello World';
});
$app->get('/goodbye', function () {
    return 'Goodbye World';
});

// @codeCoverageIgnoreStart
if (PHP_SAPI != 'cli') {
    $app->run();
}
// @codeCoverageIgnoreEnd

return $app;
"""


class PHPTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        current_dir = os.path.dirname(__file__)
        cls.base_image = test_util.TarDockerImage(
            os.path.join(current_dir, "testdata/base_image/config_file"),
            os.path.join(current_dir,
                         "testdata/base_image/distroless-base-latest.tar.gz"))

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self.ctx = context.Memory()
        self.ctx.AddFile("app.php", _APP)
        self.builder = builder.From(self.ctx)

        # Mock out the calls to package managers for speed.
        self.builder.PackageLayer._gen_package_tar = mock.Mock()
        self.builder.PackageLayer._gen_package_tar.return_value = ('layer',
                                                                   'sha')

    def test_create_package_base_no_descriptor(self):
        self.assertFalse(self.ctx.Contains('composer.json'))
        self.assertFalse(self.ctx.Contains('composer-lock.json'))

        layer, sha, overrides = self.builder.PackageLayer(
            self.builder._ctx, None,
            self.builder.descriptor_files, "/app").BuildLayer()

        self.assertIsInstance(layer, str)


if __name__ == '__main__':
    unittest.main()
