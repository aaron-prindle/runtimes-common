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

import unittest
import tempfile
import datetime
import mock

from ftl.common import context
from ftl.python import builder

_REQUIREMENTS_TXT = """
Flask==0.12.0
"""

_APP = """
import os
from flask import Flask
app = Flask(__name__)


@app.route("/")
def hello():
    return "Hello from Python!"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
"""


class PythonTest(unittest.TestCase):
    def setUp(self):
        self.ctx = context.Memory()
        self.ctx.AddFile("app.py", _APP)
        self.builder = builder.From(self.ctx)
        self.builder._pip_install = mock.Mock()
        self.builder._get_pkg_dirs = mock.Mock()
        self.builder._get_pkg_dirs.return_value = \
            [tempfile.mkdtemp()]

        # Mock out the calls to package managers for speed.
        self.builder.PackageLayer._gen_package_tar = mock.Mock()
        self.builder.PackageLayer._gen_package_tar.return_value = ('layer',
                                                                   'sha')

    def test_build_interpreter_layer_ttl_written(self):
        lyr_generator = self.builder.PackageLayerInit(_REQUIREMENTS_TXT)
        # the first layer from python is a cachechecklayer
        lyr_generator.next()
        _, _, overrides = lyr_generator.next().BuildLayer()

        self.assertNotEqual(overrides.creation_time, "1970-01-01T00:00:00Z")
        last_created = _timestamp_to_time(overrides.creation_time)
        now = datetime.datetime.now()
        self.assertTrue(last_created > now - datetime.timedelta(days=2))

    # TODO(aaron-prindle) add test to check expired/unexpired logic for TTL


def _timestamp_to_time(dt_str):
    dt = dt_str.rstrip("Z")
    return datetime.datetime.strptime(dt, "%Y-%m-%dT%H:%M:%S")


if __name__ == '__main__':
    unittest.main()
