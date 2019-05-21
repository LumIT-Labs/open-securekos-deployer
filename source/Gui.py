from __future__ import division
import time, warnings
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GObject, Gdk
from Util import *
from System import *
from Filesystem import *

class Gui:
    deviceFilenamesStorage = ['/dev/sdb','/dev/sdc','/dev/sdd','/dev/sde','/dev/sdf','/dev/sdg','/dev/sdh','/dev/sdi','/dev/sdj','/dev/sdk','/dev/sdl','/dev/sdm','/dev/sdn','/dev/sdo','/dev/sdp','/dev/sdq','/dev/sdr','/dev/sds','/dev/sdt','/dev/sdu','/dev/sdv','/dev/sdw','/dev/sdx','/dev/sdy']

    window = None
    progressbars = {}
    completedDevices = {}
    encryptSecretEntry = None
    builder = Gtk.Builder()

    STATUS_WRITE = False
    STATUS_WRITE_FINISHED = False
    validDevicesArray = []

    isoFile = ""
    isoFileSize = 0



    # Manage GUI according to mounted/unmounted devices.
    def manageGUI(self):
        # Find mounted USB devices (i.e. get Linux device files) and set text on self.progressbars.
        devicesArray = System.getInsertedUSBDevices()

        # Before writing.
        if not self.STATUS_WRITE and not self.STATUS_WRITE_FINISHED:
            # Reset all self.progressbars' text.
            for bar in self.deviceFilenamesStorage:
                self.progressbars[bar].set_show_text(False)

            # Put <device> information on the progressbar.
            for device,serial in devicesArray:
                keySize = System.getKeySize(device)
                self.progressbars[device].set_text("Device: "+device.replace("/dev/","")+" | "+serial[-20:]+" | "+keySize)
                self.progressbars[device].set_show_text(True)

        # After write is finished, clean removed USB keys.
        if self.STATUS_WRITE_FINISHED:
            for dev in self.deviceFilenamesStorage:
                if not (any(dev in arr for arr in devicesArray)): # if not (dev in devicesArray):
                    self.progressbars[dev].set_fraction(0)

        return True # must be true for the timeout not to stop.



    def deploy(self, button):
        self.STATUS_WRITE = True

        if self.isoFile:
            # Kill open processes and delete logs. Disable write button. Clean progress bars' text.
            System.processesKillAndClean(self.config['logorroic'])
            button.set_sensitive(False)

            # GUI is modified only after the end of a method: all gtk events are handled in the mainloop.
            # The following lines of code force GUI updating.
            while Gtk.events_pending():
                Gtk.main_iteration_do(False)

            for bar in self.deviceFilenamesStorage:
                self.progressbars[bar].set_show_text(False)

            # Define valid and invalid devices.
            devicesAssociativeArray = System.getInsertedUSBDevices()
            for device,serial in devicesAssociativeArray:
                if System.getKeySize(device):
                    self.progressbars[device].set_text("Valid device: creating initial structures...")
                    self.progressbars[device].set_show_text(True)

                    self.validDevicesArray.append((device,serial))
                else:
                    self.progressbars[device].set_text("Invalid device.")
                    self.progressbars[device].set_show_text(True)

            while Gtk.events_pending():
                Gtk.main_iteration_do(False)

            # For every valid device, umount partitions, clean GPT, create system  partitions
            # and launch xorriso (progress stored in /tmp/device.log).
            for device,serial in self.validDevicesArray:
                System.forceUnmounting(device,self.config['logorroic'])

                if not System.wipeKeys(device, self.config['logorroic']):
                    self.progressbars[device].set_text("Error initializing the GPT partitioning scheme.")
                    self.completedDevices[device] = True # mark this device as completed.
                else:
                    # Create the first system partition for writing kernel+initrd+filesystem.squashfs files into.
                    if not System.createIsoHostingPartition(device, int(self.isoFileSize), self.config['logorroic']):
                        self.progressbars[device].set_text("Error creating the ISO hosting partition.")
                        self.completedDevices[device] = True
                    else:
                        # Write content from the hybrid-ISO (no MBR; only kernel, initrd, filesystem.squashfs)
                        # with xorriso into the host partition: launch process.
                        System.launchXorrisoSystemWrite(self.isoFile,device,"1",self.config['logorroic'])

                    while Gtk.events_pending():
                        Gtk.main_iteration_do(False)

            #  Watch xorriso writing completion in a loop until all completed.
            while len(self.completedDevices)<len(self.validDevicesArray):
                for device, serial in self.validDevicesArray:
                    # Retrieve progress info.
                    infos = Filesystem.readFile("/tmp/"+device[-3:]+".log")
                    if infos:
                        infos = infos.strip()

                        # If write in progress (infos!=-1 and infos!=-2) for this device.
                        if infos!="-1" and infos!="-2":
                            percentageCompletion = float(infos)/100

                            # Write text on progressbar.
                            self.progressbars[device].set_text("Writing system: "+infos+"% completed...")
                            self.progressbars[device].set_show_text(True)

                            # Show advance.
                            try:
                                if percentageCompletion<=1:
                                    self.progressbars[device].set_fraction(percentageCompletion)
                            except Exception:
                                self.progressbars[device].set_fraction(0)

                        # If finished (ok or ko).
                        else:
                            # Write status on progressbar.
                            self.progressbars[device].set_fraction(1)

                            if infos=="-1":
                                self.progressbars[device].set_text("Waiting...")
                                self.progressbars[device].set_show_text(True)

                            if infos=="-2":
                                self.progressbars[device].set_text("Writing error.")
                                self.progressbars[device].set_show_text(True)

                            # Mark device as xorriso-write completed.
                            self.completedDevices[device] = True

                        while Gtk.events_pending():
                            Gtk.main_iteration_do(False)

                    time.sleep(6)

            # If xorriso write completed for every key, proceed serially for the remaining actions.
            for device, serial in self.validDevicesArray:
                self.progressbars[device].set_text("Writing second system partition...")
                while Gtk.events_pending():
                    Gtk.main_iteration_do(False)

                # Create the second system partition for writing kernel+initrd files into.
                if not System.createIsoHostingPartition(device, self.config['secondSystemPartitionSize'], self.config['logorroic']):
                    self.progressbars[device].set_text("Error creating the second system partition.")
                else:
                    # Write content from ISO image (only kernel+initrd) with xorriso into the second system partition.
                    if not System.xorrisoSecondSystemWrite(self.isoFile,device,"2",self.config['logorroic']):
                        self.progressbars[device].set_text("Error writing the second system partition.")
                    else:
                        # Find out ISO partitions UUIDs.
                        isoUuidSystemPartition = System.getPartitionUuid(device,"1",self.config['logorroic'])
                        isoUuidSecondSystemPartition = System.getPartitionUuid(device,"2",self.config['logorroic'])

                        if not isoUuidSystemPartition and isoUuidSecondSystemPartition:
                            self.progressbars[device].set_text("ISO partition lacks UUID.")
                        else:
                            self.progressbars[device].set_text("UEFI partition creation...")
                            while Gtk.events_pending():
                                Gtk.main_iteration_do(False)

                            # Create UEFI structures on the key; pass isoUuid* to grub.cfg:
                            # GRUB will load kernel and initrd from the second system partition (which will be rewritten via xorrisofs after the kernel update by the system itself),
                            # and will instruct the live-build-patched initrd to load the filesystem.squashfs from the first (complete) system partition.
                            # A fallback boot is also available, with ye olde settings (i.e.: kernel/initrd loader from first system partition);
                            # this boot option will also pass a special boot parameter, so the system can re-build the second system partition (xorrisofs).
                            if not System.writeUEFIStructures(device,"3",self.config['uefiPartitionSize'],isoUuidSystemPartition,isoUuidSecondSystemPartition,self.encryptSecretEntry.get_text(),self.config['logorroic']):
                                self.progressbars[device].set_text("Error creating the UEFI structures.")
                            else:
                                self.progressbars[device].set_text("BIOS boot sector code installation...")
                                while Gtk.events_pending():
                                    Gtk.main_iteration_do(False)

                                # Install GRUB for BIOS boot, too: boot sector code into MBR and second stage into the UEFI partition.
                                if not System.installGrub(device,"3",isoUuidSystemPartition,isoUuidSecondSystemPartition,self.encryptSecretEntry.get_text(),self.config['logorroic']):
                                    self.progressbars[device].set_text("Error creating the GRUB structures.")
                                else:
                                    self.progressbars[device].set_text("Finalizing: persistence partition creation...")
                                    while Gtk.events_pending():
                                        Gtk.main_iteration_do(False)

                                    # Create persistence partition as the last partition (with all the remaining space left) and encrypt it.
                                    if not System.createPersistencePartition(device,"4",self.encryptSecretEntry.get_text().strip(),self.config['logorroic']):
                                        self.progressbars[device].set_text("Error in creating the persistence partition.")
                                    else:
                                        # Finally fix partitions' flags.
                                        if not System.setPartitionHiddenFlag(device,"1",self.config['logorroic']):
                                            self.progressbars[device].set_text("Error occurred while flagging the partition.")
                                        else:
                                            if not System.setPartitionHiddenFlag(device,"2",self.config['logorroic']):
                                                self.progressbars[device].set_text("Error occurred while flagging the partition.")
                                            else:
                                                self.progressbars[device].set_text("Operation completed.")

                while Gtk.events_pending():
                    Gtk.main_iteration_do(False)

            # Finally exit write status and enter the after-write one.
            self.STATUS_WRITE = False
            self.STATUS_WRITE_FINISHED = True

            dialog = Gtk.MessageDialog(self.window,0,Gtk.MessageType.INFO,Gtk.ButtonsType.OK,"Write process completed.")
            dialog.format_secondary_text("Open Secure-K OS deploy process finished, check each device's status.")
            dialog.run()
            dialog.destroy()



    def isoSelected(self, widget):
        self.isoFile = "\""+widget.get_filename()+"\""
        self.isoFileSize = int(Filesystem.fileSize(widget.get_filename()) / 1024 / 1024) # MB.



    def hideNonAvailableKeys(self, widget):
        # Hide all progress bars related to non-available USB keys.
        devicesAssociativeArray = System.getInsertedUSBDevices()
        for dev in self.deviceFilenamesStorage:
            self.progressbars[dev].show()
            if not (any(dev in arr for arr in devicesAssociativeArray)):
                self.progressbars[dev].hide()



    def quitApp(self, button, widget=None):
        # Clean all open processes and all logs. Then quit.
        System.processesKillAndClean(self.config['logorroic'])
        Gtk.main_quit()



    def __init__(self, configuration):
        j = 1

        # Load config.
        self.config = configuration

        # Import Glade interface, thanks to GtkBuilder.
        self.builder.add_from_file("gui.glade")
        self.window = self.builder.get_object("mainWindow")

        self.encryptSecretEntry = self.builder.get_object("encryptSecretEntry")

        # Put progressbar objects into an array named as the device name (/dev/sdb and so on).
        for device in self.deviceFilenamesStorage:
            self.progressbars[device] = self.builder.get_object("progressbar"+str(j))
            j = j+1

        # Connect GUI events (signals) to handlers.
        self.builder.connect_signals({
            "onExitMenuActivate": self.quitApp,
            "onHideBarsMenuActivate": self.hideNonAvailableKeys,
            "onImageChooserFileSet": self.isoSelected,
            "onWriteButtonPressed": self.deploy,

            "onMainWindowDeleteEvent": self.quitApp,
            "onExitButtonPressed": self.quitApp
            })

        # Set interval function for manageGUI().
        GObject.timeout_add(2000, self.manageGUI)

        warnings.filterwarnings("ignore")
        self.window.show_all()

        Gtk.main()
