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

import logging
import os
import subprocess
import tempfile

from ftl.common import builder
from ftl.common import ftl_util
from ftl.common import layer_builder as base_builder
from ftl.python import layer_builder as package_builder

_VENV_DIR = 'env'
_WHEEL_DIR = 'wheel'
_THREADS = 32
_REQUIREMENTS_TXT = 'requirements.txt'
_PYTHON_NAMESPACE = 'python-requirements-cache'


class Python(builder.RuntimeBase):
    def __init__(self, ctx, args, cache_version_str):
        super(Python, self).__init__(ctx, _PYTHON_NAMESPACE, args,
                                     cache_version_str, [_REQUIREMENTS_TXT])
        self._venv_dir = ftl_util.gen_tmp_dir(_VENV_DIR)
        self._wheel_dir = ftl_util.gen_tmp_dir(_WHEEL_DIR)
        self._python_cmd = args.python_cmd.split(" ")
        self._pip_cmd = args.pip_cmd.split(" ")
        self._venv_cmd = args.venv_cmd.split(" ")

    def Build(self):
        lyr_imgs = []
        lyr_imgs.append(self._base_image)

        if ftl_util.has_pkg_descriptor(self._descriptor_files, self._ctx):
            # check cache or build interpreter layer
            interpreter_builder = package_builder.InterpreterLayerBuilder(
                self._venv_dir, self._python_cmd, self._venv_cmd)
            cached_int_img = None
            if self._args.cache:
                with ftl_util.Timing("checking cached interpreter layer"):
                    key = interpreter_builder.GetCacheKey()
                    cached_int_img = self._cache.Get(key)
            if cached_int_img is not None:
                interpreter_builder.SetImage(cached_int_img)
            else:
                with ftl_util.Timing("building interpreter layer"):
                    interpreter_builder.BuildLayer()
                if self._args.cache:
                    with ftl_util.Timing("uploading interpreter layer"):
                        self._cache.Set(interpreter_builder.GetCacheKey(),
                                        interpreter_builder.GetImage())
            lyr_imgs.append(interpreter_builder.GetImage())

            # check cache or build package layers
            req_txt_builder = package_builder.PackageLayerBuilder(
                self._ctx, self._descriptor_files, None,
                interpreter_builder)
            cached_req_txt_img = None
            if self._args.cache:
                with ftl_util.Timing("checking cached req.txt layer"):
                    key = req_txt_builder.GetCacheKey()
                    cached_req_txt_img = self._cache.Get(key)
            if cached_req_txt_img is not None:
                req_txt_builder.SetImage(cached_req_txt_img)
            else:
                with ftl_util.Timing("installing pip packages"):
                    pkg_descriptor = ftl_util.descriptor_parser(
                        self._descriptor_files, self._ctx)
                    self._pip_install(pkg_descriptor)

                with ftl_util.Timing("resolving whl paths"):
                    whls = self._resolve_whls()
                    pkg_dirs = [self._whl_to_fslayer(whl) for whl in whls]

                req_txt_imgs = []
                for whl_pkg_dir in pkg_dirs:
                    layer_builder = package_builder.PackageLayerBuilder(
                        self._ctx, self._descriptor_files, whl_pkg_dir,
                        interpreter_builder)
                    with ftl_util.Timing("building pkg layer"):
                        layer_builder.BuildLayer()
                    req_txt_imgs.append(layer_builder.GetImage())

                with ftl_util.Timing("stitching lyrs into req.txt image"):
                    req_txt_image = self.AppendLayersIntoImage(req_txt_imgs)

                req_txt_builder.SetImage(req_txt_image)
                if self._args.cache:
                    with ftl_util.Timing("uploading req.txt image"):
                        self._cache.Set(req_txt_builder.GetCacheKey(),
                                        req_txt_builder.GetImage())
            lyr_imgs.append(req_txt_builder.GetImage())

        app = base_builder.AppLayerBuilder(
            ctx=self._ctx,
            destination_path=self._args.destination_path,
            entrypoint=self._args.entrypoint,
            exposed_ports=self._args.exposed_ports)
        with ftl_util.Timing("building app layer"):
            app.BuildLayer()
        lyr_imgs.append(app.GetImage())
        with ftl_util.Timing("stitching lyrs into final image"):
            ftl_image = self.AppendLayersIntoImage(lyr_imgs)
        with ftl_util.Timing("uploading final image"):
            self.StoreImage(ftl_image)

    def _pip_install(self, pkg_txt):
        with ftl_util.Timing("pip_download_wheels"):
            pip_cmd_args = list(self._pip_cmd)
            pip_cmd_args.extend(
                ['wheel', '-w', self._wheel_dir, '-r', "/dev/stdin"])

            proc_pipe = subprocess.Popen(
                pip_cmd_args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=self._gen_pip_env(),
            )
            stdout, stderr = proc_pipe.communicate(input=pkg_txt)
            logging.info("`pip wheel` stdout:\n%s" % stdout)
            if stderr:
                logging.error("`pip wheel` had error output:\n%s" % stderr)
            if proc_pipe.returncode:
                raise Exception("error: `pip wheel` returned code: %d" %
                                proc_pipe.returncode)

    def _resolve_whls(self):
        return [
            os.path.join(self._wheel_dir, f)
            for f in os.listdir(self._wheel_dir)
        ]

    def _whl_to_fslayer(self, whl):
        tmp_dir = tempfile.mkdtemp()
        pkg_dir = os.path.join(tmp_dir, 'env')
        os.makedirs(pkg_dir)

        pip_cmd_args = list(self._pip_cmd)
        pip_cmd_args.extend(['install', '--no-deps', '--prefix', pkg_dir, whl])

        proc_pipe = subprocess.Popen(
            pip_cmd_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=self._gen_pip_env(),
        )
        stdout, stderr = proc_pipe.communicate()
        logging.info("`pip install` stdout:\n%s" % stdout)
        if stderr:
            logging.error("`pip install` had error output:\n%s" % stderr)
        if proc_pipe.returncode:
            raise Exception("error: `pip install` returned code: %d" %
                            proc_pipe.returncode)
        return tmp_dir

    def _gen_pip_env(self):
        pip_env = os.environ.copy()
        # bazel adds its own PYTHONPATH to the env
        # which must be removed for the pip calls to work properly
        pip_env.pop('PYTHONPATH', None)
        pip_env['VIRTUAL_ENV'] = self._venv_dir
        pip_env['PATH'] = self._venv_dir + "/bin" + ":" + os.environ['PATH']
        return pip_env
