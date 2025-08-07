import math
import numpy as np
import multiprocessing
from numpy.random import randint
from numpy.linalg import norm, eigh
from numpy.fft import fft, ifft
from sklearn.base import ClusterMixin, BaseEstimator
from numpy.lib.stride_tricks import sliding_window_view


# import matplotlib
# matplotlib.use('TkAgg')
# import matplotlib.pyplot as plt


def zscore(a, axis=0, ddof=0):
    a = np.asanyarray(a)
    mns = a.mean(axis=axis)
    sstd = a.std(axis=axis, ddof=ddof)

    if axis and mns.ndim < a.ndim:
        res = ((a - np.expand_dims(mns, axis=axis)) /
               np.expand_dims(sstd, axis=axis))
    else:
        res = (a - mns) / sstd

    return np.nan_to_num(res)


def roll_zeropad(a, shift, axis=None):
    a = np.asanyarray(a)

    if shift == 0:
        return a

    if axis is None:
        n = a.size
        reshape = True
    else:
        n = a.shape[axis]
        reshape = False

    if np.abs(shift) > n:
        res = np.zeros_like(a)
    elif shift < 0:
        shift += n
        zeros = np.zeros_like(a.take(np.arange(n - shift), axis))
        res = np.concatenate((a.take(np.arange(n - shift, n), axis), zeros), axis)
    else:
        zeros = np.zeros_like(a.take(np.arange(n - shift, n), axis))
        res = np.concatenate((zeros, a.take(np.arange(n - shift), axis)), axis)

    if reshape:
        return res.reshape(a.shape)
    else:
        return res


def _ncc_c_3dim(data, shift):
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


def _sbd(x, y, shift):
    ncc = _ncc_c_3dim([x, y], shift)
    idx = np.argmax(ncc)
    yshift = roll_zeropad(y, (idx + 1) - max(len(x), len(y)))
    return yshift


def collect_shift(data, shift):
    x, cur_center = data[0], data[1]
    if np.all(cur_center == 0):
        return x
    else:
        return _sbd(cur_center, x, shift)


def _extract_shape(idx, x, j, cur_center, shift):
    _a = []
    for i in range(len(idx)):
        if idx[i] == j:
            _a.append(collect_shift([x[i], cur_center], shift))

    a = np.array(_a)

    if len(a) == 0:
        indices = np.random.choice(x.shape[0], 1)
        return np.squeeze(x[indices].copy())
        # return np.zeros((x.shape[1]))

    columns = a.shape[1]
    y = zscore(a, axis=1, ddof=1)

    s = np.dot(y[:, :, 0].transpose(), y[:, :, 0])
    p = np.empty((columns, columns))
    p.fill(1.0 / columns)
    p = np.eye(columns) - p
    m = np.dot(np.dot(p, s), p)

    _, vec = eigh(m)
    centroid = vec[:, -1]

    finddistance1 = np.sum(np.linalg.norm(a - centroid.reshape((x.shape[1], 1)), axis=(1, 2)))
    finddistance2 = np.sum(np.linalg.norm(a + centroid.reshape((x.shape[1], 1)), axis=(1, 2)))

    if finddistance1 >= finddistance2:
        centroid *= -1

    return zscore(centroid, ddof=1)


def _kshape(x, k, shift, centroid_init='zero', max_iter=100, n_jobs=1):
    m = x.shape[0]
    idx = randint(0, k, size=m)
    if centroid_init == 'zero':
        centroids = np.zeros((k, x.shape[1], x.shape[2]))

    elif centroid_init == 'random':
        indices = np.random.choice(x.shape[0], k)
        centroids = x[indices].copy()
    distances = np.empty((m, k))

    for it in range(max_iter):
        for j in range(k):
            for d in range(x.shape[2]):
                centroids[j, :, d] = _extract_shape(idx, np.expand_dims(x[:, :, d], axis=2), j,
                                                    np.expand_dims(centroids[j, :, d], axis=1), shift)
                # centroids[j] = np.expand_dims(_extract_shape(idx, x, j, centroids[j]), axis=1)

        old_idx = idx
        pool = multiprocessing.Pool(n_jobs)
        args = []
        for p in range(m):
            for q in range(k):
                args.append(([x[p, :], centroids[q, :]], shift))
        result = pool.starmap(_ncc_c_3dim, args)
        pool.close()
        r = 0
        for p in range(m):
            for q in range(k):
                distances[p, q] = 1 - result[r].max()
                r = r + 1

        idx = distances.argmin(1)
        if np.array_equal(old_idx, idx):
            break

    return idx, centroids


