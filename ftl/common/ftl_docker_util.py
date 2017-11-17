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

import json
import hashlib

from containerregistry.client.v2_2 import docker_image
from containerregistry.client.v2_2 import docker_http

class FromDisk(docker_image.DockerImage):

    def __init__(self):
        self.config = "TODO"
        self.diffid_to_blobsum = {}
        config = json.loads(self.config)
        self._manifest = json.dumps({
            'schemaVersion': 2,
            'mediaType': docker_http.MANIFEST_SCHEMA2_MIME,
            'config': {
                'mediaType': docker_http.CONFIG_JSON_MIME,
                'size': len(self.config),
                'digest': 'sha256:' + hashlib.sha256(self.config).hexdigest()
            },
            'layers': [
                {
                    'mediaType': docker_http.LAYER_MIME,
                    'size': self.blob_size(self.diffid_to_blobsum[diff_id]),
                    'digest': self.diffid_to_blobsum[diff_id]
                }
                for diff_id in config['rootfs']['diff_ids']
            ]
        }, sort_keys=True)

    def blob_size(self, digest):
        """Override."""
        if digest not in self._blobsum_to_zipped:
            return self._blobsum_to_legacy[digest].blob_size(digest)
        info = os.stat(self._blobsum_to_zipped[digest])
        return info.st_size

    def manifest(self):
        """The JSON manifest referenced by the tag/digest.

        Returns:
        The raw json manifest
        """
        # pytype: enable=bad-return-type
        return self._manifest

    def config_file(self):
        """The raw blob string of the config file."""
  # pytype: enable=bad-return-type

    def blob(self, digest):
        """The raw blob of the layer.

        Args:
        digest: the 'algo:digest' of the layer being addressed.

        Returns:
        The raw blob string of the layer.
        """
    # pytype: enable=bad-return-type

    # def uncompressed_blob(self, digest):
    #     """Same as blob() but uncompressed."""
    #     zipped = self.blob(digest)
    #     buf = cStringIO.StringIO(zipped)
    #     f = gzip.GzipFile(mode='rb', fileobj=buf)
    #     unzipped = f.read()
    #     return unzipped
  # Could be large, do not memoize
    def uncompressed_blob(self, digest):
        """Override."""
        if digest not in self._blobsum_to_unzipped:
            return self._blobsum_to_legacy[digest].uncompressed_blob(digest)
        with open(self._blobsum_to_unzipped[digest], 'r') as reader:
            return reader.read()

    def _diff_id_to_digest(self, diff_id):
        for (this_digest, this_diff_id) in zip(self.fs_layers(), self.diff_ids()):
            if this_diff_id == diff_id:
                return this_digest
        raise ValueError('Unmatched "diff_id": "%s"' % diff_id)

    def layer(self, diff_id):
        """Like `blob()`, but accepts the `diff_id` instead.

        The `diff_id` is the name for the digest of the uncompressed layer.

        Args:
            diff_id: the 'algo:digest' of the layer being addressed.

        Returns:
            The raw compressed blob string of the layer.
        """
        return self.blob(self._diff_id_to_digest(diff_id))

    def uncompressed_layer(self, diff_id):
        """Same as layer() but uncompressed."""
        return self.uncompressed_blob(self._diff_id_to_digest(diff_id))

      # __enter__ and __exit__ allow use as a context manager.
    def __enter__(self):
        """Open the image for reading."""

    def __exit__(self, unused_type, unused_value, unused_traceback):
        """Close the image."""

    def __str__(self):
        """A human-readable representation of the image."""
        return str(type(self))
