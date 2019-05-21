from termcolor import colored
from Filesystem import *

class Util:
    @staticmethod
    def isNumber(var):
        try:
            int(var)
            return True
        except ValueError:
            return False



    @staticmethod
    def readConfig(configFile):
        config = {}

        # Defaults.
        config["uefiPartitionSize"] = 32
        config["secondSystemPartitionSize"] = 256
        config["logorroic"] = "false"

        if not Filesystem.fileExists(configFile):
            configFile = "/etc/"+configFile

        try:
            configFileContent = Filesystem.readFile(configFile).strip()
            configFileContentArray = configFileContent.split("\n")

            for line in configFileContentArray:
                if line:
                    if not "#" in line:
                        lineContentArray = line.split(":")
                        config[lineContentArray[0].strip()] = str(lineContentArray[1].strip())
        except:
            config = {}

        return config



    @staticmethod
    def debugMessage(stringsArray,device):
        j = 0

        for msg in stringsArray:
            if msg:
                if j==0:
                    if not device:
                        print (colored("\n * "+msg+":","red"))
                    else:
                        print (colored("\n * "+"["+device+"] "+msg+":","red"))
                else:
                    print ("     "+msg)

                j = j+1

