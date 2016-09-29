import itertools

import numpy as np
from scipy import linalg
import matplotlib.pyplot as plt
import matplotlib as mpl

from sklearn import mixture

# Number of samples per component
n_samples = 10

# Generate random sample, two components
np.random.seed(0)
C = np.array([[0., -0.1], [1.7, .4]])
print C
#X = np.r_[np.dot(np.random.randn(n_samples, 2), C),.7 * np.random.randn(n_samples, 2) + np.array([-6, 3])]
#print X
