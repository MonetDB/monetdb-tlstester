#!/bin/bash

set -e -x

VERSION="$(python3 -c 'import tlstester; print(tlstester.VERSION)')"
TAG="docker.io/monetdb/tlstester:$VERSION"

# podman must be installed
if ! command -v podman; then
    echo "podman not found"
    exit 1
fi

# the tag must not exist yet
if podman pull "$TAG" 2>/dev/null; then
    echo "Tag $TAG already exists! Maybe increment the version number?"
    exit 1
fi

echo "Tag $TAG does not exist, good!"

podman build --tag "$TAG" .

echo -e "\nYou should now run:  podman push $TAG"

# set +x

# cmd=( echo podman xxxpush "$TAG" )
# echo "About to run:   ${cmd[*]}\n"
# echo "Enter '$VERSION'> "
# read -ei lalala
# if [ "x$REPLY" = "x$VERSION" ]; then

#     set -x
#     ${cmd[@]}
# fi

