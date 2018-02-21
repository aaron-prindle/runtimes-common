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

import argparse
import sys
from ftl.cached import args
from ftl.cached import cached


_RUNTIME = "node"
parser = argparse.ArgumentParser(description='Run FTL node cache test.')

parser = args.base_parser()
node_parser = argparse.ArgumentParser(
    add_help=False,
    parents=[parser], description='Run node cache test.')

node_parser.add_argument(
        '--label-1',
        dest='label_1',
        action='store',
        default='original',
        help='image label for original uploaded image')

node_parser.add_argument(
        '--label-2',
        dest='label_2',
        action='store',
        default='reupload',
        help='image label for reuploades image')

def main(cli_args):
    parsed_args = node_parser.parse_args(cli_args)
    c = cached.cached(parsed_args, _RUNTIME)
    c.run_cached_tests()


if __name__ == '__main__':
    main(sys.argv[1:])
