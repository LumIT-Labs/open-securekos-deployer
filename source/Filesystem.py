import os
import shutil
from random import randint
from Util import *
from Process import *

class Filesystem:
    @staticmethod
    def fileExists(filename):
        return os.path.isfile(filename)



    @staticmethod
    def readFile(filename):         
        try:
            f = open(filename,"r")        
            fileContent = f.read()
            f.close()
        except Exception:
            return ""

        return fileContent



    @staticmethod
    def writeFile(filename,content):
        try:
            f = open(filename,"w")        
            f.write(content+"\n")
            f.close()

            os.chmod(filename,0700)
        except Exception:
            return False

        return True



    @staticmethod
    def moveAs(fromFile,toFile):
        try:
            shutil.move(fromFile,toFile)
        except Exception:
            return False

        return True



    @staticmethod
    def fileSize(filename):         
        try:
            fSize = os.path.getsize(filename)
        except Exception:
            return 0

        return fSize



    @staticmethod
    def tmpMount(devicePartition):
        r = str(randint(1,9999))
        tempFolder = "/tmp/mnt__"+r

        if Process.execute("mkdir "+tempFolder+" && mount "+devicePartition+" "+tempFolder+"; sleep 2")["success"]:
            return tempFolder

        return ""



    @staticmethod
    def tmpUmount(mountpoint):
        if not Process.execute("sync; umount "+mountpoint+" && rm -fR "+mountpoint+"; sleep 2")["success"]:
            return False

        return True

