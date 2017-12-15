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
"""A binary for constructing images from a source context."""

import tarfile
import json
import datetime
import httplib2
import logging

from containerregistry.client import docker_creds
from containerregistry.client import docker_name
from containerregistry.client.v2_2 import append
from containerregistry.client.v2_2 import docker_image
from containerregistry.client.v2_2 import docker_session
from containerregistry.client.v2_2 import save
from containerregistry.transport import transport_pool

from ftl.common import args as ftl_args
from ftl.common import cache
from ftl.common import context
from ftl.common import ftl_util
from ftl.common import build_layer
from ftl.common import tar_to_dockerimage
from ftl.node import builder as node_builder

_THREADS = 32
_DEFAULT_TTL_WEEKS = 1


class BuilderRunner():
    def __init__(self, args, builder, cache_version_str):
        self.args = args
        self.transport = transport_pool.Http(httplib2.Http, size=_THREADS)
        self.base = None
        self.base_name = docker_name.Tag(args.base)
        self.base_creds = docker_creds.DefaultKeychain.Resolve(self.base_name)
        self.target_image = docker_name.Tag(args.name)
        self.target_creds = docker_creds.DefaultKeychain.Resolve(
            self.target_image)
        self.ctx = context.Workspace(args.directory)
        self.cash = cache.Registry(
            self.target_image.as_repository(),
            self.target_creds,
            self.transport,
            cache_version=cache_version_str,
            threads=_THREADS,
            mount=[self.base_name])
        extracted = _args_extractor(self.ctx, vars(self.args))
        self.builder = builder.From(**extracted)

    def GetCachedDepsImage(self, checksum):
        if not checksum:
            return None
        hit = self.cash.Get(self.base, self.builder.namespace, checksum)
        if hit:
            logging.info('Found cached dependency layer for %s' % checksum)
            last_created = _timestamp_to_time(_creation_time(hit))
            now = datetime.datetime.now()
            if last_created > now - datetime.timedelta(
                    seconds=_DEFAULT_TTL_WEEKS):
                return hit
            else:
                logging.info(
                    'TTL expired for cached image, rebuilding %s' % checksum)
        else:
            logging.info('No cached dependency layer for %s' % checksum)
        return None

    def StoreDepsImage(self, dep_image, checksum):
        if self.args.cache:
            logging.info('Storing layer cash.')
            self.cash.Store(self.base, self.builder.namespace, checksum,
                            dep_image)
        else:
            logging.info('Skipping storing layer cash.')

    def GenerateFTLImage(self):
        with docker_image.FromRegistry(self.base_name, self.base_creds,
                                       self.transport) as self.base:
            # Create (or pull from cache) the base image with the
            # package descriptor installation overlaid.
            # ftl_image = self.base
            # ftl_image = single_layer_image
            lyr = self.builder.GetBuildLayers()
            lyr_gz, sha, overrides = lyr.BuildLayer()
            single_layer_image = tar_to_dockerimage.TarDockerImage(lyr_gz)

            # for lyr in lyrs:
            #     key = lyr.GetCacheKey()
            #     cached_img = self.GetCachedDepsImage(key)
            #     if cached_img:
            #         ftl_image = cached_img
            #         if isinstance(lyr, build_layer.CacheCheckLayer):
            #             cached_img.was_cached = True
            #         break

            #     if not isinstance(lyr, build_layer.CacheCheckLayer):
            #         built_layer, diff_id, overrides = \
            #             lyr.BuildLayer()
            #         ftl_image = append.Layer(
            #             ftl_image,
            #             built_layer,
            #             diff_id=diff_id,
            #             overrides=overrides)
            #         self.StoreDepsImage(ftl_image, key)

            if self.args.output_path:
                with ftl_util.Timing("saving_tarball_image"):
                    with tarfile.open(
                            name=self.args.output_path, mode='w') as tar:
                        save.tarball(self.target_image, single_layer_image, tar)
                    logging.info("{0} tarball located at {1}".format(
                        str(self.target_image), self.args.output_path))
                return
            with ftl_util.Timing("pushing_image_to_docker_registry"):
                with docker_session.Push(
                        self.target_image,
                        self.target_creds,
                        self.transport,
                        threads=_THREADS,
                        mount=[self.base_name]) as session:
                    logging.info('Pushing final image...')
                    session.upload(single_layer_image)
                return


def _creation_time(image):
    logging.info(image.config_file())
    cfg = json.loads(image.config_file())
    return cfg.get('created')


def _timestamp_to_time(dt_str):
    dt = dt_str.rstrip("Z")
    return datetime.datetime.strptime(dt, "%Y-%m-%dT%H:%M:%S")


def _args_extractor(ctx, args):
    extracted = {}
    extracted['ctx'] = ctx
    for flg in ftl_args.node_flgs + ftl_args.php_flgs + ftl_args.python_flgs:
        if flg in args and args[flg] is not None:
            extracted[flg] = args[flg]
    return extracted
