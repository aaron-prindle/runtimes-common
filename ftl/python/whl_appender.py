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
"""This package pulls images from a Docker Registry."""


from __future__ import google_type_annotations

import argparse
import cStringIO
import json
import os
import subprocess
import tarfile
import tempfile
import time
import zipfile

from containerregistry.client import docker_creds
from containerregistry.client import docker_name
from containerregistry.client.v2 import docker_image as v2_image
from containerregistry.client.v2_2 import append
from containerregistry.client.v2_2 import docker_image as v2_2_image
from containerregistry.client.v2_2 import docker_session
from containerregistry.client.v2_2 import v2_compat
from containerregistry.tools import patched
from containerregistry.transport import transport_pool

import httplib2


parser = argparse.ArgumentParser(
    description='Overlay a Python application on a given base image.')

parser.add_argument('--base', action='store',
                    help=('The name of the docker base image.'))

parser.add_argument('--directory', action='store',
                    help='The directory containing the app.')

parser.add_argument('--download-cache', action='store',
                    help='Where to cache download artifacts.')

parser.add_argument('--name', action='store',
                    help=('Where to publish the resulting image.'))


class Timing(object):
  def __init__(self, descriptor):
    self.descriptor = descriptor

  def __enter__(self):
    self.start = time.time()
    return self

  def __exit__(self, unused_type, unused_value, unused_traceback):
    end=time.time()
    print '%s took %d seconds' % (self.descriptor, end-self.start)


def resolve_whls(args):
  # For now, invoke `pip wheel` on a temporary directory and return a list
  # of the resulting .whl files.  In the future, invoke the logic underlying
  # `pip wheel` to perform the resolution and return the enumerated packages,
  # but use a large multi-tenant wheelhouse.
  dirpath = tempfile.mkdtemp()
  fnull = open(os.devnull, 'w') # or verbose?
  subprocess.check_call(
    ['pip', 'wheel'] +
    ['-w', dirpath] +
    (['--download-cache', args.download_cache] if args.download_cache else []) +
    ['-r', os.path.join(args.directory, 'requirements.txt')],
    stdout=fnull, stderr=fnull)
  return [os.path.join(dirpath, f) for f in os.listdir(dirpath)]


def whl_to_fslayer(whl):
  # Open the .whl (zip) and put all its files into a .tar.gz laid
  # out like it should be on the filesystem.
  zf = zipfile.ZipFile(whl, 'r')

  def add_files(out):
    target_dir = '/env/lib/python3.6/site-packages/'
    for name in zf.namelist():
      content = zf.read(name)
      info = tarfile.TarInfo(os.path.join(target_dir, name))
      info.size = len(content)
      out.addfile(info, fileobj=cStringIO.StringIO(content))

#   http://python-packaging.readthedocs.io/en/latest/command-line-scripts.html
  def add_scripts(out):
    basename = os.path.basename(whl)
    dist_parts = basename.split('-')
    distribution = '-'.join(dist_parts[:2])
    metadata = json.loads(zf.read(
        os.path.join(distribution + '.dist-info', 'metadata.json')))

    extensions = metadata.get('extensions')
    if not extensions:
      return

    commands = extensions.get('python.commands')
    if not commands:
      return

    scripts = commands.get('wrap_console', {})
    # TODO(mattmoor): Use distutils when doing this for realz
    target_dir = 'usr/local/bin'
    # Create the scripts in a deterministic ordering.
    for script in sorted(scripts):
      descriptor = scripts[script]
      (module, obj) = descriptor.split(':')
      content = """#!/usr/bin/python

# -*- coding: utf-8 -*-
import re
import sys

from {module} import {obj}

if __name__ == '__main__':
    sys.argv[0] = re.sub(r'(-script\.pyw?|\.exe)?$', '', sys.argv[0])
    sys.exit(run())
""".format(module=module, obj=obj)

      target_path = os.path.join('usr/local/bin')
      info = tarfile.TarInfo(os.path.join(target_dir, script))
      info.size = len(content)
      info.mode = 0777
      out.addfile(info, fileobj=cStringIO.StringIO(content))


  buf = cStringIO.StringIO()
  with tarfile.open(fileobj=buf, mode='w:gz') as out:
    add_files(out)
    add_scripts(out)
  return buf.getvalue()


def app_layer(args):
  # TODO(mattmoor): Collect the application files and stuff them into
  # a .tar.gz laid out like it should be on the filesystem.

  buf = cStringIO.StringIO()
  with tarfile.open(fileobj=buf, mode='w:gz') as out:
    for root, dirnames, filenames in os.walk(args.directory):
      relative = root[len(args.directory):]
      if relative.startswith('.git') or relative.startswith('bazel-'):
        continue
      for fname in filenames:
        fqname = os.path.join(args.directory, relative, fname)
        out.add(fqname, arcname=os.path.join("/app", relative, fname))

  return buf.getvalue()


def inner_main():
  args = parser.parse_args()

  if not args.base or not args.name or not args.directory:
    raise Exception('--base, --directory, and --name are required arguments.')

  # Resolve the appropriate credential to use based on the standard Docker
  # client logic.
  base = docker_name.Tag(args.base)
  creds = docker_creds.DefaultKeychain.Resolve(base)
  target = docker_name.Tag(args.name)

  transport = transport_pool.Http(httplib2.Http, size=8)

  with Timing("resolve whls"):
    whls = resolve_whls(args)

  # TODO(mattmoor): Parallelize all of this.
  with Timing("create filesystem layers"):
    layers = ([whl_to_fslayer(whl) for whl in whls] +
              [app_layer(args)])

  def append_stuff(baseimg, tgzs):
    if not tgzs:
      # Push it when we run out of stuff to append.
      with Timing("push"):
        with docker_session.Push(
            target, creds, transport, threads=8, mount=[base]) as session:
          session.upload(baseimg)
          return

    with append.Layer(baseimg, tgzs[0]) as new_base:
      append_stuff(new_base, tgzs[1:])

  with v2_2_image.FromRegistry(base, creds, transport) as v2_2_img:
    if v2_2_img.exists():
      with Timing("append and push (v2.2 base)"):
        append_stuff(v2_2_img, layers)
      return

  with v2_image.FromRegistry(base, creds, transport) as v2_img:
    with v2_compat.V22FromV2(v2_img) as v2_2_img:
      with Timing("append and push (v2 base)"):
        append_stuff(v2_2_img, layers)
      return


def main():
  with Timing("everything"):
    inner_main()

if __name__ == '__main__':
  with patched.Httplib2():
    main()
