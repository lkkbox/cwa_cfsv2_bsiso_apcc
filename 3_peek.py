#!/nwpr/gfs/com120/.conda/envs/rd/bin/python
'''
create the figure to quickly compare with the obs data,
works on ln23 (obs data location)
'''
import tools.timetools as tt
import tools.nctools as nct
import tools.caltools as ct
import matplotlib.pyplot as plt
import numpy as np


def main():
    varName, clevs = 'OLRA', np.r_[180:320+10:10]
    varName, clevs = 'U850', [-12, -9, -6, -3, 0, 3, 6, 9, 12]
    refDate = tt.ymd2float(2025, 1, 25)
    path = tt.float2format(
        refDate, f'./data/output/%Y/%Y%m%d_CWACFS2_0_{varName}_BSISO',
    )

    LON = np.r_[40:160+1:2.5]
    LAT = np.r_[-10:40+1:2.5]
    TIME_ANALYSIS = [refDate - 120 + delta for delta in range(120)]
    TIME_FORECAST = [refDate + delta for delta in range(40)]

    #
    # ---- read output
    with open(path, 'rt') as f:
        lines = f.readlines()

    data = np.array([[float(num) for num in line.split()] for line in lines])
    data = np.reshape(data, (240, 21, 49))

    analysis = data[:120, :]
    forecast = np.reshape(data[120:, :], (3, 40, 21, 49))

    #
    # ---- read obs
    if varName == 'U850':
        obs = np.nan * np.ones((160, 21, 49))
        for iDate in range(160):
            path = tt.float2format(
                refDate - 120 + iDate,
                f'/nwpr/gfs/com120/9_data/ERA5/nearRealTime/daymean/ERA5_u_%Y%m%d_r720x360_1day.nc'
            )
            data, dims = nct.ncreadByDimRange(
                path, 'u', [[-np.inf, np.inf], [850, 850], [-10, 40], [40, 160],],
            )
            data = np.squeeze(data, axis=(0, 1))
            data = ct.interp_1d(dims[-1], data, LON, axis=-1, extrapolate=True)
            data = ct.interp_1d(dims[-2], data, LAT, axis=-2, extrapolate=True)
            obs[iDate, :] = data

    elif varName == 'OLRA':
        obs, dims = nct.ncreadByDimRange(
            '/nwpr/gfs/com120/9_data/NOAA_OLR/olr.cbo-1deg.day.mean.nc',
            'olr',
            [[refDate-120, refDate+39], [-10, 40], [40, 160]],
        )
        obs = ct.interp_1d(dims[-1], obs, LON, axis=-1, extrapolate=True)
        obs = ct.interp_1d(dims[-2], obs, LAT, axis=-2, extrapolate=True)

    obs_analysis = obs[:120, :]
    obs_forecast = obs[120:, :]

    #
    # ----- plot
    figName = f'./peeks_{varName}.png'
    cmap='jet'
    fig = plt.figure(figsize=(12,9), layout='constrained')

    for iData, data in enumerate([obs_analysis, analysis, obs_forecast, *forecast]):
        if iData == 0:
            time = TIME_ANALYSIS
            title = 'obs (for analyis)'
        elif iData == 1:
            time = TIME_ANALYSIS
            title = 'model analyis'
        elif iData == 2:
            time = TIME_FORECAST
            title = f'obs (for forecast)'
        else:
            time = TIME_FORECAST
            title = f'model forecast (m={iData})'

        # ----- x mean (analysis)
        ax = plt.subplot(6, 3, iData*3 + 1)
        ax.set_xlabel('y')
        ax.set_ylabel('t')
        ax.set_title(title)
        x = LAT
        y = time
        z = np.mean(data, -1)
        hc = ax.contourf(x, y, z, cmap=cmap, levels=clevs, extend='both')
        fig.colorbar(hc)

        # ----- y mean
        ax = plt.subplot(6, 3, iData*3 + 2)
        ax.set_xlabel('x')
        ax.set_ylabel('t')
        ax.set_title(title)
        x = LON
        y = time
        z = np.mean(data, -2)
        hc = ax.contourf(x, y, z, cmap=cmap, levels=clevs, extend='both')
        fig.colorbar(hc)

        # ----- t mean
        ax = plt.subplot(6, 3, iData*3 + 3)
        ax.set_xlabel('x')
        ax.set_ylabel('y')
        ax.set_title(title)
        x = LON
        y = LAT
        z = np.mean(data, -3)
        hc = ax.contourf(x, y, z, cmap=cmap, levels=clevs, extend='both')
        fig.colorbar(hc)


    fig.savefig(figName)

if __name__ == '__main__':
    main()
