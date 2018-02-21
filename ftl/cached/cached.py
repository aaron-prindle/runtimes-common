# Copyright 2017 Google Inc. All rights reserved.

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

# http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import subprocess
import datetime
import time
import os
import logging
import httplib2
import json

_THREADS = 32


class Cached():
    def __init__(self, args, runtime):
        self._base = args.base
        self._name = args.name
        self._directory = args.directory
        self._labels = [args.label_1, args.label_2]
        self._runtime = runtime

    def run_cached_tests(self):
        logging.getLogger().setLevel("NOTSET")
        logging.basicConfig(
            format='%(asctime)s.%(msecs)03d %(levelname)-8s %(message)s',
            datefmt='%Y-%m-%d,%H:%M:%S')
        logging.info('Beginning building {0} images'.format(self._runtime))
        try:
            # For the binary
            builder_path = 'ftl/{0}_builder.par'.format(self._runtime)

            # For container builder
            if not os.path.isfile(builder_path):
                builder_path = 'bazel-bin/ftl/{0}_builder.par'.format(
                    self._runtime)
            lyr_shas = []
            for label in self._labels:
                cmd = subprocess.Popen(
                    [
                        builder_path, '--base', self._base, '--name', self._name,
                        '--directory', self._directory
                    ],
                    stderr=subprocess.PIPE)
                _, output = cmd.communicate()
                logging.info('output build #1: {0}'.format(output))
                cmd = subprocess.Popen(
                    [
                        builder_path, '--base', self._base, '--name', self._name,
                        '--directory', self._directory
                    ],
                    stderr=subprocess.PIPE)
                _, output = cmd.communicate()
                logging.info('output of build {0}: {1}'.format(label, output))
                lyr_shas.append(fetch_lyr_shas(name)
            try:
                self._compare_layers(lyr_shas_1, lyr_shas_2)
            except RuntimeError:
                exit(1)
        except OSError:
            raise OSError("""Cached test assumes either ftl/{0}_builder.par
                or bazel-bin/ftl/{0}_builder.par
                exists""".format(self._runtime))

    def _compare_layers(self, lyr_shas_1, lyr_shas_2):
        if len(lyr_shas_1) != len(lyr_shas_2):
            logging.error("different amount of layers found when \
                               reuploading same image")
            raise RuntimeError("different amount of layers found when \
                               reuploading same image")
        lyr_diff_cnt = 0
        for lyr_sha in lyr_shas_1:
            if lyr_sha not in lyr_shas_2:
                lyr_diff_cnt += 1
            if lyr_diff_cnt > 1:
                logging.error("more layers differed then app layer when \
                reuploading image")
            raise RuntimeError("more layers differed then app layer when \
                reuploading image")

