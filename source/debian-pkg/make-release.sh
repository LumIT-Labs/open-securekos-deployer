#!/bin/bash

# Generator must be run as root.
ID=$(id -u)
if [ $ID -ne 0 ]; then
    echo "This script must be run as root."
    exit 1
fi

# Get Deployer version from the release file.
deployerRelease=$(echo $(cat deployer.release))
deployerMajorVersion=$(echo $deployerRelease | awk -F. '{print $1}')

# Definitions.
workingFolder="open-securekos-deployer_${deployerRelease}_all"
deployerMainFolder="usr/lib/open-securekos-deployer-${deployerMajorVersion}"
deployerConfigFolder="etc"
deployerIconFolder="usr/share/icons/hicolor/scalable/apps"
deployerDesktopfileFolder="usr/share/applications"

# Cleanups.
rm *.deb >/dev/null 2>&1
if [ -d $workingFolder ]; then
    rm -fR $workingFolder
fi

# Create a new working folder.
mkdir $workingFolder

# Compile Python files.
python -m compileall ./*.py

cd $workingFolder
    # Shape structures for creating .deb.
    mkdir -p $deployerMainFolder
    mkdir -p $deployerConfigFolder
    mkdir -p $deployerIconFolder
    mkdir -p $deployerDesktopfileFolder

    # Copy program files.
    cp -a ../grub-bios $deployerMainFolder/
    cp -a ../grub-uefi $deployerMainFolder/
    cp -a ../deployer.pyc $deployerMainFolder/
    cp -a ../System.pyc $deployerMainFolder/
    cp -a ../Filesystem.pyc $deployerMainFolder/
    cp -a ../Process.pyc $deployerMainFolder/
    cp -a ../Gui.pyc $deployerMainFolder/
    cp -a ../Util.pyc $deployerMainFolder/
    cp -a ../gui.glade $deployerMainFolder/

    # Hardcable program version.
    sed -i s/DEPLOYER_RELEASE/$deployerRelease/g $deployerMainFolder/gui.glade

    # Copy additional files.
    cp -a ../debian-pkg/usr/lib/deployer/deployer.sh $deployerMainFolder/
    cp -a ../debian-pkg/etc/sudoers.d $deployerConfigFolder/
    cp -a ../debian-pkg/usr/share/icons/hicolor/scalable/apps/deployer.svg $deployerIconFolder/
    cp -a ../debian-pkg/usr/share/applications/deployer.desktop $deployerDesktopfileFolder/

    cp -a ../deployer.cfg $deployerConfigFolder/
    cp -a ../debian-pkg/DEBIAN .

    # Configure.
    sed -i s/^logorroic:.*//g $deployerConfigFolder/deployer.cfg
    sed -i s/^Version:.*/Version:\ $deployerRelease/g DEBIAN/control

    sed -i s/DEPLOYER_MAJOR/$deployerMajorVersion/g $deployerMainFolder/deployer.sh
    sed -i s/DEPLOYER_MAJOR/$deployerMajorVersion/g $deployerConfigFolder/sudoers.d/deployer
    sed -i s/DEPLOYER_MAJOR/$deployerMajorVersion/g $deployerDesktopfileFolder/deployer.desktop
    sed -i s/DEPLOYER_MAJOR/$deployerMajorVersion/g DEBIAN/postinst

    # deployerMainFolder as root:root 700.
    chown -R 0:0 $deployerMainFolder
    chmod -R 700 $deployerMainFolder

    chown 0.0 $deployerConfigFolder/sudoers.d/deployer
    chmod 440 $deployerConfigFolder/sudoers.d/deployer
cd ..
    # Build the .deb.
    dpkg-deb --build $workingFolder

    # Final cleanups.
    rm -fR $workingFolder
    rm *.pyc
