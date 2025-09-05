The source files (both clim data and code) are located on ln23,
then copied to ln16 for operational running.


---- ---- run ---- ----
1. create a directory for running (let's call it RUNDIR)
2. copy "0_setup.sh" into RUNDIR and execute it
3. try "run.sh > run.out"
4. check the on-screen output or ./logs for errors
5. install to crontab: "00 08 * * * cd $RUNDIR && sh run.sh > run.out"


---- ---- logic ---- ----
output is created everyday
    variables: u850, olr
    area: 10S-40N, 40-160E, 2p5
    forecast: 40 days, T+1 to T+40 (T = reference date. Square braketed times denote init dates.)
    analysis: 120 days, T-119 to T

forecasts (three members from three init time steps):
    valid for T+1, T+2, ..., T+40, | backup plan ("degraded" outputs) for missing files:
    lead =    2~41, 3~42, 4~43     |   lead = 5~44,  6~45
    init from [T-1], [T-2], [T-3], |   init = [T-4], [T-5]

analysis:
    valid for T-119, T-118, ..., T-1, T-0         | backup plan for missing files: 
    lead = 1, 1,            ..., 1,   2           |   (1) using the neighboring dates to average
    init from [T-120], [T-119], ..., [T-2], [T-2] |   (2) using lead=2
                                                      i.e, fail if 3 continuous files are missing

degraded output:
    The output is degraded when switched to the backup plan. A warning message will be
    created in the run directory. The warning message will be removed if a new output 
    is updated by the expected normal procedures (left hand side of the above tow paragraphs).

steps:
    source (grib2 or tarred grib2)
1_convertOp2nc.py
    It cuts out the needed data from source files to nc.
    The date will be auto skipped if the source file does not exist,
                                     or the middle nc file already exists.
2_nc2ascii.py
    It aligns the forecasts and analysis, calculates the bias correction,
    and creates the output.
(3_peeks.py)
    check: draw the output and compare to the reanalysis


---- ---- CFSv2 operation timing ---- ----
    e.g., for init: 2025/03/09 00Z
    daymean output finished in 2025/03/09 20:00L ~ 2025/03/10 10:00L 
    (but the nearest 40 day forecast is earlier, so run at 08:00L should be ok)
    -> latest output varilable = [T-1]


---- ---- output format ---- ----
analysis (120 days x 21 lats x 49 lons)
forecast (3 inits x 40 days x 21 lats x 49 lons)

write lons on each line,
    then nesting loops for lat -> time -> inits

L1: analysis t=1, y=1, x=1~49
L2: analysis t=1, y=2, x=1~49
    ...
L21: analysis t=1, y=21, x=1~49
L22: analysis t=2, y=1, x=1~49
    ...
L(120*21): analysis t=120, y=21, x=1~49
L(120*21+1): forecast i=1, t=1, y=1, x=1~49
L(120*21+2): forecast i=1, t=1, y=2, x=1~49
           ...
L(120*21+40*21):   forecast i=1, t=40, y=21, x=1~49
L(120*21+40*21+1): forecast i=2, t=1, y=11, x=1~49
                 ...

---- ---- known missing files ---- ----
    init 2025/01/28 -> still exists on SILO, manually downloaded and processed
        ln23:/nwpr/gfs/com120/7_CFS_BSISO_APCC/3_op/data/daymean/2025/250128_*.nc


---- ---- paths ---- ----
model data
    on ln16/17:
        - /nwpr/cfsop/cfsaoper/P6/OP/WORKING/tcoTL359l60m550x50oocb4_rsmwrk
        - /cfsdata/cfsaoper/P6/OP/CWBCFSv2/gsmdm/gsmdm_source
    on silo: /op/arc/cfm/P6/CWBCFSv2
    on sata1 (accessible from rdccs1): /syn_sata1/users/cfsoper/P6/CWBCFSv2/gsmdm/gsmdm_source

model clim data
    on ln23: /nwpr/gfs/com120/9_data/models/processed/re_cfsv2_dm/1991

ERA5 data for comparison (3_peek.py)
    on ln23: /nwpr/gfs/com120/9_data/ERA5/nearRealTime/daymean

code: on ln23 /nwpr/gfs/com120/7_CFS_BSISO_APCC
