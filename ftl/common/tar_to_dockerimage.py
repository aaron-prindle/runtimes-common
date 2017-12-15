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
"""This package provides DockerImage for examining docker_build outputs."""

import cStringIO
import json
import gzip
import six
import hashlib

from containerregistry.client.v2_2 import docker_digest
from containerregistry.client.v2_2 import docker_image
from containerregistry.client.v2_2 import docker_http
from containerregistry.transform.v2_2 import metadata as v2_2_metadata


class TarDockerImage(docker_image.DockerImage):
    """Interface for implementations that interact with Docker images."""
    def __init__(self, blob):
        #   self._uncompressed_blob = uncompressed_blob
          self._blob = blob

    def fs_layers(self):
        """The ordered collection of filesystem layers that comprise this image."""
        manifest = json.loads(self.manifest())
        return [x['digest'] for x in reversed(manifest['layers'])]

    def diff_ids(self):
        """The ordered list of uncompressed layer hashes (matches fs_layers)."""
        cfg = json.loads(self.config_file())
        return list(reversed(cfg.get('rootfs', {}).get('diff_ids', [])))

    def config_blob(self):
        manifest = json.loads(self.manifest())
        return manifest['config']['digest']

    def blob_set(self):
        """The unique set of blobs that compose to create the filesystem."""
        return set(self.fs_layers() + [self.config_blob()])

    def digest(self):
        """The digest of the manifest."""
        return docker_digest.SHA256(self.manifest())

    def media_type(self):
        """The media type of the manifest."""
        manifest = json.loads(self.manifest())

        return manifest.get('mediaType', docker_http.OCI_MANIFEST_MIME)


    def manifest(self):
        """The JSON manifest referenced by the tag/digest.

        Returns:
          The raw json manifest
        """
        config = json.loads(self.config_file())
        content = self.config_file().encode('utf-8')

        layer_hash = hashlib.sha256(self.uncompressed_blob("")).hexdigest()

        # is the diff_id the sha of the uncompressed blob of a layer?
        diff_id = 'sha256:' + layer_hash  # (diffid_filename)
        blob_sum = 'sha256:' + layer_hash  # (diffid_filename)

        diffid_to_blobsum = {}
        diffid_to_blobsum[diff_id] = blob_sum

        return json.dumps({
            'schemaVersion': 2,
            'mediaType': docker_http.MANIFEST_SCHEMA2_MIME,
            'config': {
                'mediaType': docker_http.CONFIG_JSON_MIME,
                'size': len(content),
                'digest': 'sha256:' + hashlib.sha256(content).hexdigest()
            },
            'layers': [
                {
                    'mediaType': docker_http.LAYER_MIME,
                    'size': self.blob_size(""),
                    'digest': diffid_to_blobsum[diff_id] # digest
                }
                for diff_id in config['rootfs']['diff_ids']
            ]
        }, sort_keys=True)

    def config_file(self):
        """The raw blob string of the config file."""
        # layer = "Layer sha256 hashes that make up this image"
        arg_layer = [hashlib.sha256(self.uncompressed_blob("")).hexdigest()]
        blob_sum = 'sha256:' + arg_layer[0]  # (diffid_filename)
        _PROCESSOR_ARCHITECTURE = 'amd64'
        _OPERATING_SYSTEM = 'linux'

        data = json.loads('{}')
        layers = []
        for layer in arg_layer:
            layers.append(layer)

        output = v2_2_metadata.Override(data, v2_2_metadata.Overrides(
            author='Bazel', created_by='bazel build ...',
            layers=layers,
            ),
            architecture=_PROCESSOR_ARCHITECTURE,
            operating_system=_OPERATING_SYSTEM)
        # THIS IS WRONG, CHANGE, ERROR
        # NEEDS TO MATCH
        # sha256:d328f49ef4532c300e5cec2968b1ac14c7927a9e034ffae9f262323dc0b53ac9
        # ^^ from v2_2/save.py:93-94
        # vvvvvvvvvvvvvvvvvvvvvvvvvvv

        # NEW ERROR
        # 'digest' parameter 'sha256:d328f49ef4532c300e5cec2968b1ac14c7927a9e034ffae9f262323dc0b53ac9' does not matc
        # h computed digest 'sha256:a93e09c8b2a785736b2023e32054c42b9e0be248022f7b9d005811b883d9bfc1'.: None

        output['rootfs'] = {'diff_ids': [blob_sum]}

        return json.dumps(output, sort_keys=True)


    def blob_size(self, digest):
        """The byte size of the raw blob."""
        return len(self.blob(""))


    def blob(self, digest):
        """The raw blob of the layer.

        Args:
          digest: the 'algo:digest' of the layer being addressed.

        Returns:
          The raw blob string of the layer.
        """
        return self._blob

    def uncompressed_blob(self, digest):
        """Same as blob() but uncompressed."""
        zipped = self.blob("")
        buf = cStringIO.StringIO(zipped)
        f = gzip.GzipFile(mode='rb', fileobj=buf)
        unzipped = f.read()
        return unzipped

    def _diff_id_to_digest(self, diff_id):
        for (this_digest, this_diff_id) in zip(self.fs_layers(), self.diff_ids()):
          if this_diff_id == diff_id:
            return this_digest
        raise ValueError('Unmatched "diff_id": "%s"' % diff_id)

    def layer(self):
        """Like `blob()`, but accepts the `diff_id` instead.

        The `diff_id` is the name for the digest of the uncompressed layer.

        Args:
          diff_id: the 'algo:digest' of the layer being addressed.

        Returns:
          The raw compressed blob string of the layer.
        """
        return self.blob("")

    def uncompressed_layer(self, diff_id):
        """Same as layer() but uncompressed."""
        return self.uncompressed_blob(self._diff_id_to_digest(diff_id))


    def __enter__(self):
        """Open the image for reading."""

    def __exit__(self, unused_type, unused_value, unused_traceback):
        """Close the image."""

    def __str__(self):
        """A human-readable representation of the image."""
        return str(type(self))
