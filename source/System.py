import pyudev, sys, re, hashlib
from random import randint
from Filesystem import *
from Util import *
from Process import *

class System:
    @staticmethod
    def getInsertedUSBDevices():
        devicesArray = []

        try:
            # udev watch & parse (only) for USB devices.
            context = pyudev.Context()
            for device in context.list_devices(ID_BUS='usb'):
                if device.get('UDISKS_PRESENTATION_NOPOLICY', '0')=='1':
                    continue
                if not str(device.get('DEVNAME')).find('/dev/input'):
                    continue
                if not str(device.get('DEVNAME')).find('/dev/bus'):
                    continue

                # Get name, for example /dev/sda3, and serial of inserted key.
                devName = device.get('DEVNAME','')
                devSerialRaw = device.get('ID_SERIAL').strip().replace("-0:0","") # brand_model_ABCXYZ.
                devSerial = devSerialRaw[(devSerialRaw.rfind("_")+1):] # ABCXYZ.

                # Consider only really-connected USB devices.
                # On some systems, Linux assigns a device file for non-connected devices (!); for example: the Macbook internal flash card reader.
                if System.__isValidDevice(devName,devSerialRaw):
                    if devName and devSerial:
                        # Append only devices, not partitions (so, sda is ok, while sda1 isn't).
                        if not Util.isNumber(devName[-1:]):
                            devicesArray.append((devName,devSerial))

        except Exception:
            pass

        return devicesArray # unique for sure. For example, [(u'/dev/sdb', u'Generic_Flash_Disk_715FEC49'), (u'/dev/sdc', u'iStorage_datashur_20095008150750010960')].



    @staticmethod
    def getKeySize(device):
        size = ""
        getSizeCmdln = "lsblk | grep "+device[-3:]+" | head -1 |  awk '{print $4}'"
        getSizeRun = Process.execute(getSizeCmdln)

        if getSizeRun["success"]:
            size = getSizeRun["output"]

        return size



    @staticmethod
    def processesKillAndClean(debugMode):
        xorrisoKillCmdln = "/usr/bin/killall xorriso"
        removeTempStructuresCmdln = "rm /tmp/sd*; rm -R /tmp/mnt__*"

        Process.launch(xorrisoKillCmdln)
        Process.launch(removeTempStructuresCmdln)

        if debugMode=="true":
            Util.debugMessage(["ddKillAndClean",xorrisoKillCmdln,removeTempStructuresCmdln],None)

        return True



    @staticmethod
    def forceUnmounting(device,debugMode):
        # Unmount all mounted device partitions if the DE mounts them (Deployer installation instructions not followed).
        umountCmdln = "for i in $(mount | grep "+device+" | awk '{print $1}'); do umount $i; done"
        Process.launch(umountCmdln)

        if debugMode=="true":
            Util.debugMessage(["forceUnmounting",umountCmdln],device)

        return True



    @staticmethod
    def wipeKeys(device, debugMode):
        # Initially wipe with wipefs.
        planeCmdln = "wipefs -af "+device+" && sleep 2"
        Process.launch(planeCmdln)

        # Re-create a blank GPT with a protective MBR - do not ever use fdisk/parted when GPT is involved.
        createBlankGPTCommand = "printf \"o\\nY\\nw\\nY\\n\" | gdisk "+device+" && sync && sleep 6"
        createBlankGPTRun = Process.execute(createBlankGPTCommand)

        if debugMode=="true":
            Util.debugMessage(["wipeKeys",planeCmdln,createBlankGPTCommand],device)

        if not createBlankGPTRun["success"]:
            if debugMode == "true":
                Util.debugMessage(["Error", "creating GPT: " + createBlankGPTRun["output"]], device)
            return False

        return True



    @staticmethod
    def setPartitionHiddenFlag(device,partitionNumber,debugMode):
        setFlagCmdln = "printf \"x\\na\\n"+partitionNumber+"\\n62\\n\\nw\\nY\\n\" | gdisk "+device+" && sync && sleep 2"
        setFlagRun = Process.execute(setFlagCmdln)

        if debugMode=="true":
            Util.debugMessage(["setPartitionFlags",setFlagCmdln],device)

        if not setFlagRun["success"]:
            if debugMode=="true":
                Util.debugMessage(["Error","fixing the partition flags: "+setFlagRun["output"]],device)
            return False

        return True



    @staticmethod
    def setExtPartitionName(device,partitionNumber,partitionName,debugMode):
        setNameCmdln = "e2label "+device+partitionNumber+" "+partitionName
        setNameRun = Process.execute(setNameCmdln)

        if debugMode=="true":
            Util.debugMessage(["setPartitionName",setNameCmdln],device)

        if not setNameRun["success"]:
            if debugMode=="true":
                Util.debugMessage(["Error","setting the partition name: "+setNameRun["output"]],device)
            return False

        return True



    @staticmethod
    def createIsoHostingPartition(device,partitionMB,debugMode):
        # Create a blank partition for writing the ISO image into.
        if int(partitionMB):
            createPartitionCmdln = "printf \"n\\n\\n\\n+"+str(partitionMB)+"M\\n8300\\nw\\nY\\n\" | gdisk "+device+" && sync && sleep 2"
            createPartitionRun = Process.execute(createPartitionCmdln)

            if debugMode=="true":
                Util.debugMessage(["createIsoHostingPartition",createPartitionCmdln],device)

            if not createPartitionRun["success"]:
                if debugMode=="true":
                    Util.debugMessage(["Error","creating the ISO hosting partition: "+createPartitionRun["output"]],device)
                return False

        return True



    @staticmethod
    def launchXorrisoSystemWrite(isoFile,device,partition,debugMode):
        dev = device[-3:] # device like "/dev/sdb"; dev like "sdb".

        # Execute xorriso and keep track of progress percentage in /tmp/"+dev+".log.
        xorrisoScript = "#!/bin/bash \n" \
            \
            "xorriso -indev "+isoFile+" -boot_image any discard -overwrite on -volid 'SK-SYSTEM1' -rm_r .disk boot efi efi.img isolinux md5sum.txt live/filesystem.packages* live/filesystem.size live/initrd.img-* live/vmlinuz-* -- -outdev stdio:"+device+partition+" -blank as_needed 2>/tmp/"+dev+".log.tmp & \n" \
            "pid_"+dev+"=$! \n" \
            \
            "while true; do \n" \
            "    sleep 2 \n" \
            \
            "    # If process running. \n" \
            "    if [ -d /proc/$pid_"+dev+" ]; then \n" \
            "        # Save its (float) completion percentage into a file, if positive. \n" \
            "        percentage=$(cat /tmp/"+dev+".log.tmp | awk '{print $7}' | sed s/%//g | tail -1) \n" \
            "        percentageInt=${percentage/.*}\n " \
            "        [ \"$percentage\" != \"\" ] && [ \"$percentageInt\" -gt \"0\" ] && echo $percentage > /tmp/"+dev+".log \n" \
            \
            "    # If process finished (or never begun). \n" \
            "    else \n" \
            "        if cat /tmp/"+dev+".log.tmp | grep -qi success; then \n" \
            "            echo '-1' > /tmp/"+dev+".log # all ok. \n" \
            "        else \n" \
            "            echo '-2' > /tmp/"+dev+".log # some error occurred. \n" \
            "        fi \n" \
            \
            "        exit 0 \n" \
            "    fi \n" \
            "done"
        Filesystem.writeFile("/tmp/"+dev+".xorriso.sh",xorrisoScript)

        xorrisoExtractCommand = "/bin/bash /tmp/"+dev+".xorriso.sh &"
        Process.launch(xorrisoExtractCommand)

        if debugMode=="true":
            Util.debugMessage(["launchXorrisoSystemWrite",xorrisoExtractCommand],device)

        return True



    @staticmethod
    def xorrisoSecondSystemWrite(isoFile,device,partition,debugMode):
        xorrisoExtractCommand = "xorriso -indev "+isoFile+" -boot_image any discard -overwrite on -volid 'SK-SYSTEM2' -rm_r .disk boot efi efi.img isolinux md5sum.txt live/filesystem.* live/filesystem.size live/initrd.img-* live/vmlinuz-* -- -outdev stdio:"+device+partition+" -blank as_needed"
        xorrisoExtractRun = Process.execute(xorrisoExtractCommand)

        if debugMode=="true":
            Util.debugMessage(["xorrisoSecondSystemWrite",xorrisoExtractCommand],device)

        if xorrisoExtractRun["success"]:
            # Return code of SORRY is ok.
            # This can happen if some excluded files are not within the ISO.
            if xorrisoExtractRun["status"]!=32:
                if debugMode=="true":
                    Util.debugMessage(["Error","writing the second system partition: "+xorrisoExtractRun["output"]],device)
                return False

        return True



    @staticmethod
    def getPartitionUuid(device,partitionNumber,debugMode):
        # Get the UUID of the partition.
        uuid = ""
        findUuidCommand = "blkid -s UUID "+device+partitionNumber

        if debugMode=="true":
            Util.debugMessage(["getPartitionUuid",findUuidCommand],device)

        rawUuid = Process.execute(findUuidCommand)["output"] # /dev/sdc1: UUID="7693-974D"
        uuidRegexp = re.search('UUID="(.*?)"', rawUuid)
        if uuidRegexp:
            uuid = str(uuidRegexp.group(1))

        if debugMode=="true":
            Util.debugMessage(["getPartitionUuid","uuid: "+uuid],device)

        return uuid.strip()



    @staticmethod
    def writeUEFIStructures(device,partitionNumber,uefiPartitionMB,isoUuidSystemPartition,isoUuidSecondSystemPartition,encryptionSecret,debugMode):
        status = True
        if int(uefiPartitionMB):
            # Create UEFI structure directly on the key (must be FAT).
            # Flag the UEFI partition so that it is recognized as such by the OSs and not mounted.
            createUEFIStructuresCmdln = "printf \"n\\n\\n\\n+"+str(uefiPartitionMB)+"M\\nef00\\nw\\nY\\n\" | gdisk "+device+" && sync && sleep 2 && mkfs.vfat -n \"UEFI Boot\" "+device+partitionNumber+" && sleep 2"
            createUEFIStructuresRun = Process.execute(createUEFIStructuresCmdln)

            if debugMode == "true":
                Util.debugMessage(["writeUEFIStructures",createUEFIStructuresCmdln],device)

            if createUEFIStructuresRun["success"]:
                # Copy the grub UEFI bootloader and its config file inside, then modify it.
                # With Secure Boot support, bootx64.efi is the Linux Foundation's preloader, while loader.efi is the grub-efi bootloader.
                tmpMountpoint = Filesystem.tmpMount(device+partitionNumber)
                if tmpMountpoint:
                    copyEfiFolderCmdln = "cp -R grub-uefi "+tmpMountpoint+"/efi"
                    setGrubCfgCmdln = "sed -i -e \"s/SYSTEM_ISO_UUID1/"+isoUuidSystemPartition+"/g\" "+tmpMountpoint+"/efi/boot/grub.cfg; sed -i -e \"s/SYSTEM_ISO_UUID2/"+isoUuidSecondSystemPartition+"/g\" "+tmpMountpoint+"/efi/boot/grub.cfg"
                    removeLuksDirectiveFromGrubCfgCmdln = "sed -i -e \"s/persistence-encryption=luks //g\" "+tmpMountpoint+"/efi/boot/grub.cfg" # only for cleartext persistence, remove the LUKS directive from the bootloader's config.

                    if debugMode=="true":
                        if encryptionSecret:
                            Util.debugMessage(["writeUEFIStructures","mounting "+device+partitionNumber,copyEfiFolderCmdln,setGrubCfgCmdln],device)
                        else:
                            Util.debugMessage(["writeUEFIStructures","mounting "+device+partitionNumber,copyEfiFolderCmdln,setGrubCfgCmdln,removeLuksDirectiveFromGrubCfgCmdln],device)
                    
                    if encryptionSecret:
                        # If an encrypted persistence partition has been selected.     
                        if not (Process.execute(copyEfiFolderCmdln)["success"] and Process.execute(setGrubCfgCmdln)["success"]):
                            if debugMode=="true":
                                Util.debugMessage(["Error","copying the bootloader and/or hashing files."],device)
                            status = False                    
                    else:
                        # If a cleartext persistence partition has been selected.     
                        if not (Process.execute(copyEfiFolderCmdln)["success"] and Process.execute(setGrubCfgCmdln)["success"] and Process.execute(removeLuksDirectiveFromGrubCfgCmdln)["success"]):
                            if debugMode=="true":
                                Util.debugMessage(["Error","copying the bootloader and/or hashing files."],device)
                            status = False

                    Filesystem.tmpUmount(tmpMountpoint)
                else:
                    if debugMode=="true":
                        Util.debugMessage(["Error", "copying the bootloader and hashing files: cannot mount device."],device)
                    status = False
            else:
                if debugMode=="true":
                    Util.debugMessage(["Error","creating UEFI structure: "+createUEFIStructuresRun["output"]],device)
                status = False
        else:
            status = False

        return status



    @staticmethod
    def installGrub(device,partitionNumber,isoUuidSystemPartition,isoUuidSecondSystemPartition,encryptionSecret,debugMode):
        # Install GRUB for BIOS boot.
        # Second stage bootloader is saved into the UEFI folder.
        status = True
        tmpMountpoint = Filesystem.tmpMount(device+partitionNumber)
        if tmpMountpoint:
            copyGrubFolderCmdln = "cp -R grub-bios "+tmpMountpoint+"/boot"
            setGrubCfgCmdln = "sed -i -e \"s/SYSTEM_ISO_UUID1/"+isoUuidSystemPartition+"/g\" "+tmpMountpoint+"/boot/grub/grub.cfg; sed -i -e \"s/SYSTEM_ISO_UUID2/"+isoUuidSecondSystemPartition+"/g\" "+tmpMountpoint+"/boot/grub/grub.cfg"
            removeLuksDirectiveFromGrubCfgCmdln = "sed -i -e \"s/persistence-encryption=luks //g\" "+tmpMountpoint+"/boot/grub/grub.cfg" # only for cleartext persistence, remove the LUKS directive from the bootloader's config.
            grubMbrInstallCmdln = "grub-install --root-directory="+tmpMountpoint+" "+device+" --force >/dev/null 2>&1"

            if debugMode=="true":
                if encryptionSecret:
                    Util.debugMessage(["installGrub","mounting "+device+partitionNumber,copyGrubFolderCmdln,setGrubCfgCmdln,grubMbrInstallCmdln],device)
                else:
                    Util.debugMessage(["installGrub","mounting "+device+partitionNumber,copyGrubFolderCmdln,setGrubCfgCmdln,removeLuksDirectiveFromGrubCfgCmdln,grubMbrInstallCmdln],device)

            if encryptionSecret:
                # If an encrypted persistence partition has been selected.
                if not (Process.execute(copyGrubFolderCmdln)["success"] and Process.execute(setGrubCfgCmdln)["success"] and Process.execute(grubMbrInstallCmdln)["success"]):
                    if debugMode=="true":
                        Util.debugMessage(["Error","installing GRUB for BIOS boot."],device)
                    status = False
            else:
                # If a cleartext persistence partition has been selected.
                if not (Process.execute(copyGrubFolderCmdln)["success"] and Process.execute(setGrubCfgCmdln)["success"] and Process.execute(removeLuksDirectiveFromGrubCfgCmdln)["success"] and Process.execute(grubMbrInstallCmdln)["success"]):
                    if debugMode=="true":
                        Util.debugMessage(["Error","installing GRUB for BIOS boot."],device)
                    status = False

            Filesystem.tmpUmount(tmpMountpoint)
        else:
            if debugMode=="true":
                Util.debugMessage(["Error","installing GRUB for BIOS boot: cannot mount device."],device)
            status = False

        return status



    @staticmethod
    def createPersistencePartition(device,partitionNumber,encryptionSecret,debugMode):
        # Create the persistence partition as the last one with all the space left.
        createPersistencePartitionCmdln = "printf \"n\\n\\n\\n\\n\\nw\\nY\\n\" | gdisk "+device+" && sync && sleep 2 && mkfs.ext4 -F "+device+partitionNumber+" && sleep 2"
        createPersistencePartitionRun = Process.execute(createPersistencePartitionCmdln)

        if debugMode=="true":
            Util.debugMessage(["createPersistencePartition",createPersistencePartitionCmdln],device)

        if createPersistencePartitionRun["success"]:
            # Encrypt (if encryptionSecret is not null) and put persistence.conf file into the persistence partition.
            if not System.__encryptAndManagePersistencePartition(device,partitionNumber,encryptionSecret,debugMode):
                if debugMode=="true":
                    Util.debugMessage(["Error","handling persistence partition."],device)
                return False
        else:
            if debugMode=="true":
                Util.debugMessage(["Error","creating the persistence partition: "+createPersistencePartitionRun["output"]],device)
            return False

        return True



    #
    #
    # PRIVATE METHODS.
    #
    #

    @staticmethod
    def __tmpLuksMount(device,partitionNumber,encryptionSecret,debugMode):
        r = str(randint(1,9999))
        mapperDeviceName = r+device[-3:]
        mapperDevice = "/dev/mapper/"+mapperDeviceName
        tempFolder = "/tmp/mnt__"+mapperDeviceName

        openPersistencePartitionCmdln = "echo -n \""+encryptionSecret+"\" | cryptsetup luksOpen "+device+partitionNumber+" "+mapperDeviceName+" -"
        mountPersistencePartitionCmdln = "mkdir "+tempFolder+"; mount -t auto "+mapperDevice+" "+tempFolder

        if debugMode=="true":
            Util.debugMessage(["__tmpLuksMount",openPersistencePartitionCmdln,mountPersistencePartitionCmdln],device)

        if Process.execute(openPersistencePartitionCmdln)["success"] and Process.execute(mountPersistencePartitionCmdln)["success"]:
            return tempFolder

        return ""



    @staticmethod
    def __tmpLuksUmount(mountpoint,debugMode):
        mapperDevice = "/dev/mapper/"+mountpoint.strip("/tmp/mnt__")

        unmountPersistencePartitionCmdln = "sync; umount "+mountpoint+" && cryptsetup luksClose "+mapperDevice+" && rm -fR "+mountpoint

        if debugMode=="true":
            Util.debugMessage(["__tmpLuksUmount",unmountPersistencePartitionCmdln],None)

        Process.execute(unmountPersistencePartitionCmdln)
        if not Process.execute(unmountPersistencePartitionCmdln)["success"]:
            return False

        return True



    @staticmethod
    def __encryptAndManagePersistencePartition(device,partitionNumber,encryptionSecret,debugMode):
        status = False
        r = str(randint(1,9999))

        if encryptionSecret:
            # Encrypted persistence partition.
            encryptPersistencePartitionCmdln = "echo -n \""+encryptionSecret+"\" | cryptsetup --hash=sha512 --cipher=aes-xts-plain64 --key-size=512 luksFormat "+device+partitionNumber+" -"
            openPersistencePartitionCmdln = "echo -n \""+encryptionSecret+"\" | cryptsetup luksOpen "+device+partitionNumber+" encrypted_"+r+device[-3:]+" -"
            formatAndLabelPersistencePartitionCmdln = "mkfs.ext4 -i 8192 /dev/mapper/encrypted_"+r+device[-3:]+" && e2label /dev/mapper/encrypted_"+r+device[-3:]+" persistence"
            closePersistencePartitionCmdln = "/sbin/cryptsetup luksClose /dev/mapper/encrypted_"+r+device[-3:]

            if debugMode=="true":
                Util.debugMessage(["__encryptAndManagePersistencePartition",encryptPersistencePartitionCmdln,openPersistencePartitionCmdln,formatAndLabelPersistencePartitionCmdln,closePersistencePartitionCmdln],device)

            if Process.execute(encryptPersistencePartitionCmdln)["success"] and Process.execute(openPersistencePartitionCmdln)["success"] and Process.execute(formatAndLabelPersistencePartitionCmdln)["success"] and Process.execute(closePersistencePartitionCmdln)["success"]:
                tmpLuksMountpoint = System.__tmpLuksMount(device,partitionNumber,encryptionSecret,debugMode)
                if tmpLuksMountpoint:
                    putPersistenceFileIntoPersistencePartitionCmdln = "echo \"/ union\" > "+tmpLuksMountpoint+"/persistence.conf"

                    if debugMode=="true":
                        Util.debugMessage(["__encryptAndManagePersistencePartition",putPersistenceFileIntoPersistencePartitionCmdln],device)

                    if Process.execute(putPersistenceFileIntoPersistencePartitionCmdln)["success"]:
                        status = True
                    else:
                        if debugMode=="true":
                            Util.debugMessage(["Error", "putting files into LUKS."],device)

                    System.__tmpLuksUmount(tmpLuksMountpoint,debugMode)
                else:
                    if debugMode=="true":
                        Util.debugMessage(["Error", "re-mounting LUKS."],device)
            else:
                if debugMode=="true":
                    Util.debugMessage(["Error", "setting up LUKS."],device)
        else:
            # Cleartext persistence partition.
            formatAndLabelPersistencePartitionCmdln = "mkfs.ext4 -i 8192 "+device+partitionNumber+" && e2label "+device+partitionNumber+" persistence"

            if debugMode=="true":
                Util.debugMessage(["__encryptAndManagePersistencePartition","Cleartext persistence selected",formatAndLabelPersistencePartitionCmdln],device)

            if Process.execute(formatAndLabelPersistencePartitionCmdln)["success"]:
                tmpMountpoint = Filesystem.tmpMount(device+partitionNumber)
                if tmpMountpoint:
                    putPersistenceFileIntoPersistencePartitionCmdln = "echo \"/ union\" > "+tmpMountpoint+"/persistence.conf"

                    if debugMode=="true":
                        Util.debugMessage(["__encryptAndManagePersistencePartition","Cleartext persistence selected",putPersistenceFileIntoPersistencePartitionCmdln],device)

                    if Process.execute(putPersistenceFileIntoPersistencePartitionCmdln)["success"]:
                        status = True
                    else:
                        if debugMode=="true":
                            Util.debugMessage(["Error", "putting files into the cleartext persistence partition."],device)

                    Filesystem.tmpUmount(tmpMountpoint)
                else:
                    if debugMode=="true":
                        Util.debugMessage(["Error", "re-mounting the cleartext persistence partition."],device)
            else:
                if debugMode=="true":
                    Util.debugMessage(["Error", "setting up the cleartext persistence partition."],device)

        return status



    @staticmethod
    def __isValidDevice(deviceName,deviceSerial):
        deviceSerial = deviceSerial.lower()
        devName = deviceName[-3:]

        # Remove Apple Card_Reader device.
        if "card" in deviceSerial and "reader" in deviceSerial:
            return False

        # Remove live persistent linuxes from the bunch.
        if (deviceName):
            secureKDevName = Process.execute("mount | grep persistence | grep mapper | awk '{print $1}' | awk -F\"/\" '{print $4}' | sed 's/[0-9]*//g'")["output"]
            if (devName==secureKDevName):
                return False

        return True
