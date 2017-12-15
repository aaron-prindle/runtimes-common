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
"""This package defines the interface for orchestrating image builds."""

import os
import subprocess
import tempfile
import logging
import json
import datetime
import hashlib

from containerregistry.transform.v2_2 import metadata

from ftl.common import builder
from ftl.common import ftl_util
from ftl.common import build_layer

_NODE_NAMESPACE = 'node-package-lock-cache'
_PACKAGE_LOCK = 'package-lock.json'
_PACKAGE_JSON = 'package.json'

_DEFAULT_ENTRYPOINT = 'node server.js'


class Node(builder.JustApp):
    def __init__(self, ctx, destination_path):
        self.descriptor_files = [_PACKAGE_LOCK, _PACKAGE_JSON]
        self.namespace = _NODE_NAMESPACE
        self.destination_path = destination_path
        super(Node, self).__init__(ctx)

    def __enter__(self):
        """Override."""
        return self

    def GetBuildLayers(self):
        return self.app_layer
        # descriptor_contents = ftl_util.descriptor_parser(
        #     self.descriptor_files, self._ctx)
        # if descriptor_contents is None:
        #     return [self.app_layer]
        # builder_lyrs = [
        #     self.PackageLayer(self._ctx, None, self.descriptor_files,
        #                       self.destination_path)
        # ]
        # builder_lyrs.append(self.app_layer)
        # return builder_lyrs

    class PackageLayer(build_layer.BaseLayer):
        def __init__(self, ctx, pkg_txt, descriptor_files, destination_path):
            self._ctx = ctx
            self._pkg_txt = pkg_txt
            self._descriptor_files = descriptor_files
            self._destination_path = destination_path

        def GetCacheKey(self):
            descriptor_contents = ftl_util.descriptor_parser(
                self._descriptor_files, self._ctx)

            return hashlib.sha256(descriptor_contents).hexdigest()

        def BuildLayer(self):
            """Override."""
            overrides = self._generate_overrides()

            layer, sha = self._gen_package_tar(self._pkg_txt,
                                               self._destination_path)
            logging.info('Generated layer with sha: %s', sha)
            return layer, sha, overrides

        def _generate_overrides(self):
            pj_contents = {}
            if self._ctx.Contains(_PACKAGE_JSON):
                pj_contents = json.loads(self._ctx.GetFile(_PACKAGE_JSON))
            entrypoint = parse_entrypoint(pj_contents)
            return metadata.Overrides(
                creation_time=str(datetime.date.today()) + "T00:00:00Z",
                entrypoint=entrypoint)

        def _gen_package_tar(self, pkg_txt, destination_path):
            # Create temp directory to write package descriptor to
            pkg_dir = tempfile.mkdtemp()
            app_dir = os.path.join(pkg_dir, destination_path.strip("/"))
            os.makedirs(app_dir)

            # Copy out the relevant package descriptors to a tempdir.
            ftl_util.descriptor_copy(self._ctx, self._descriptor_files,
                                     app_dir)

            check_gcp_build(
                json.loads(self._ctx.GetFile(_PACKAGE_JSON)), app_dir)
            subprocess.check_call(
                ['rm', '-rf',
                 os.path.join(app_dir, 'node_modules')])
            with ftl_util.Timing("npm_install"):
                if pkg_txt is None:
                    subprocess.check_call(
                        ['npm', 'install', '--production'], cwd=app_dir)
                else:
                    subprocess.check_call(
                        ['npm', 'install', '--production', pkg_txt],
                        cwd=app_dir)

            return ftl_util.zip_dir_to_layer_sha(pkg_dir)


def check_gcp_build(package_json, app_dir):
    scripts = package_json.get('scripts', {})
    gcp_build = scripts.get('gcp-build')

    if not gcp_build:
        return

    env = os.environ.copy()
    env["NODE_ENV"] = "development"
    subprocess.check_call(['npm', 'install'], cwd=app_dir, env=env)
    subprocess.check_call(
        ['npm', 'run-script', 'gcp-build'], cwd=app_dir, env=env)


def parse_entrypoint(package_json):
    entrypoint = []

    scripts = package_json.get('scripts', {})
    start = scripts.get('start', _DEFAULT_ENTRYPOINT)
    prestart = scripts.get('prestart')

    if prestart:
        entrypoint = '%s && %s' % (prestart, start)
    else:
        entrypoint = start
    return ['sh', '-c', entrypoint]


def From(ctx, destination_path='/app'):
    return Node(ctx, destination_path)
