# import time
# import matplotlib.pyplot as plt

import numpy as np


def highlightMeteorPath(input_img, rho, phi, path_width=20):
    """ Draws two guides parallel to the meteor so it highlights the detection. 

        input_img: numpy array containing a grayscale image
        rho: HT parameter (distance from the center of the image)
        thera: HT parameter (counter-clockwise positive from the +horizontal axis)
        path_width: distance from the meteor to individual guide (pixels)
    """

    def checkUpperLimits(x, y, x_lim, y_lim):
        """ Checks if given points are within the image. """
        if (x<x_lim) and (y<y_lim):
            return (x, y)
        return (-1, -1)

    # Vectorize the checkUpperLimits function
    checkUpperLimits = np.vectorize(checkUpperLimits, excluded=['x_lim', 'y_lim'])

    y_size, x_size = len(input_img), len(input_img[0])

    phi = np.radians(phi+90)

    a = np.cos(phi)
    b = np.sin(phi)

    for width in [-path_width, path_width]:

        rho_expanded = rho + width

        # HT coodrinate system is a bit modified, it starts in the middle of the image
        x0 = a*rho_expanded + int(y_size/2)
        y0 = b*rho_expanded + int(x_size/2)

        img_diag = int(np.sqrt(x_size**2 + y_size**2))

        x1 = int(x0 + img_diag*(-b))
        y1 = int(y0 + img_diag*(a))
        x2 = int(x0 - img_diag*(-b))
        y2 = int(y0 - img_diag*(a))

        length = int(np.hypot(x2-x1, y2-y1))
        x, y = np.linspace(x1, x2, length), np.linspace(y1, y2, length)

        # Convert from row vector to column vector
        # Take only every 5th element
        x = x.astype(int)[::5]
        y = y.astype(int)[::5]

        # Check pixels for upper limit (y_size and x_size are intentianally reversed) and remove them
        x, y = checkUpperLimits(x, y, x_lim = y_size, y_lim = x_size)

        x = np.reshape(x, (-1, 1))
        y = np.reshape(y, (-1, 1))

        points = np.hstack((x, y))

        # Remove all values less then zero
        points = points[~(points < 0).any(1)]

        x, y = np.hsplit(points, 2)

        x = np.reshape(x, (1, -1))
        y = np.reshape(y, (1, -1))

        input_img[x, y] = 255

    return input_img


# img_name = 'FF459_20150411_010051_555_0607232.bin 0001  X _maxpixel.bmp'

# input_img = plt.imread(img_name)

# s1 = time.clock()
# img = highlightMeteorPath(input_img, -194, 75)

# print time.clock() - s1

# plt.imshow(img, cmap = "gray")
# plt.show()
