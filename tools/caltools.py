import numpy as np

def bootstrapResampling(data, numSamples, axis=0):
    data = np.swapaxes(data, 0, axis)
    newData = np.nan * np.ones((numSamples, *data.shape[1:]))
    lenDim = data.shape[0]
    indices = np.random.randint(0, lenDim, lenDim*numSamples)
    indices = np.reshape(indices, (numSamples, lenDim))
    for i in range(numSamples):
        newData[i, :] = np.nanmean(data[indices[i, :], :], axis=0)
    return np.swapaxes(newData, 0, axis)


def bootstrapResampledDifferenceLevel(data1, data2, numSamples, axis=0):
    resampledData1 = bootstrapResampling(data1, numSamples, axis)
    resampledData2 = bootstrapResampling(data2, numSamples, axis)
    return np.nansum((resampledData1>resampledData2), axis)/numSamples


def smooth(dataArray, numSmooths, axis=0, **kwargs):
    from scipy.ndimage import uniform_filter1d
    isnan = np.isnan(dataArray)
    dataArray[isnan] = 0
    dataArray = uniform_filter1d(dataArray, numSmooths, axis, mode='nearest', **kwargs)
    dataArray[isnan] = np.nan
    return dataArray

def getContinuousIntegersIntervals(inputList):
    if len(inputList) == 0:
        return [[]]
    
    if len(inputList) == 1:
        return [[inputList[0], inputList[0]]]
    
    breakers = []
    for d1, d2 in zip(inputList, inputList[1:]):
        if d2 == d1 + 1:
            continue
        breakers.append([d1, d2])

    if not breakers:
        return [[inputList[i] for i in [0, -1]]]

    intervals = [[inputList[0], breakers[0][0]]]
    for breaker1, breaker2 in zip(breakers, breakers[1:]):
        intervals.append([breaker1[1], breaker2[0]])

    intervals.append([breakers[-1][-1], inputList[-1]])
    return intervals


def mirror(levels):
    levels = list(levels)
    neg_levels = [-l for l in levels if l != 0]
    levels.extend(neg_levels)
    levels.sort()
    return levels


def w2g(LON, lon_s, lon_e):
    if lon_s is None:
        lon_s = -np.inf
    if lon_e is None:
        lon_e = np.inf
    
    if lon_s <= lon_e:
        indices = np.where(np.logical_and(lon_s <= LON, LON <= lon_e))
    else:
        indices = np.where(np.logical_or(lon_s <= LON, LON <= lon_e))

    indices = indices[0]

    if len(indices) == 0:
        print(f'[w2g] warning, no values are found, [xs, xe] = {lon_s, lon_e}, minMax(LON)=({np.min(LON)}, {np.max(LON)})')
        xs, xe = None, None
    elif len(indices) == 1:
        [xs, xe] = indices[[0, 0]]
    else:
        [xs, xe] = indices[[0, -1]]

    if xe is not None:
        xe = xe + 1  # for python indexing

    lon = LON[xs:xe]
    nx = len(lon)
    return xs, xe, nx, lon


