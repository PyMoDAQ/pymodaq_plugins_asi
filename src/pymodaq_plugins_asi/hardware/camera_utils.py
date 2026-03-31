import numpy as np
import math

def bin2d(array : np.ndarray, x : int,y : int) -> np.ndarray:
    """
    Summing over 2d arrays for SNR improvement.

    Parameters
    ----------
    array : np.ndarray
        input bi-dimensional data.
    x : int
        Size reduction factor of the 1-st axis
    y : int
        Size reduction factor of the 0-th axis

    Returns
    -------
    binned_arrray : np.ndarray
        Summed array with reduced size
    """
    x_bins = array.shape[1]//x
    y_bins = array.shape[0]//y
    binned_array =  array.reshape(y_bins,y,x_bins,x).sum(axis=3).sum(axis=1)
    # We want array that have shape e.g. (y,1) to reduce to (y,).
    if binned_array.shape[1] == 1 :
        binned_array = binned_array.sum(axis = 1)
    if binned_array.shape[0] == 1 :
        binned_array = binned_array.sum(axis = 0)
    return binned_array
    # https://stackoverflow.com/questions/61325586/fast-way-to-bin-a-2d-array-in-python

def get_bin_list(size) :
    """
    Produces the list of binning factors for powers of 2 shape (has a default value for other shapes)
    TODO : Improve this function to produce binning factors for any integer.

    Parameters
    ----------
    size : int
        size of the data array to be binned. e.g. data.shape[0]

    Returns
    -------
    bin_list : list[int]
        The list of binning factors

    Notes
    -----
    For example `get_bin_list(256)` will return [1,2,4,8,16,32,64,128,256]
    """
    bin_list = []
    # Either we get the power of two of the input size (integer) or the input number is not a power of two.
    power = math.log(size,2) 
    if power.is_integer() :
        for i in range(round(power + 1)) :
            bin_list.append(size//(2**i))
    else : 
        bin_list = [size,1]
    # Better to reverse for display reasons
    bin_list.reverse()
    return bin_list