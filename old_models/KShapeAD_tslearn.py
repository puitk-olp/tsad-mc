"""
This function is adapted from [TimeEval-algorithms] by [CodeLionX&wenig]
Original source: [https://github.com/TimeEval/TimeEval-algorithms]
"""

from sklearn.base import BaseEstimator, OutlierMixin
from tslearn.clustering import KShape
import numpy as np
from numpy.lib.stride_tricks import sliding_window_view
from ..utils.utility import zscore
from numpy.fft import fft, ifft
from numpy.linalg import norm, eigh

def _ncc_c_3dim(data, shift=None):
    x, y = data[0], data[1]
    den = norm(x, axis=(0, 1)) * norm(y, axis=(0, 1))

    if den < 1e-9:
        den = np.inf

    x_len = x.shape[0]
    if shift == None:
        shift = x_len - 1
    fft_size = 1 << (2 * x_len - 1).bit_length()
    cc = ifft(fft(x, fft_size, axis=0) * np.conj(fft(y, fft_size, axis=0)), axis=0)
    cc = np.concatenate((cc[-(x_len - 1):], cc[:x_len]), axis=0)
    cc_1 = np.full_like(cc, -np.inf)
    cc_1[(x_len - 1 - shift):(x_len + shift)] = cc[(x_len - 1 - shift):(x_len + shift)]

    return np.real(cc_1).sum(axis=-1) / den

class KShapeAD(BaseEstimator, OutlierMixin):
    def __init__(self, k, window_size, stride, n_jobs=1, normalize=True):
        self.k = k
        self.window_size = window_size
        self.stride = stride
        self.model = KShape(n_clusters=k)
        self.padding_length = 0
        self.normalize = normalize

    def _preprocess_data(self, X: np.ndarray) -> np.ndarray:
        flat_shape = (X.shape[0] - (self.window_size - 1), -1)  # in case we have a multivariate TS
        slides = sliding_window_view(X, window_shape=self.window_size, axis=0).reshape(flat_shape)[::self.stride, :]
        self.padding_length = X.shape[0] - (slides.shape[0] * self.stride + self.window_size - self.stride)
        print(f"Required padding_length={self.padding_length}")
        if self.normalize: slides = zscore(slides, axis=1, ddof=1)
        # return slides
        return slides.reshape(-1, self.window_size, 1)  # Reshape to 3D: (n_samples, window_size, 1)
        
    def _custom_reverse_windowing(self, scores: np.ndarray) -> np.ndarray:
        print("Reversing window-based scores to point-based scores:")
        print(f"Before reverse-windowing: scores.shape={scores.shape}")
        # compute begin and end indices of windows
        begins = np.array([i * self.stride for i in range(scores.shape[0])])
        ends = begins + self.window_size

        # prepare target array
        unwindowed_length = self.stride * (scores.shape[0] - 1) + self.window_size + self.padding_length
        mapped = np.full(unwindowed_length, fill_value=np.nan)

        # only iterate over window intersections
        indices = np.unique(np.r_[begins, ends])
        for i, j in zip(indices[:-1], indices[1:]):
            window_indices = np.flatnonzero((begins <= i) & (j-1 < ends))
            mapped[i:j] = np.nanmean(scores[window_indices])

        # replace untouched indices with 0 (especially for the padding at the end)
        np.nan_to_num(mapped, copy=False)
        print(f"After reverse-windowing: scores.shape={mapped.shape}")
        return mapped

    def fit(self, X: np.ndarray, y=None, preprocess=True) -> 'KShapeAD':
        if preprocess:
            X = self._preprocess_data(X)
        self.model.fit(X)
        return self

    def predict(self, X: np.ndarray, preprocess=True) -> np.ndarray:
        if preprocess:
            X = self._preprocess_data(X)
        clusters = self.model.predict(X)
        # diffs = np.linalg.norm(X - self.model.cluster_centers_[clusters], axis=1)

        diffs = np.zeros(len(X))
        xx = np.array(X)
        for i in range(len(X)):
            diffs[i] = 1 - _ncc_c_3dim([xx[i], self.model.cluster_centers_[int(self.model.labels_[i])]]).max()

        return self._custom_reverse_windowing(diffs)

    def fit_predict(self, X, y=None) -> np.ndarray:
        X = self._preprocess_data(X)
        X = zscore(X, axis=1, ddof=1)
        print('X: ', X.shape)
        self.fit(X, y, preprocess=False)
        return self.predict(X, preprocess=False)