def value2Slice(valueList, valueStart, valueEnd):
    #
    # ---- checking inputs ---- #
    if not isinstance(valueList, (list, np.ndarray)):
        raise TypeError('"valueList" must be a list.')

    valueList = list(valueList)

    for valueSmall, valueBig in zip(valueList, valueList[1:]):
        if valueSmall >= valueBig:
            raise ValueError(
                'values in "valueList" must be strictly increasing. '
                f'({valueSmall=}, {valueBig=})'
            )

    if valueStart is None:
        valueStart = -np.inf
    if valueEnd is None:
        valueEnd = np.inf

    if not isinstance(valueStart, (int, float)):
        raise TypeError('"valueStart" must be an integer of float')
    if not isinstance(valueEnd, (int, float)):
        raise TypeError('"valueEnd" must be an integer of float')
    
    if valueStart > valueEnd:
        raise ValueError(
            f'Inquiring with {valueStart=} > {valueEnd=} makes no sense.'
        )
    if valueStart > valueList[-1]:
        raise ValueError(
            f'The inquired "valueStart" is larger than the entire list: '
            f'{valueStart=} > {valueList[-1]=}'
        )
    if valueEnd < valueList[0]:
        raise ValueError(
            f'The inquired "valueEnd" is smaller than the entire list: '
            f'{valueEnd=} < {valueList[0]=}'
        )
    # TODO: is the element numeric?
    # for e in valueList:
    #     if not isinstance(e, (int, float)):
    #         raise TypeError('values in "valueList" must be integers or float.')

    #
    # ---- get sliceStart and sliceEnd ----
    for sliceStart, value in enumerate(valueList):
        if value >= valueStart:
            break
    for reversedSliceEnd, value in enumerate(valueList[::-1]):
        if value <= valueEnd:
            break

    return slice(sliceStart, len(valueList)-reversedSliceEnd)


def interp_1d(x, y, x_new, axis=0, extrapolate=False):
    '''
    This function interpolates the nd-array y(x) to y(x_new)
    along the left-most axis.
    x is an 1-d array, with the same length as the first dimension 
    of y.
    '''
    def strictly_increasing(L): return all(e1 < e2 for e1, e2 in zip(L, L[1:]))

    x = np.array(x, dtype=np.double)
    y = np.array(y, dtype=np.double)
    x_new = np.array(x_new, dtype=np.double)

    if np.array_equal(x, x_new):  # no need to interpolate
        return y

    if axis != 0:
        y = np.swapaxes(y, 0, axis)
    if x.ndim > 1:
        raise Exception(f'x.ndim must be 1 but input is {x.ndim}')
    if x_new.ndim > 1:
        raise Exception(f'x_new.ndim must be 1 but input is {x_new.dim}')
    if len(x) != y.shape[0]:
        raise Exception(f'len(x) must be the same as y.shape[0]')
    if not strictly_increasing(x):
        raise Exception('x must be strictly increasing.')
    if not strictly_increasing(x_new):
        raise Exception('x_new must be strictly increasing.')
    if not extrapolate and np.min(x_new) < np.min(x):
        raise Exception('min(x_new) must >= min(x)')
    if not extrapolate and np.max(x_new) > np.max(x):
        raise Exception('min(x_new) must <= min(x)')

    nx = len(x)
    nx_new = len(x_new)

    # find index of x to interpolate
    ixl = np.zeros((nx_new,), dtype=np.int32)
    ixr = np.zeros((nx_new,), dtype=np.int32)

    for ix_new in range(nx_new):
        dx = np.array(x_new[ix_new] - x)

        if extrapolate:
            if x_new[ix_new] < x[0]:
                ixl[ix_new] = 0
                continue
            if x_new[ix_new] > x[-1]:
                ixl[ix_new] = nx - 2
                continue

        # check the exact same grid
        ix = np.where(dx == 0)[0]
        if len(ix) and ix == 0:
            ixl[ix_new] = ix
            continue
        if len(ix) and ix != 0:
            ixl[ix_new] = ix-1
            continue

        # find the intersection
        ix = np.where(dx < 0)[0][0]
        ixl[ix_new] = ix-1

    ixr = ixl + 1

    # interpolation to y_new
    y_new = x_new - x[ixl]
    y_new /= x[ixr] - x[ixl]

    y_new = np.tile(y_new, [1 for i in range(y.ndim)])  # for broadcasting
    if y_new.ndim != 1:
        y_new = np.swapaxes(y_new, 0, y_new.ndim-1)  # for broadcasting

    y_new = y_new * (y[ixr, :] - y[ixl, :])
    y_new += y[ixl]

    if axis != 0:
        y_new = np.swapaxes(y_new, 0, axis)
    return y_new


