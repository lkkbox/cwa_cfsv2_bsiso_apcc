#!/nwpr/gfs/com120/.conda/envs/rd/bin/python
'''
SYNTAX
    ./2_nc2ascii.py [YYYYMMDD (reference date)]

----
If the reference date (T) is not sepecified,
the default reference is today.

The script converts the CFSv2 forecast data for APCC BSISO in ascii format.
    variables: u850, olr
    domain: 40-160E, 10S-40N
    grid: 2p5 horizontal, daily mean
    lead time: 45 days
    init time range: reference date (T)-1 to T-121
    ↑ should be processed by 1_*.py 

Steps (see the "pre-checking" part and the "run" function):
    0- [pre-check] check the data file status and determine the init dates to use
    1- [run] analysis - read: obs clim, model clim, model raw
                      - bias_correction = model_raw - (model_clim + obs_clim)
    2- [run] forecast - same as analysis but with 3 inits
    3- [run] write output 
'''
import tools.timetools as tt
import tools.nctools as nct
import numpy as np
import logging
import os
import sys


def main():
    def postCheck():
        # ---- mark the log file for warning
        # ---- and make another warning file in the run path
        def warnFileName(warnType):
            return f'{RUNDIR}/warning-{tt.float2format(REFDATE, '%y%m%d')}-{warnType}'

        logging.info('post-checking')
        if any([not os.path.exists(getDesPath(varName)) for varName in VARNAMES]):
            # any output file is missing
            warnType = 'error'
        elif isDegraded:
            warnType = 'degraded'
        else:
            warnType = None

        logging.info(f'  {warnType=}')

        if not warnType:
            # the file is corrected now, so we can remove the warning
            for wt in ['error', 'degraded']:
                if os.path.exists(warnFileName(wt)):
                    logging.info(f'  removing the warning message-{wt}')
                    os.remove(warnFileName(wt))
            logging.info('normal exit')
            return

        # if warnType
        logging.info(f'  creating the warning message')
        with open(warnFileName(warnType), 'wt') as f:  # create the warning file
            f.write(f'warning details in {LOGFILE}-{warnType}')

        logging.info(f'normal exit (log file marked)')
        os.system(f'mv {LOGFILE} {LOGFILE}-{warnType}')


    def printUsage():
        print('ERROR: unrecognized input arguments')
        print('SYNTAX:')
        print('./2_nc2ascii.py')
        print('./2_nc2ascii.py YYYYMMDD')

    #
    # ---- inputs
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
    NUM_FORECASTS = 3  # [T-1], [T-2], [T-3], ...
    NUM_LEADS = 40
    NUM_ANALYSIS = 120
    ANALYSIS_START = -119 # T-119, T-118, ... T-0
    ANALYSIS_LEAD_MAX = 3
    VARNAMES = ['u850', 'olr']
    NX, NY = 49, 21
    LONW, LONE = 40, 160
    LATS, LATN = -10, 40
    RUN_ID = tt.float2format(tt.now(), '%y%m%d_%H%M%S')

    # tolerate: rooms for discontinued op output or other contingencies
    MAX_FORECAST_DELAY = 5  # forecast init delayed maximum to n (init=T-n)
    # The analysis is allowed to have 1 discontinued date that will be
    #   replaced by the interpolation of the neighboring two.
    # If 2 continuous init files are missing, then lead=2 will be used for 
    #   the analysis.
    # Will fail if 3+ continuous init files are missing

    # -- file paths
    RUNDIR = '.'
    LOGFILE = f'{RUNDIR}/logs/nc2ascii.{RUN_ID}'

    SRCDIR = f'{RUNDIR}/data/daymean'
    DESDIR = f'{RUNDIR}/data/output'

    def getDaymeanPath(initTime, varName):
        return tt.float2format(initTime, f'{SRCDIR}/%Y/%y%m%d_{varName}.nc')

    def getModelClimPath(initTime, varName):
        return tt.float2format(
            initTime, f'data/clim_mod/{varName}/global_daily_2p5_{varName}_%m%d_1991_2020_3harm.nc'
        )

    def getObsClimPath(varName):
        return f'data/clim_obs/obs_{varName}_clim_2p5.nc'

    def getDesPath(varName):
        if varName == 'olr':
            varName2 = 'OLRA'
        elif varName == 'u850':
            varName2 = 'U850'
        return tt.float2format(REFDATE, f'{DESDIR}/%Y/%Y%m%d_CWBC_{varName2}_BSISO')

    # ----- permission check
    if not os.access(DESDIR, os.W_OK):
        raise PermissionError(f'no writing permission for {DESDIR=}')
    # Assume the rest of the permission checks are already done
    # in step 1 (convert from op to nc). Skip them here.
    # -----

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
    logging.info(
        'beginning converting the nc file to ASCII format for APCC BISIO')
    logging.info(f'  {RUN_ID=}')
    logging.info(f'  REFDATE (T) = {tt.float2format(REFDATE)}')

    # ---------------------- #
    # ---- pre-checking ---- #
    # ---------------------- #
    logging.info('pre-checking')
    forecastValidDates = [REFDATE + iLead for iLead in range(1, NUM_LEADS+1)]
    #                     T+1, T+2, ..., T+40

    isDegraded = False  # mark the log file name later

    # make sure all the analysis files exist or is discontinued by only 2
    analysisInitDates, analysisValidDates, analysisLeads = [], [], []
    for delta in range(ANALYSIS_START, ANALYSIS_START+NUM_ANALYSIS):  # [T-119] to [T-1]
        validDate = REFDATE + delta
        analysisValidDates.append(validDate)

        found = False # find the init files for analysis from lead 1 to ANALYSIS_LEAD_MAX
        for lead in range(1, ANALYSIS_LEAD_MAX+1):
            initTime = validDate - lead

            if initTime == REFDATE - 1 and lead == 1:
                continue # don't use [T-1] lead 1 for analysis (or would be the same as forecast)

            paths = [getDaymeanPath(initTime, varName) for varName in VARNAMES]
            anyMissing = any([not os.path.exists(path) for path in paths])

            if anyMissing:
                continue # using the next lead

            if lead > 1 and validDate != REFDATE:
                # only allow target=T-0 using [T-2]
                isDegraded = True
                degradedReason = f'using {lead=} for analysis valid={tt.float2format(validDate)}'
                logging.warning(degradedReason)

            analysisInitDates.append(initTime)
            analysisLeads.append(lead)
            found = True
            break

        if not found: # throw an error message
            logging.error(
                f'missing file: analysis, valid={tt.float2format(validDate)}, {ANALYSIS_LEAD_MAX=}'
            )
            postCheck()
            return  # fatal error

    # find the acceptable forecast files from [T-1] to [T-n]
    numAcceptedForecasts, forecastInitDates = 0, []
    for delta in range(1, MAX_FORECAST_DELAY+1):  # [T-1], [T-2], ...
        initTime = REFDATE - delta

        paths = [getDaymeanPath(initTime, varName) for varName in VARNAMES]
        anyMissing = any([not os.path.exists(path) for path in paths])

        if anyMissing:  # unqualified
            isDegraded = True
            degradedReason = f'missing file: forecast, init={tt.float2format(initTime)}'
            logging.warning(degradedReason)
            continue

        # T-1 needs minNumLeads to be 41, T-2 needs 42, ... to align for the valids
        minNumLeads = NUM_LEADS + delta
        fileNumLeads = [nct.getVarDimLength(path, varName, 0)
                        for path, varName in zip(paths, VARNAMES)]

        if any([lead < minNumLeads for lead in fileNumLeads]):  # unqualified
            isDegraded = True
            degradedReason = f'too short numLeads: forecast, init={tt.float2format(initTime)}'
            logging.warning(degradedReason)
            continue

        numAcceptedForecasts += 1
        forecastInitDates.append(initTime)

        if numAcceptedForecasts >= NUM_FORECASTS:  # the number of needed forecast is reached
            break

    #
    # ---- check the obs clim files
    paths = [getObsClimPath(varName) for varName in VARNAMES]
    if any([not os.path.exists(path) for path in paths]):
        logging.error('file missing: obs clim not found')
        postCheck()
        return  # fatal
    # check dim shape
    shapes = [nct.getVarShape(path, varName)
              for path, varName in zip(paths, VARNAMES)]
    if any([shape[0] != 365 or shape[1] < NY or shape[2] < NX for shape in shapes]):
        logging.error('wrong file dimension: obs clim')
        postCheck()
        return  # fatal

    #
    # ---- check the model clim files: for analysis
    notFoundFiles = [
        f'{varName}_{tt.float2format(initTime, '%m%d')}'
        for initTime in analysisInitDates
        for varName in VARNAMES
        if not os.path.exists(getModelClimPath(initTime, varName))
    ]
    if notFoundFiles:
        logging.error(f'file missing: model clim {','.join(notFoundFiles)}')
        postCheck()
        return  # fatal

    leadTooShortFiles = [
        f'{varName}_{tt.float2format(initTime, '%m%d')}'
        for initTime in analysisInitDates
        for varName in VARNAMES
        if nct.getVarDimLength(getModelClimPath(initTime, varName), varName, 0) < ANALYSIS_LEAD_MAX
    ]
    if leadTooShortFiles:
        logging.error(
            f'lead too short: model clim {','.join(leadTooShortFiles)}')
        postCheck()
        return  # fatal

    #
    # ---- check the model clim files: for forecast
    notFoundFiles = [
        f'{varName}_{tt.float2format(initTime, '%m%d')}'
        for initTime in forecastInitDates
        for varName in VARNAMES
        if not os.path.exists(getModelClimPath(initTime, varName))
    ]
    if notFoundFiles:
        logging.error(f'file missing: model clim {','.join(notFoundFiles)}')
        postCheck()
        return  # fatal

    leadTooShortFiles = [
        f'{varName}_{tt.float2format(initTime, '%m%d')}'
        for initTime in forecastInitDates
        for varName in VARNAMES
        if nct.getVarDimLength(getModelClimPath(initTime, varName), varName, 0) < NUM_LEADS + MAX_FORECAST_DELAY
    ]
    if leadTooShortFiles:
        logging.error(
            f'lead too short: model clim {','.join(leadTooShortFiles)}')
        postCheck()
        return  # fatal

    if isDegraded:
        logging.warning('The output quality will be degraded.')
    else:
        logging.info('  pre-checking passed')


    logging.info(
        f'  analysis inits (T-{REFDATE-min(analysisInitDates)}'
        + f' to T-{REFDATE-max(analysisInitDates)})'
        + f' = {' to '.join([
                tt.float2format(analysisInitDates[i]) for i in [0, -1]
            ])
        }'
    )
    logging.info(
        f'  analysis valid (max_lead={max(analysisLeads)}) = {
            ' to '.join([
                tt.float2format(analysisValidDates[i]) for i in [0, -1]
            ])
        }'
    )
    logging.info(
        f'  forecast inits {
            ', '.join([f'(T-{int(REFDATE - d)})' for d in forecastInitDates])
        } = {
            ', '.join([
                tt.float2format(d) for d in forecastInitDates
            ])
        }'
    )
    logging.info(
        f'  forecast valid (T+1 to T+{NUM_LEADS}) = {
            ' to '.join([
                tt.float2format(forecastValidDates[i]) for i in [0, -1]
            ])
        }'
    )

    # ------------- #
    # ---- run ---- #
    # ------------- #
    def run(varName):
        #
        # ---- read obs clim
        logging.info(f'  reading obs clim')
        obsClim, __ = nct.ncreadByDimRange(
            getObsClimPath(varName),
            varName,
            [[-np.inf, np.inf], [LATS, LATN], [LONW, LONE]],
        )
        i228 = tt.ymd2int(2001, 2, 28) - tt.ymd2int(2001, 1, 1)
        i301 = tt.ymd2int(2001, 3, 1) - tt.ymd2int(2001, 1, 1)
        obsClim = np.concatenate(  # 365 -> 366
            (obsClim[:i228+1, :],
             0.5 * (obsClim[i228, :]+obsClim[i301, :])[None, :, :],
             obsClim[i301:, :]),
            axis=0,
        )

        #
        # ---- read analysis model clim
        logging.info(f'  reading analysis - model clim')
        minMaxs = [
            [None]*2,
            [LATS, LATN],
            [LONW, LONE],
        ]
        analysisModelClim = np.nan * np.ones((NUM_ANALYSIS, NY, NX))
        for iAnalysis, (initTime, lead) in enumerate(zip(analysisInitDates, analysisLeads)):
            minMaxs[0] = [lead]*2
            path = getModelClimPath(initTime, varName)
            analysisModelClim[iAnalysis, :], __ = nct.ncreadByDimRange(
                path, varName, minMaxs, decodeTime=False
            )

        #
        # ---- read analysis raw [lead=?, valid=(T-119, T-0), init=(T-120, T-2)]
        logging.info(f'  reading analysis - raw')
        slices = [
            None,
            slice(None, None),  # all lat
            slice(None, None),  # all lon
        ]

        analysisRaw = np.nan * np.ones((NUM_ANALYSIS, NY, NX))
        for iAnalysis, (initTime, lead) in enumerate(zip(analysisInitDates, analysisLeads)):
            slices[0] = slice(lead-1, lead) # ilead = lead - 1
            path = getDaymeanPath(initTime, varName)
            analysisRaw[iAnalysis, :] = nct.ncread(path, varName, slices)

        #
        # ---- calculate the analysis bias correction
        iDayClim366 = [tt.dayOfYear229(int(d))-1 for d in analysisValidDates]
        analysis = analysisRaw - analysisModelClim + obsClim[iDayClim366, :]

        #
        # ---- read forecast model clim
        logging.info(f'  reading forecast - model clim')
        forecastModelClim = np.nan * np.ones((NUM_FORECASTS, NUM_LEADS, NY, NX))
        for iForecast, initTime in enumerate(forecastInitDates):
            # find the lead values (they are different for each forecast init)
            leads = [vd - initTime for vd in forecastValidDates]
            minMaxs = [
                # the 1st dimension is lead for model clim
                [min(leads), max(leads)],
                [LATS, LATN],
                [LONW, LONE],
            ]
            path = getModelClimPath(initTime, varName)
            forecastModelClim[iForecast, :], __ = nct.ncreadByDimRange(
                path, varName, minMaxs, decodeTime=False
            )

        #
        # ---- read forecast raw
        logging.info(f'  reading forecast - raw')
        forecastRaw = np.nan * np.ones((NUM_FORECASTS, NUM_LEADS, NY, NX))
        minMaxs = [
            [min(forecastValidDates), max(forecastValidDates)],
            [LATS, LATN],
            [LONW, LONE],
        ]
        for iForecast, initTime in enumerate(forecastInitDates):
            path = getDaymeanPath(initTime, varName)
            forecastRaw[iForecast, :], __ = nct.ncreadByDimRange(
                path, varName, minMaxs
            )

        #
        # ---- calculate the forecast bias correction
        iDayClim366 = [tt.dayOfYear229(int(d))-1 for d in forecastValidDates]
        forecast = forecastRaw - forecastModelClim + obsClim[iDayClim366, :]

        #
        # ---- writing output
        desPath = getDesPath(varName)
        logging.info(f'  writing to {desPath}')

        if not os.path.exists(os.path.dirname(desPath)):
            os.mkdir(os.path.dirname(desPath))

        with open(desPath, 'wt') as f:
            for f_2d in analysis:
                for f_1d in f_2d:
                    f.write(' '.join([f'{value:7.2f}' for value in f_1d]))
                    f.write('\n')
            for f_3d in forecast:
                for f_2d in f_3d:
                    for f_1d in f_2d:
                        f.write(' '.join([f'{value:7.2f}' for value in f_1d]))
                        f.write('\n')

    # ------------------- #
    # ---- main loop ---- #
    # ------------------- #
    for varName in VARNAMES:
        logging.info(f'{varName=}')
        run(varName)

    #
    # ---- mark the log file for warning
    # ---- and make another warning file in the run path
    postCheck()


if __name__ == '__main__':
    main()
