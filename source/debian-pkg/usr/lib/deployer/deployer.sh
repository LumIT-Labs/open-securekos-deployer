#!/bin/bash

# Script to be launched via (gk)sudo.

PROG_FOLDER="/usr/lib/open-securekos-deployer-DEPLOYER_MAJOR"
PROG_NAME="deployer.pyc"

# Launch the Deployer if not already running (with root privileges).
if [ "$(ps aux | grep deployer | grep python)" = "" ]; then
    cd $PROG_FOLDER
    /usr/bin/python $PROG_NAME --gui
fi