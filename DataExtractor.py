from collections import namedtuple
from genericpath import exists
from importlib.resources import path
from msilib.schema import Binary, Verb
from operator import truediv
import sys
import pathlib
from subprocess import check_output
from os import access, chmod, R_OK
from pathlib import Path
import time
import platform
import os
import json
import argparse
import mimetypes
import urllib.request

_args_quiet = ('-loglevel', 'panic')
_args_print = ('-show_streams', '-print_format', 'json')

Properties = namedtuple('p', 'title ffprobe_args')
VideoData = Properties('video', (*_args_quiet, '-select_streams', 'v:0', *_args_print))

binary = Path(__file__).parent / 'binary_dependencies'
system = platform.system()
ffprobe = "Missing"
InputDirectory = False
InputPath = ""
OutputDirectory = False
OutputPath = ""
codecs = []

VerboseEnabled = False

class MediaFile:
    def __init__(self, path):
        self.path = path
        self.name = os.path.basename(path)
        self.extension = os.path.splitext(path)[1]
        self.size = os.path.getsize(path)
        self.creationTime = os.path.getctime(path)
        self.modificationTime = os.path.getmtime(path)
        self.accessTime = os.path.getatime(path)
    
class FormatContainer:
    def _init_(self,extension):
        self.extension = extension
        Media = []