def kshape(x, k, shift, centroid_init='zero', max_iter=100):
    idx, centroids = _kshape(np.array(x), k, centroid_init=centroid_init, max_iter=max_iter, shift=shift)
    clusters = []
    for i, centroid in enumerate(centroids):
        series = []
        for j, val in enumerate(idx):
            if i == val:
                series.append(j)
        clusters.append((centroid, series))

    return clusters


class KShapeAD(ClusterMixin, BaseEstimator):
    labels_ = None
    centroids_ = None

    def __init__(self, n_clusters, centroid_init='zero', max_iter=100, n_jobs=None, stride=1, window_size=20,
                 shift=None):
        self.n_clusters = n_clusters
        self.centroid_init = centroid_init
        self.max_iter = max_iter
        self.stride = stride
        if self.stride < 1:
            self.stride = 1
        self.padding_length = 0
        self.n_clusters = n_clusters
        self.window_size = window_size
        self.shift = shift
        if n_jobs is None:
            self.n_jobs = 1
        elif n_jobs == -1:
            self.n_jobs = multiprocessing.cpu_count()
        else:
            self.n_jobs = n_jobs

    def _preprocess_data(self, X: np.ndarray) -> np.ndarray:
        flat_shape = (X.shape[0] - (self.window_size - 1), -1)  # in case we have a multivariate TS
        slides = sliding_window_view(X, window_shape=self.window_size, axis=0).reshape(flat_shape)[::self.stride, :]
        self.padding_length = X.shape[0] - (slides.shape[0] * self.stride + self.window_size - self.stride)
        print(f"Required padding_length={self.padding_length}")
        return slides

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
            window_indices = np.flatnonzero((begins <= i) & (j - 1 < ends))
            # print(i, j, window_indices)
            mapped[i:j] = np.nanmean(scores[window_indices])

        # replace untouched indices with 0 (especially for the padding at the end)
        np.nan_to_num(mapped, copy=False)
        print(f"After reverse-windowing: scores.shape={mapped.shape}")
        return mapped

    def fit(self, X, y=None, preprocess=True):
        if preprocess:
            X = self._preprocess_data(X)
            X = zscore(X, axis=1, ddof=1)
            X = np.expand_dims(X, axis=2)
        clusters = self._fit(X, self.n_clusters, self.shift, self.centroid_init, self.max_iter, self.n_jobs)
        self.labels_ = np.zeros(X.shape[0])
        self.centroids_ = np.zeros((self.n_clusters, X.shape[1], X.shape[2]))
        for i in range(self.n_clusters):
            self.labels_[clusters[i][1]] = i
            self.centroids_[i] = clusters[i][0]
        return self

    def predict(self, X, preprocess=True):
        if preprocess:
            X = self._preprocess_data(X)
            X = zscore(X, axis=1, ddof=1)
            X = np.expand_dims(X, axis=2)
        labels, _ = self._predict(X, self.centroids_, self.shift)
        return labels

    def _predict(self, x, centroids, shift):
        m = x.shape[0]
        idx = randint(0, self.n_clusters, size=m)
        distances = np.empty((m, self.n_clusters))

        pool = multiprocessing.Pool(self.n_jobs)
        args = []
        for p in range(m):
            for q in range(self.n_clusters):
                args.append(([x[p, :], centroids[q, :]], shift))
        result = pool.starmap(_ncc_c_3dim, args)
        pool.close()
        r = 0
        for p in range(m):
            for q in range(self.n_clusters):
                distances[p, q] = 1 - result[r].max()
                r = r + 1

        idx = distances.argmin(1)

        return idx, centroids

    def _fit(self, x, k, shift, centroid_init='zero', max_iter=100, n_jobs=1):
        idx, centroids = _kshape(np.array(x), k, shift=shift, centroid_init=centroid_init, max_iter=max_iter,
                                 n_jobs=n_jobs)
        clusters = []
        for i, centroid in enumerate(centroids):
            series = []
            for j, val in enumerate(idx):
                if i == val:
                    series.append(j)
            clusters.append((centroid, series))

        return clusters

    def getAnomalyScore(self, X):
        X = self._preprocess_data(X)
        X = zscore(X, axis=1, ddof=1)
        X = np.expand_dims(X, axis=2)
        anomaly_score = np.zeros(len(X))
        xx = np.array(X)
        for i in range(len(X)):
            anomaly_score[i] = 1 - _ncc_c_3dim([xx[i], self.centroids_[int(self.labels_[i])]], self.shift).max()
        return self._custom_reverse_windowing(anomaly_score)


