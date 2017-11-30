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
import datetime
import hashlib

from containerregistry.transform.v2_2 import metadata

from ftl.common import builder
from ftl.common import ftl_util
from ftl.common import build_layer

_PYTHON_NAMESPACE = 'python-requirements-cache'
_REQUIREMENTS_TXT = 'requirements.txt'
_VENV_DIR = 'env'
_TMP_APP = 'app'
_WHEEL_DIR = 'wheel'


class Python(builder.JustApp):
    def __init__(self, ctx, python_version):
        self.descriptor_files = [_REQUIREMENTS_TXT]
        # TODO(aaron-prindle) map  python_version to interpreter_parser
        # will prob need to pass in args to the builder
        self.pkg_txt_parser = ftl_util.descriptor_parser  # detect phase here
        self.namespace = _PYTHON_NAMESPACE
        self._venv_dir = self._gen_tmp_dir(_VENV_DIR)
        self._wheel_dir = self._gen_tmp_dir(_WHEEL_DIR)
        self.python_version = python_version
        super(Python, self).__init__(ctx)

    def __enter__(self):
        """Override."""
        return self

    def _generate_overrides(self, set_path):
        env = {
            "VIRTUAL_ENV": "/env",
        }
        if set_path:
            env['PATH'] = '/env/bin:$PATH'
        return metadata.Overrides(
            creation_time=str(datetime.date.today()) + "T00:00:00Z", env=env)

    def GetBuildLayers(self):
        pkg_txts = ftl_util.descriptor_parser(self.descriptor_files, self._ctx)
        yield self.InterpreterLayer(self._venv_dir, self._generate_overrides,
                                    self.python_version)
        for layer in self.PackageLayerInit(pkg_txts):
            yield layer
        yield self.AppLayer(self._ctx)

    class InterpreterLayer(build_layer.BaseLayer):
        def __init__(self, venv_dir, overrides_fxn, python_version):
            self._venv_dir = venv_dir
            self._generate_overrides = overrides_fxn
            self.python_version = python_version

        def GetCacheKey(self):
            return self.python_version

        def BuildLayer(self):
            self._setup_venv(self.python_version)
            layer, sha = ftl_util.zip_dir_to_layer_sha(
                os.path.abspath(os.path.join(self._venv_dir, os.pardir)))
            return layer, sha, self._generate_overrides(True)

        def _setup_venv(self, python_version):
            with ftl_util.Timing("create_virtualenv"):
                subprocess.check_call([
                    'virtualenv', '--no-download', self._venv_dir, '-p',
                    python_version
                ])

    def PackageLayerInit(self, pkg_txts):
        # need to yield 'dummy' layer to check cache
        cache_check_layer = build_layer.CacheCheckLayer(
            self._ctx, self.descriptor_files)
        yield cache_check_layer
        if not cache_check_layer.was_cached:
            self._pip_install(pkg_txts)
            for pkg_dir in self._get_pkg_dirs():
                yield self.PackageLayer(self._ctx,
                                        pkg_dir,
                                        self.descriptor_files,
                                        self._generate_overrides)

    def _get_pkg_dirs(self):
        whls = self._resolve_whls()
        return [self._whl_to_fslayer(whl) for whl in whls]

    class PackageLayer(build_layer.BaseLayer):
        def __init__(self, ctx, pkg_dir, descriptor_files, overrides_fxn):
            self._ctx = ctx
            self._pkg_dir = pkg_dir
            self._descriptor_files = descriptor_files
            self._overrides_fxn = overrides_fxn

        def GetCacheKey(self):
            descriptor_contents = ftl_util.descriptor_parser(
                self._descriptor_files, self._ctx)
            return hashlib.sha256(descriptor_contents).hexdigest()

        def BuildLayer(self):
            layer, sha = ftl_util.zip_dir_to_layer_sha(self._pkg_dir)
            return layer, sha, self._overrides_fxn(False)

    def _resolve_whls(self):
        return [
            os.path.join(self._wheel_dir, f)
            for f in os.listdir(self._wheel_dir)
        ]

    def _whl_to_fslayer(self, whl):
        tmp_dir = tempfile.mkdtemp()
        pkg_dir = os.path.join(tmp_dir, 'env')
        os.makedirs(pkg_dir)
        subprocess.check_call(
            ['pip', 'install', '--prefix', pkg_dir, whl],
            env=self._gen_pip_env())
        return tmp_dir

    def _gen_pip_env(self):
        pip_env = os.environ.copy()
        # bazel adds its own PYTHONPATH to the env
        # which must be removed for the pip calls to work properly
        del pip_env['PYTHONPATH']
        pip_env['VIRTUAL_ENV'] = self._venv_dir
        pip_env['PATH'] = self._venv_dir + "/bin" + ":" + os.environ['PATH']
        return pip_env

    def _pip_install(self, pkg_txt):
        with ftl_util.Timing("pip_install_wheels"):
            args = ['pip', 'wheel', '-w', self._wheel_dir, '-r', "/dev/stdin"]

            pipe1 = subprocess.Popen(
                args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=self._gen_pip_env(), )
            pipe1.communicate(input=pkg_txt)[0]

    def _gen_tmp_dir(self, dirr):
        tmp_dir = tempfile.mkdtemp()
        dir_name = os.path.join(tmp_dir, dirr)
        os.mkdir(dir_name)
        return dir_name


def From(ctx, python_version='python2.7'):
    return Python(ctx, python_version)
