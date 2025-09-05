#!/bin/sh

# [CRONTAB]
# 0 8 * * * cd /path/to/rundir && run.sh > run.out
#           (8 a.m. should be good, see the op output time for reference)

#
# ---- setup
PYTHON="/nwpr/gfs/com120/.conda/envs/rd/bin/python"
pyFiles="1_convertOp2nc.py 2_nc2ascii.py" # files for running
runDir="$(dirname "$(realpath "$0")")"  # auto, run directory (path=$runDir/$pyFiles)

#
# ---- go to the run dir
cd $runDir >/dev/null 2>&1
if [ ! $? -eq 0 ]; then
    echo "failed to change dir to run dir: $runDir"
    exit 1
fi

#
# ---- validate the input reference date (default set to today)
if [ -z "$1" ]; then
    refDate=`date +%Y%m%d`
else
    input="$1"
    if [[ "$input" =~ ^[0-9]{4}[0-9]{2}[0-9]{2}$ ]]; then
        # Further validation to check if it's a valid date
        if date -d "$input" >/dev/null 2>&1; then
            refDate="$1"
        else
            echo "The date $input is not a valid date."
            exit 1
        fi
    else
        echo "Invalid format. Please enter a date in YYYYMMDD format."
        exit 1
    fi
fi

#
# ---- validate the python path
"$PYTHON" --version >/dev/null 2>&1
if [ ! $? -eq 0 ]; then
    echo "python failed (received errors from $PYTHON --version)"
    exit 1
fi

#
# ---- check the file existence
for pyFile in $pyFiles; do
    if [ ! -f "$pyFile" ]; then
        echo "file not found: $pyFile"
        exit 1
    fi
done

#
# ---- begin running
echo "rundir = $runDir"
echo "reference date = $refDate"

for pyFile in $pyFiles; do
    echo "running $pyFile"
    "$PYTHON" "$pyFile" "$refDate"
    echo "  exit code = $?"
done
echo "exiting run.sh"
