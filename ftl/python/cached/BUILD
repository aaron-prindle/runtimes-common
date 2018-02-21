package(default_visibility = ["//visibility:public"])

load(
    "@io_bazel_rules_docker//python:image.bzl",
    "py_image",
)

py_binary(
    name = "python_cached",
    srcs = [
        "main.py",
        "//ftl/cached:cached_lib",
    ],
    data = ["//ftl:php_builder.par"],
    main = "main.py",
    deps = [
        "//ftl:ftl_lib",
        "@containerregistry",
    ],
)

load("@base_images_docker//dockerfile_build:dockerfile_build.bzl", "dockerfile_build")

dockerfile_build(
    name = "cached_base",
    base = "//ftl:python_builder_base",
    dockerfile = "//ftl/cached:Dockerfile",
)

py_image(
    name = "python_cached_image",
    srcs = [
        "main.py",
        "//ftl/cached:cached_lib",
    ],
    base = ":cached_base",
    main = "main.py",
    deps = [
        "//ftl:ftl_lib",
        "@containerregistry",
    ],
)
