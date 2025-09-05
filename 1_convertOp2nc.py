#!/nwpr/gfs/com120/.conda/envs/rd/bin/python
'''
SYNTAX
    ./1_convertOp2nc.py [YYYYMMDD (reference date)]

If the reference date (T) is not sepecified,
the default reference is today.

---- ---- ---- ----
The script converts the operational CFSv2 data to nc files
for APCC BSISO purpose.
    variables: u850, olr
    domain: 40-160E, 10S-40N
    grid: 2p5 horizontal, daily mean
    lead time: 45 days
    init time range: reference date (T)-1 to T-121

For automation, the script can be executed everyday.
The already completed files will be skipped.

Steps (see the "main loop" part):
    0- check if the file needs update or is completed
    1- get the grib2 files from op data to TMPDIR, either untar or make links
    2- extract the variable and merge valid dates to a single file
    3- convert to nc file
'''
import tools.timetools as tt
import tools.nctools as nct
import shutil
import os
import subprocess
import logging
import sys


def main():
    #
    # ---- inputs
    def printUsage():
        print('ERROR: unrecognized input arguments')
        print('SYNTAX:')
        print('./1_convertOp2nc.py')
        print('./1_convertOp2nc.py YYYYMMDD')

    inargs = sys.argv
    if len(inargs) == 1:
        REFDATE = tt.today()

    elif len(inargs) == 2:
        arg = inargs[1]

        # make sure the input is numerical
        if len(arg) != 8:
            printUsage()
            return
        if not all([char in '0123456789' for char in arg]):
            printUsage()
            return
        
        REFDATE = int(tt.format2float(arg, '%Y%m%d'))
    else:
        printUsage()
        return
    

    #
    # ---- settings
    # -- run settings
    NUMLEADS = 45
    NUMINITS = 121 # forecast: T-1 to T-3, analysis: T-2 to T-121 -> all: T-1 to T-121
    CLEANTMPDIR = True # auto delete the tmpdir, set to False for debug
    VARNAMES = ['u850', 'olr']
    VARIABLES = {
        'u850': {
            'grib2matcher': ':UGRD:850 mb:',
            'cdoVarName': 'avg_u',
        },
        'olr': {
            'grib2matcher': ':ULWRF:',
            'cdoVarName': 'param4.5.0',
        }
    }
    CDOGRIDOPTION = '-sellonlatbox,40,160,-10,40 -remapbil,r144x73'
    RUNID = tt.float2format(tt.now(), '%y%m%d_%H%M%S') # can be set to 'test' for debug

    # -- bin paths
    WGRIB2 = '/usr/bin/wgrib2'
    CDO = '/nwpr/gfs/com120/.conda/envs/rd/bin/cdo'
    NCRENAME = '/usr/bin/ncrename'
    TAR = '/usr/bin/tar'

    # -- file paths
    RUNDIR = '.'
    LOGFILE = f'{RUNDIR}/logs/convert.{RUNID}'
    TMPDIR = f'{RUNDIR}/tmps/{RUNID}'

    SRCROOT = f'{RUNDIR}/data/op_src'
    DESROOT = f'{RUNDIR}/data/daymean'

    def getSrcDir(initTime):
        return tt.float2format(initTime, f'{SRCROOT}/%Y%m%d00/POST/OUTPUT/GFS/dm')

    def getTarredSrcPath(srcDir, validDate):
        return tt.float2format(validDate, f'{srcDir}/%Y%mdm.tar')

    def getGrib2SrcPath(srcDir, validDate):
        return tt.float2format(validDate, f'{srcDir}/%Y%m%d.grib2')

    def getDesPath(initTime, varName):
        return tt.float2format(initTime, f'{DESROOT}/%Y/%y%m%d_{varName}.nc')

    # ---- don't trigger the path check error in test run
    if RUNID == 'test':
        if os.path.exists(TMPDIR):
            shutil.rmtree(TMPDIR)
        if os.path.exists(LOGFILE):
            os.remove(LOGFILE)
    #
    # ---- check paths for working
    if os.path.exists(TMPDIR):
        raise FileExistsError(f'{TMPDIR=}')
    if os.path.exists(LOGFILE):
        raise FileExistsError(f'{LOGFILE=}')
    if not os.access(os.path.dirname(TMPDIR), os.W_OK):
        raise PermissionError(f'{os.path.dirname(TMPDIR)=}')
    if not os.access(os.path.dirname(LOGFILE), os.W_OK):
        raise PermissionError(f'{os.path.dirname(LOGFILE)=}')
    if not os.access(DESROOT, os.W_OK):
        raise PermissionError(f'{DESROOT=}')

    #
    # ---- set up the logger
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.FileHandler(LOGFILE),  # output to the file
            logging.StreamHandler()  # display in the terminal as well
        ]
    )

    #
    # ---- check bin paths
    returnCode, __ = runCommand(f'{WGRIB2} --version')
    if returnCode != 8:  # wgrib2 returns 8 in version checking...
        logging.fatal(f'wgrib2 not found: {WGRIB2=}')
        return

    returnCode, __ = runCommand(f'{CDO} --version')
    if returnCode != 0:
        logging.fatal(f'cdo not found: {CDO=}')
        return

    returnCode, __ = runCommand(f'{TAR} --version')
    if returnCode != 0:
        logging.fatal(f'tar not found: {TAR=}')
        return

    returnCode, __ = runCommand(f'{NCRENAME} --version')
    if returnCode != 0:
        logging.fatal(f'ncrename not found: {NCRENAME=}')
        return

    #
    # ---- initialization
    logging.info('beginning converting the CFSv2 data from grib2 to nc file')
    logging.info(f'  {RUNID=}')
    logging.info(f'  {NUMINITS=}')
    logging.info(f'  {NUMLEADS=}')
    logging.info(f'  REFDATE (T) ={tt.float2format(REFDATE)}')

    #
    # ---- organize the grib2 files from source to TMPDIR (grb2 -> grb2)
    def getTmpGrib2(initTime):
        #
        # ---- setup
        logging.info(f'  getting grib2 files from src to TMPDIR')
        srcDir = getSrcDir(initTime)
        if os.path.exists(TMPDIR):
            shutil.rmtree(TMPDIR)
        os.mkdir(TMPDIR)

        #
        # ---- is the grib2 files not tarred yet?
        # op provides grib2 files separated by dates,
        # but they are later tarred.
        # -> check we are processing from which state of the source files
        grib2SrcPaths = [
            getGrib2SrcPath(srcDir, initTime+iLead+1) for iLead in range(NUMLEADS)
        ]
        allGrib2SrcFound = all([
            os.path.exists(path) for path in grib2SrcPaths
        ])

        #
        # ---- not all found: untar files to TMPDIR / all found: make links to TMPDIR
        if allGrib2SrcFound:  # make links
            logging.info('  making links from the src grib2 to TMPDIR')
            for srcPath in grib2SrcPaths:
                # add "../../" for the relative path between the TMPDIR and SRCDIR
                runCommand(f'ln -s ../../{srcPath} {TMPDIR}')
        elif not allGrib2SrcFound:  # find tar files and untar them
            logging.info('  trying locating the tar files')
            tarredSrcPaths = [getTarredSrcPath(
                srcDir, initTime+iLead+1) for iLead in range(NUMLEADS)]
            tarredSrcPaths = list(set(tarredSrcPaths))  # remove duplicates
            allTarredSrcFound = all([os.path.exists(path)
                                    for path in tarredSrcPaths])

            if not allTarredSrcFound:
                logging.error(f'unable to locate all the src files')
                return False  # for error

            logging.info('  untarring files')
            for path in tarredSrcPaths:
                runCommand(f'{TAR} -xvf {path} -C {TMPDIR}')

        #
        # ---- check all grib2 files are located in (either linked or untarred to) the TMPDIR
        for iLead in range(NUMLEADS):
            path = tt.float2format(initTime+iLead+1, f'{TMPDIR}/%Y%m%d.grib2')
            if not os.path.exists(path):
                logging.error(f'unable to locate {path}')
                return False  # for error

        return True  # for success

    #
    # ---- merge variables from each valid dates to a single grib2 file and convert to nc
    def extractVariable(initTime, varName):
        #
        # ---- setup
        logging.info(f'  {varName}: extracting and merging')
        matcher = VARIABLES[varName]['grib2matcher']
        mergedPath = f'{TMPDIR}/{varName}.grib2'

        if os.path.exists(mergedPath):
            os.remove(mergedPath)

        #
        # ---- merge records
        for iLead in range(NUMLEADS):
            validTime = initTime + iLead + 1
            path = tt.float2format(validTime, f'{TMPDIR}/%Y%m%d.grib2')

            #
            # ---- get the record number
            command = [*f"{WGRIB2} -ncpu 1 {path} -match".split(), matcher]
            returnCode, result = runCommand(command, autoSplit=False)
            if returnCode != 0:
                logging.error(f'{returnCode=} for {command}, {result=}')
                return False
            # remove the empty string and warning message
            recordNumbers = [message.split(':')[0]
                             for message in result.split('\n')]
            recordNumbers = [
                num for num in recordNumbers if num not in ['Warning', '']]
            if len(recordNumbers) != 1:
                logging.error(
                    f'expecting 1 but found {len(recordNumbers)} messages in {path}')
                return False

            #
            # ---- merge data
            command = [
                *f"{WGRIB2} -ncpu 1 {path} -match".split(), matcher,
                '-append', '-grib_out', mergedPath,
            ]
            returnCode, result = runCommand(command, autoSplit=False)
            if returnCode != 0:
                logging.error(f'{returnCode=} for {command}, {result=}')
                return False

        return True

    #
    # ---- regrid, cut domain, and convert to nc, then ncrename
    def merged2nc(initTime, varName):
        #
        # ---- setup
        logging.info(f'  {varName}: converting to nc')
        srcPath = f'{TMPDIR}/{varName}.grib2'
        desPath = getDesPath(initTime, varName)
        cdoVarName = VARIABLES[varName]['cdoVarName']

        if not os.path.exists(os.path.dirname(desPath)):
            os.system(f'mkdir -p {os.path.dirname(desPath)}')

        #
        # ---- do it
        command = f'{CDO} -f nc4 -z zip9 --reduce_dim'
        command += f' -settaxis,{tt.float2format(initTime+1, '%Y%m%d,%H%M%S')},1day'
        command += f' -chname,{cdoVarName},{varName}'
        command += f' {CDOGRIDOPTION}'
        command += f' {srcPath} {desPath}'
        returnCode, result = runCommand(command)
        if returnCode != 0:
            logging.error(f'{returnCode=} for {command}, {result=}')
            return False

        return True

    #
    # ---- check output
    def checkOutput(initTime, varName):
        #
        # ---- setup
        path = getDesPath(initTime, varName)
        isCompleted, reason = True, ''

        #
        # ---- check existence
        if not os.path.exists(path):
            isCompleted = False
            reason = 'file not found'
            return isCompleted, reason

        #
        # ---- check varName
        if varName not in nct.getVarNames(path):
            isCompleted = False
            reason = 'varName not found'
            return isCompleted, reason

        #
        # ---- check lead lengths
        numLeads = nct.getVarShape(path, varName)[0]
        if numLeads < NUMLEADS:
            isCompleted = False
            reason = f'{numLeads=} (<{NUMLEADS})'

        return isCompleted, reason

    # ------------------- #
    # ---- main loop ---- #
    # ------------------- #
    for iInit in range(NUMINITS):
        #
        # ---- initial setup
        initTime = REFDATE - (iInit + 1)
        logging.info(f'T-{REFDATE-initTime} ({tt.float2format(initTime)})')

        #
        # ---- check file completeness, skip if completed
        outputStats = [checkOutput(initTime, varName) for varName in VARNAMES]
        areCompleted = [outputStat[0] for outputStat in outputStats]
        reasons = [outputStat[1] for outputStat in outputStats]

        if all(areCompleted):
            logging.info('  skipped: all outputs are completed')
            continue
        else:
            logging.info(f'  updating: {
                ', '.join([
                    f'{varName}-{reason}'
                    for varName, reason in zip(VARNAMES, reasons)
                    if reason != ''
                ])
            }')

        #
        # ---- run
        stat = getTmpGrib2(initTime)
        if not stat:
            continue

        for varName, isCompleted in zip(VARNAMES, areCompleted):
            if isCompleted:
                logging.info(f'  {varName}: skipping because completed')
                continue

            stat = extractVariable(initTime, varName)
            if not stat:
                continue

            stat = merged2nc(initTime, varName)
            if not stat:
                continue

            logging.info(f'  {varName}: finished')

        if not stat:
            continue
        logging.info('  all finished')

    #
    # ---- get output file status summary
    outputStats = [
        [iInit, varName, *checkOutput(REFDATE - (iInit + 1), varName)]
        for iInit in range(NUMINITS)
        for varName in VARNAMES
    ]
    missings = ', '.join([
                    f'T-{iInit+1} {varName}-{reason}'
                    for iInit, varName, isCompleted, reason in outputStats
                    if not isCompleted
                ])
    
    if len(missings) > 0:
        logging.warning(f'summary - missing files: {missings}')
    else:
        logging.info(f'summary - all outputs are completed')

    #
    # ---- clean up
    if os.path.exists(TMPDIR) and CLEANTMPDIR:
        shutil.rmtree(TMPDIR)
    
    #
    # ---- finished
    logging.info('normal exit')


def runCommand(command, autoSplit=True):
    if autoSplit:
        command = command.split()
    try:
        process = subprocess.run(command, capture_output=True, encoding='utf8')
        returnCode = process.returncode
        result = f'{process.stdout}{process.stderr}'
    except Exception as e:  # failed
        returnCode = 999
        result = str(e)
    return returnCode, result


if __name__ == '__main__':
    main()