def format_bytes(size):
    # 2**10 = 1024
    power = 2**10
    n = 0
    power_labels = {0 : '', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
    while size > power:
        size /= power
        n += 1
    return str(round(size,2)) + " " + power_labels[n] + 'B'

def str2bool(v):
    if isinstance(v, bool):
        return v
    if v.lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    elif v.lower() in ('no', 'false', 'f', 'n', '0'):
        return False
    else:
        raise argparse.ArgumentTypeError('Boolean value expected.')

def Verbose(string):
    if(args.verbose):
        print(string)

def VerboseHeader():
    Verbose("")
    Verbose(f"Launch Time {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}")
    Verbose(f"Working Directory {os.getcwd()}")
    Verbose("Arguments:")
    Verbose(f"Input: {args.input}")
    Verbose(f"Output: {args.output}")
    Verbose(f"Codec(s): {args.codec}")
    Verbose(f"Recursive: {args.recursive}")
    Verbose(f"Verbose: {args.verbose}")
    Verbose("")

def DirectoryCheck(input, output, verbose):
    global InputPath
    global OutputPath
    global InputDirectory
    global OutputDirectory
    InputPath = input
    OutputPath = output
    if(input or output):
        if(input == "N/A"):
            InputDirectory = True
            InputPath = str(pathlib.Path().resolve())
            Verbose(f"Input directory/file not specified, using current directory [{InputPath}]")
        if(output == "N/A" and verbose == True):
            OutputDirectory = True
            OutputPath = str(pathlib.Path().resolve())
            Verbose(f"Output directory not specified, using current directory [{InputPath}]")
    if (os.path.isdir(input)) and (InputDirectory == False):
        Verbose("Input is a directory")
        InputDirectory = True
    elif((input != "N/A") and (InputDirectory == False)):
        Verbose("Input is a file")
        InputDirectory = False
    if (os.path.isdir(output)) and (OutputDirectory == False):
        Verbose("Output is a directory")
        OutputDirectory = True
    elif((output != "N/A") and (OutputDirectory == False)):
        Verbose("Output is a file")
        OutputDirectory = False

def OutputChecker():
    global OutputDirectory
    global OutputPath
    global InputDirectory
    global InputPath
    if(OutputDirectory == True):
        if(os.path.exists(OutputPath)):
            Verbose("Output directory exists")
        else:
            Verbose("Output directory does not exist, creating")
            os.mkdir(OutputPath)
            Verbose(f"Output directory created [{OutputPath}]")
        
        Verbose("Generating output file")
        OutputFileName = f"DataExtractor_{time.strftime('%Y-%m-%d_%H-%M-%S', time.localtime())}.csv"
        OutputPath = OutputPath + f"/{OutputFileName}"
        open(OutputPath, 'w')
        with open(OutputPath, 'a') as f:
                f.write(f"Path,Codec,FileSize")
                f.close()
        Verbose(f"Output file generated [{OutputPath}]")

    elif(OutputDirectory == False):
        if(os.path.exists(OutputPath)):
            Verbose("Output file exists")
        elif((OutputPath != "N/A") or (VerboseEnabled == True)):
            Verbose("Output file does not exist, creating")
            open(OutputPath, 'w')
            with open(OutputPath, 'a') as f:
                f.write(f"Path,Codec,FileSize")
                f.close()
            Verbose(f"Output file created [{OutputPath}]")

def Set_ffprobe():
    Verbose("Setting correct ffprove binary")
    global ffprobe
    if system == 'Darwin':
        Verbose("Linux Environment")
        a = str(binary / 'ffprobe')
        chmod(a, 0o755)
        ffprobe = a

    if system == 'Windows':
        Verbose("Windows Environment")
        ffprobe = str(binary / 'ffprobe.exe')
    
    Verbose(f"Set ffprobe binary [{ffprobe}]")

def CodecSetup(codecs):
    global Codecs
    if(codecs == "ALL"):
        Codecs = ["ALL"]
    else:
        codecs = codecs.lower()
        Codecs = codecs.split(",")
    
    Verbose(f"Desired Codecs: {Codecs}")

def FileChecker(path):
    Verbose(f"Checking file [{path}]")
    try:
        if mimetypes.guess_type(path)[0].startswith('video'):
            Verbose(f"{path} is a video")
            return True
        else:
            return False
    except:
        Verbose(f"{path} is not a video")
        return False

def GetVideoData(path: str,title: str, ffprobe_args):
    Verbose(f"Getting video data for [{path}]")
    if(not access(path, R_OK)):
        Verbose(f"Cannot read file [{path}]")
        #raise RuntimeError(f"Cannot read file [{path}]")
    else:
        output = check_output([ffprobe, *ffprobe_args, path], encoding='utf-8')
        props = json.loads(output)
        return props['streams'][0]

def WriteFile(Data):
    if(VerboseEnabled == True):
        Verbose("Writing data to file")
        with open(OutputPath, 'a') as f:
            f.write(f"\n{Data}")
            f.close()
        
def CheckFile(path):
    Verbose("Checking File [{path}]")
    Verbose("Getting absolute path")
    abspath = os.path.abspath(path)
    if(FileChecker(path)):
        Verbose(f"Getting Video Data [{path}]")
        Data = (GetVideoData(str(path),*VideoData))
        Verbose(f"Codec: {Data['codec_name']}")
        Size = format_bytes(os.path.getsize(abspath))
        Verbose(f"Size: {Size}")
        if((Data['codec_name'].lower() in Codecs) or (("ALL") in Codecs)):
            WriteFile(f"{abspath},{Data['codec_name']},{Size}")
        else:
            Verbose(f"Codec not in desired {Data['codec_name']}")

def FirstRun():
    RunDirectory = os.path.realpath(os.path.dirname(sys.argv[0]))
    Verbose("Linux Environment")
    if system == 'Darwin':
        if(os.path.exists(f"{RunDirectory}/binary_dependencies/ffprobe")):
            Verbose("Binary Dependencies Exists")
        else:
            Verbose("Downloading Binary dependency")
            linkToFile = "https://files.kristansmout.co.uk/Projects/PlexCodecInformation/ffprobe"
            localDestination = f"{RunDirectory}/binary_dependencies/ffprobe"
            resultFilePath, responseHeaders = urllib.request.urlretrieve(linkToFile, localDestination)

    if system == 'Windows':
        Verbose("Windows Environment")
        if(os.path.exists(f"{RunDirectory}/binary_dependencies/ffprobe.exe")):
            Verbose("Binary Dependencies Exists")
        else:
            Verbose("Downloading Binary dependency")
            linkToFile = "https://files.kristansmout.co.uk/Projects/PlexCodecInformation/ffprobe.exe"
            localDestination = f"{RunDirectory}/binary_dependencies/ffprobe.exe"
            resultFilePath, responseHeaders = urllib.request.urlretrieve(linkToFile, localDestination)

#Arguments
parser = argparse.ArgumentParser(description="Check media files for specific codecs and file sizes")

parser.add_argument("-i", "--input", 
                    help="Full path to the input file",
                    default="Z:\Github\MediaInformationGrabber")
parser.add_argument("-o", "--output",
                    help="Output file destination",
                    default="N/A")
parser.add_argument("-c", "--codec",
                    help="Output only specific format(s) (comma separated)",
                    default="ALL")
parser.add_argument("-r", "--recursive", 
                    help="Recursivly search child directories \n True:\n'yes', 'true', 't', 'y', '1' \nFalse:\n'no', 'false', 'f', 'n', '0'",
                    type=str2bool, 
                    nargs='?', 
                    const=True, 
                    default="true",)
parser.add_argument("-v","--verbose", 
                    help="Verbose output",
                    type=str2bool, 
                    nargs='?', 
                    const=True, 
                    default="t",)

args = parser.parse_args()
#print(vars(args))
FirstRun()
VerboseHeader()
if(args.verbose == True):
    Verbose("Verbose output enabled")
    VerboseEnabled = True
DirectoryCheck(args.input, args.output, args.verbose)
OutputChecker()
Set_ffprobe()
CodecSetup(args.codec)

if(InputDirectory == False):
    CheckFile(os.path.abspath(InputPath))
elif(InputDirectory == True):
    if(args.recursive == False):
        Verbose("Recursive search disabled")
        for file in os.listdir(InputPath):
            CheckFile(os.path.abspath(InputPath + "/" + file))
    elif(args.recursive == True):
        Verbose("Recursive search enabled")
        for root, dirs, files in os.walk(InputPath):
            for file in files:
                CheckFile(os.path.abspath(root + "/" + file))




