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
import json
import concurrent.futures

from ftl.common import builder
from ftl.common import constants
from ftl.common import ftl_util
from ftl.common import layer_builder as base_builder
from ftl.php import layer_builder as php_builder


class PHP(builder.RuntimeBase):
    def __init__(self, ctx, args):
        super(PHP, self).__init__(
            ctx, constants.PHP_CACHE_NAMESPACE, args,
            [constants.COMPOSER_LOCK, constants.COMPOSER_JSON])

    def _parse_composer_pkgs(self):
        descriptor_contents = ftl_util.descriptor_parser(
            self._descriptor_files, self._ctx)
        composer_json = json.loads(descriptor_contents)
        pkgs = []
        for k, v in composer_json['require'].iteritems():
            pkgs.append((k, v))
        return pkgs

    def _parse_composer_lock_pkgs(self):
        descriptor_contents = ftl_util.descriptor_parser(
            self._descriptor_files, self._ctx)
        composer_lock_json = json.loads(descriptor_contents)
        pkgs = []
        for pkg in composer_lock_json['packages']:
            pkgs.append((pkg['name'], pkg['version']))
        return pkgs

    def _list_composer_lock_pkgs(self):
        descriptor_contents = ftl_util.descriptor_parser(
            self._descriptor_files, self._ctx)
        composer_lock_json = json.loads(descriptor_contents)
        pkg_list = []
        for pkg in composer_lock_json['packages']:
            pkg_list.append(pkg['name'])
        return pkg_list

    def _parse_composer_lock_pkgs(self):
        descriptor_contents = ftl_util.descriptor_parser(
            self._descriptor_files, self._ctx)
        composer_lock_json = json.loads(descriptor_contents)
        pkgs = []
        for pkg in composer_lock_json['packages']:
            pkgs.append((pkg['name'], pkg['version']))
        return pkgs

    def Build(self):
        lyr_imgs = []
        lyr_imgs.append(self._base_image)
        if ftl_util.has_pkg_descriptor(self._descriptor_files, self._ctx):
            if self._ctx.Contains(constants.COMPOSER_LOCK):
                pkgs = self._parse_composer_lock_pkgs()
                pkg_list = self._list_composer_lock_pkgs()
            else:
                pkgs = self._parse_composer_pkgs()
            # due to image layers limits, we revert to using phase 1 if over
            # the threshold
            if self._args.php_phase_1 or len(pkgs) > 41:
                # phase 1
                logging.info('Building package layer')
                layer_builder = php_builder.PhaseOneLayerBuilder(
                    ctx=self._ctx,
                    descriptor_files=self._descriptor_files,
                    destination_path=self._args.destination_path,
                    cache=self._cache)
                layer_builder.BuildLayer()
                lyr_imgs.append(layer_builder.GetImage())
            else:
                # phase 2
                with ftl_util.Timing('uploading_all_package_layers'):
                    with concurrent.futures.ThreadPoolExecutor(
                            max_workers=constants.THREADS) as executor:
                        future_to_params = {executor.submit(
                                self._build_pkg, pkg_txt, lyr_imgs, pkg_list): pkg_txt
                                for pkg_txt in pkgs
                        }
                        for future in concurrent.futures.as_completed(
                                future_to_params):
                            future.result()

        app = base_builder.AppLayerBuilder(
            ctx=self._ctx,
            destination_path=self._args.destination_path,
            entrypoint=self._args.entrypoint,
            exposed_ports=self._args.exposed_ports)
        app.BuildLayer()
        lyr_imgs.append(app.GetImage())
        ftl_image = ftl_util.AppendLayersIntoImage(lyr_imgs)
        self.StoreImage(ftl_image)

    def _build_pkg(self, pkg_txt, lyr_imgs, pkg_list):
        logging.info('Building package layer: {0} {1}'.format(
            pkg_txt[0], pkg_txt[1]))
        layer_builder = php_builder.PhaseTwoLayerBuilder(
            ctx=self._ctx,
            descriptor_files=self._descriptor_files,
            pkg_descriptor=pkg_txt,
            pkg_list=pkg_list,
            destination_path=self._args.destination_path,
            cache=self._cache)
        layer_builder.BuildLayer()
        lyr_imgs.append(layer_builder.GetImage())