def scores_2d(forecast, observation, lat):
    def rmse():
        rmse = (forecast-observation)**2
        rmse = np.nanmean(rmse, axis=(-1, -2), keepdims=True)
        rmse = np.sqrt(rmse)
        rmse = np.nanmean(rmse, axis=-3)
        return np.squeeze(rmse)

    def pcc2():
        up = forecast * observation
        up = np.nansum(up, axis=(-1, -2), keepdims=True)
        down = np.sqrt(np.nansum(forecast**2, axis=(-1, -2), keepdims=True))
        down *= np.sqrt(np.nansum(observation**2,
                        axis=(-1, -2), keepdims=True))
        pcc = np.nanmean(up/down, axis=-3)
        return np.squeeze(pcc)

    def acc2():
        up = forecast * observation
        up = np.nansum(up, axis=-3, keepdims=True)
        down = np.sqrt(np.nansum(forecast**2, axis=-3, keepdims=True))
        down *= np.sqrt(np.nansum(observation**2, axis=-3, keepdims=True))
        acc = np.nanmean(up/down, axis=(-1, -2))
        return np.squeeze(acc)

    weight = np.sqrt(np.cos(lat / 180 * np.pi))
    weight = np.transpose(np.tile(weight, (1, 1)))
    forecast = np.array(forecast) * weight
    observation = np.array(observation) * weight

    return rmse(), pcc2(), acc2()



def harmonicFitting(x, y, nHarmList, axis=0):
    # Calculate the harmonic fitting for y to x (in radians) in the
    # n-th harmonic orders in nHarmList
    # mask = np.logical_not( np.logical_or( np.isnan( x), np.isnan(y)))

    if not isinstance(x, np.ndarray):
        x = np.array(x)
    x = np.squeeze(x)
    if x.ndim != 1:
        raise ValueError(f'only support x.ndim = 1 but {x.shape=}')
    if not isinstance(y, np.ndarray):
        y = np.array(y)
    if x.size != y.shape[axis]:
        raise ValueError(
            f'x ({x.size}) and y ({y.shape[axis]}) have inconsistent length at {axis=}')

    # ===========================================
    # permute axes
    y = np.swapaxes(y, axis, 0)
    x = np.tile(x, (1 for __ in range(y.ndim)))
    x = np.swapaxes(x, -1, 0)

    # ===========================================
    # begin
    yHat = np.repeat(np.nanmean(y, axis=0, keepdims=True), len(x), axis=0)

    for nHarm in nHarmList:
        c = np.nanmean(y * np.exp(-1j * x * nHarm), axis=0)
        amp = 2 * np.absolute(c)
        phase = np.angle(c)
        yHat += amp * np.cos(nHarm * x + phase)

    # ===========================================
    # inverse permuting axes
    yHat = np.swapaxes(yHat, 0, axis)

    return yHat


def bandPassFilter(data, freq_low, freq_high, sampling_frequency=1, axis=0):
    data = np.swapaxes(data, axis, -1)
    # Perform FFT on the data
    fft_data = np.fft.fft(data, axis=-1)
    frequencies = np.fft.fftfreq(data.shape[-1], 1/sampling_frequency)

    # Create a frequency mask to keep only the frequencies within the band-pass range
    mask = (np.abs(frequencies) >= freq_low) & (np.abs(frequencies) <= freq_high)

    # Apply the mask to the FFT data
    filtered_fft_data = fft_data * mask

    # Perform the inverse FFT to get the filtered signal back in the time domain
    filtered_data = np.fft.ifft(filtered_fft_data, axis=-1)

    filtered_data = np.swapaxes(filtered_data, axis, -1)
    return filtered_data


def smoothNans1d(data, axis):
    data = np.swapaxes(data, axis, 0)

    mask = np.isnan(data)
    smoothData = np.copy(data)
    smoothData[1:-1, :] = np.nanmean(
        np.concatenate(
            (data[None, :-2 , :], data[None, 2: , :])
        , axis=0
        ),
        axis=0
    )

    data[mask] = smoothData[mask]

    data = np.swapaxes(data, axis, 0)
    return data