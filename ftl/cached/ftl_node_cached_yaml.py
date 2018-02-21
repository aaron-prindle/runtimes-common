"""A script to generate a cloudbuild yaml."""

import os
import yaml
import argparse

# Add directories for new tests here.
DEP_TESTS = ['small_app']
_DATA_DIR = '/workspace/ftl/node/cached/data/'
_NODE_BASE = 'gcr.io/google-appengine/nodejs:latest'

parser = argparse.ArgumentParser(
    description='Generate cloudbuild yaml for FTL cache test.')

parser.add_argument(
    '--label-1',
    action='store',
    type=int,
    default=None,
    help='name of first cache image')

parser.add_argument(
    '--label-2',
    dest='dep_test',
    action='store_true',
    default=None,
    help='name of second cache image')

def main():
    args = parser.parse_args()
    if not (args.dep_test and args.app_size):
        args.dep_test = True
        args.app_size = True

    cloudbuild_yaml = {
        'steps': [
            # We need to chmod in some cases for permissions.
            {
                'name': 'ubuntu',
                'args': ['chmod', 'a+rx', '-R', '/workspace']
            },
            # Build the FTL image from source and load it into the daemon.
            {
                'name':
                'gcr.io/cloud-builders/bazel',
                'args': [
                    'run', '//ftl/node/cached:node_cached_image', '--',
                    '--norun'
                ],
            },
            # Build the node builder par file
            {
                'name': 'gcr.io/cloud-builders/bazel',
                'args': ['build', 'ftl:node_builder.par']
            },
        ]
    }

    # Generate a set of steps for each test and add them.
    for app_dir in DEP_TESTS:
        cloudbuild_yaml['steps'] += dependency_test_step(app_dir)

    print yaml.dump(cloudbuild_yaml)


def dependency_test_step(app_dir):
    name = 'gcr.io/ftl-node-test/cached/cached_%s:latest' % app_dir
    return [
        # First build the image
        {
            'name':
            'bazel/ftl/node/cached:node_cached_image',
            'args': [
                '--base', _NODE_BASE,
                '--name', name,
                '--directory', os.path.join(_DATA_DIR + app_dir),
                 '--label-1', 'original',
                 '--label-2', 'reupload'
            ]
        }
    ]


if __name__ == "__main__":
    main()
