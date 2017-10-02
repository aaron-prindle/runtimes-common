package(default_visibility = ["//visibility:public"])

load(
    "@io_bazel_rules_docker//docker/contrib/python:image.bzl",
    "py_image",
)
load(
    "@io_bazel_rules_docker//docker:docker.bzl",
    "docker_build",
)

py_library(
    name = "ftl_lib",
    srcs = glob([
        "__init__.py",
        "common/*.py",
    ]),
    deps = [
        "@containerregistry",
        "@httplib2//:httplib2",
    ],
)

py_test(
    name = "context_test",
    srcs = ["common/context_test.py"],
    deps = [
        ":ftl_lib",
        "@mock//:mock",
    ],
)

py_test(
    name = "builder_test",
    srcs = ["common/builder_test.py"],
    deps = [
        ":ftl_lib",
        "@mock//:mock",
    ],
)

py_test(
    name = "cache_test",
    srcs = ["common/cache_test.py"],
    deps = [
        ":ftl_lib",
        "@mock//:mock",
    ],
)

py_test(
    name = "node_builder_test",
    srcs = ["node/builder_test.py"],
    main = "node/builder_test.py",
    deps = [
        ":node_lib",
        "@mock//:mock",
    ],
    data = [
        ":node/testdata/base_image/config_file",
        ":node/testdata/node_app/app.js",
        ":node/testdata/node_app/package.json",
        ":node/testdata/base_image/fast/000.tar.gz",
        ":node/testdata/base_image/fast/001.tar.gz",
        ":node/testdata/base_image/fast/002.tar.gz",
        ":node/testdata/base_image/fast/003.tar.gz",
        ":node/testdata/base_image/fast/004.tar.gz",
        ":node/testdata/base_image/fast/005.tar.gz",
        ":node/testdata/base_image/fast/006.tar.gz",
        ":node/testdata/base_image/fast/007.tar.gz",
        ":node/testdata/base_image/fast/008.tar.gz",
        ":node/testdata/base_image/fast/009.tar.gz",
        ":node/testdata/base_image/fast/000.sha256",
        ":node/testdata/base_image/fast/001.sha256",
        ":node/testdata/base_image/fast/002.sha256",
        ":node/testdata/base_image/fast/003.sha256",
        ":node/testdata/base_image/fast/004.sha256",
        ":node/testdata/base_image/fast/005.sha256",
        ":node/testdata/base_image/fast/006.sha256",
        ":node/testdata/base_image/fast/007.sha256",
        ":node/testdata/base_image/fast/008.sha256",
        ":node/testdata/base_image/fast/009.sha256",

    ]
)

py_library(
    name = "node_lib",
    srcs = glob(["node/*.py"]),
    deps = [":ftl_lib"],
)

# The node base image sets a default CMD, which causes issues if you run our image with no CMD.
# So, reset it to [""] before building our py_image.
docker_build(
    name = "node_builder_base",
    base = "@node_base//image",
    cmd = [""],
    entrypoint = "",
)

py_binary(
    name = "node_builder",
    srcs = [":node_lib"],
    main = "node/main.py",
    deps = ["@containerregistry"],
)

py_image(
    name = "node_builder_image",
    srcs = [":node_lib"],
    base = ":node_builder_base",
    main = "node/main.py",
    deps = [
        "@containerregistry",
    ],
)
