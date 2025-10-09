#!/bin/sh
# ---- ---- ---- ---- #
# setup the running directory
# and copy the necessary data
#
# change the source hostname "h6dm23" to IP if necessary
# ---- ---- ---- ---- #

runDir="$(dirname "$(realpath "$0")")"  # get the current directory as prefix


# copy the code and clim file
# (daymean files are optional, but copying is much faster than processing them again)
rsync -ruPavL \
        --exclude="tmps" --exclude="logs" --exclude="*.png" \
        h6dm23:/nwpr/gfs/com120/7_CFS_BSISO_APCC/3_op/ $runDir
        # \ # --exclude="data/daymean" \


# linking op output directory to local
if [ ! -L $runDir/data/op_src ]; then
    ln -s /nwpr/cfsop/cfsaoper/P6/OP/WORKING/tcoTL359l60m550x50oocb4_rsmwrk $runDir/data/op_src
fi


# making directory
mkdir -p $runDir/tmps
mkdir -p $runDir/logs
mkdir -p $runDir/data/daymean
mkdir -p $runDir/data/output


# make .py and .sh executable
chmod 744 $runDir/*.py
chmod 744 $runDir/*.sh


# getting this 250128 file is necessary because the op source is missing
mkdir -p $runDir/data/daymean/2025
rsync -avu h6dm23:/nwpr/gfs/com120/7_CFS_BSISO_APCC/3_op/data/daymean/2025/250128_*.nc $runDir/data/daymean/2025
rsync -avu h6dm23:/nwpr/gfs/com120/7_CFS_BSISO_APCC/2_clim_re_sata20/data/clim/3harm/* $runDir/data/clim_mod/
