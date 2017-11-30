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
"""This package defines the shared cli args for ftl binaries."""

import abc
import hashlib

from ftl.common import ftl_util


class BaseLayer(object):
    """BaseLayer is an abstract base class representing a container layer.

    It provides methods for generating a dependency layer and an application
    layer.
    """

    __metaclass__ = abc.ABCMeta  # For enforcing that methods are overriden.

    @abc.abstractmethod
    def __init__(self):
        pass
        # self._ctx = ctx

    @abc.abstractmethod
    def GetCacheKey(self):
        """Synthesizes the application layer from the context.
        Returns:
          a raw string of the layer's .tar.gz
        """

    @abc.abstractmethod
    def BuildLayer(self):
        """Synthesizes the layer from the context.
        Returns:
          a raw string of the layer's .tar.gz
        """

class CacheCheckLayer(BaseLayer):
    def __init__(self, ctx, descriptor_files):
        self._ctx = ctx
        self._descriptor_files = descriptor_files
        self.was_cached = False

    def GetCacheKey(self):
        descriptor_contents = ftl_util.descriptor_parser(
            self._descriptor_files, self._ctx)
        return hashlib.sha256(descriptor_contents).hexdigest()

    def BuildLayer(self):
        pass
