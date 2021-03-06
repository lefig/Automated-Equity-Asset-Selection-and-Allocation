import numpy as np
import csv
import re
from sklearn import svm
from sklearn import metrics
from datetime import datetime

from sklearn.model_selection import GridSearchCV
from sklearn.model_selection import KFold
from sklearn.model_selection import cross_val_score
from sklearn.preprocessing import Imputer
from sklearn.preprocessing import scale
from sklearn.neural_network import MLPClassifier
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.ensemble import RandomForestClassifier
from collections import Counter


from keras.models import Sequential
from keras.layers import Dense
from keras.layers import Dropout
from keras.layers import SimpleRNN

from keras.layers.embeddings import Embedding
from keras.preprocessing import sequence

import tensorflow as tf
from tensorflow.python.ops import rnn, rnn_cell

# no sector, matketCap feature right now

class learning:
    def __init__(self, date_start, date_end, date_type, sortino_rate=.5, testYear=2016):
        self.start, self.end, self.dType = date_start, date_end, date_type
        self.rate, self.testYear = sortino_rate, testYear
        self.loadFile()
        self.dataProcressing()

    def loadFile(self):
        typePar = "_".join([self.start, self.end])
        # load feature names
        self.feature_names = np.loadtxt("./output/selected_feature_" + typePar, dtype='str')
        # load feature_label file, 1st col as tickers, last col as label
        dat = np.loadtxt("./input/feature_label_" + typePar, delimiter=',', dtype='str')
        self.tickers = dat[:,0]
        self.feature = dat[:, 1:np.shape(dat)[1] - 8].astype(np.float)
        self.label = {}
        for i in range(5): # the last 8 cols are labels in the most recent 8 years
            self.label[i] = dat[:,-5 + i].astype(np.float)
        
        self.fticker = open('./output/tickers_' + "_".join([self.start, self.end]), 'w')
        self.fout = open('./output/result_' + "_".join([self.start, self.end]), 'a+') # save to local

        curtime = str(datetime.now())

        self.ptLocal(self.fout, "\n\nToday: %s",curtime[:len(curtime) - 10])
        self.ptLocal(self.fout, "Training data based on period: %s", \
            "2006-" + str(self.testYear - 1))

    # both print to screen and output to file
    def ptLocal(self, fout, content, pars): # pars should be an array
        print(content % (pars))
        content += "\n"
        fout.write(content % (pars))

    def dataProcressing(self):
        # increase training data by combining time horizon
        # 2006-2011, 2007-2012, 2008-2013, 2009-2014, 2010-2015, excluding TTM
        # 2006-2010, ...
        startYear = 2011
        for i in range(startYear, self.testYear):
            # tag time window to shift, increase the training data
            tag0 = self.selectedTime(self.feature_names, i - 5, i, 0)
            num = i - startYear # corresponds to the last 5 cols
            tag1 = ~np.isnan(self.label[num]) # tag non-None value as true
            if i == startYear: # 1st col in label taken as initialization
                self.X, self.y = self.feature[tag1][:,tag0], self.label[num][tag1]
            elif i < self.testYear - 1:
                self.X = np.vstack([self.X, self.feature[tag1][:,tag0]])
                self.y = np.concatenate([self.y, self.label[num][tag1]])
            elif i == self.testYear - 1: # last col taken as test data
                self.X_test, self.expected = self.feature[tag1][:,tag0], self.label[num][tag1]
        
        # define our label 1 if the sortino ratio is higher than the threshold
        self.y[self.y < self.rate], self.expected[self.expected < self.rate] = 0, 0
        self.y[self.y >= self.rate], self.expected[self.expected >= self.rate] = 1, 1
        self.y, self.expected = self.y.astype(int), self.expected.astype(int)

        # sample number
        n_samples = len(self.tickers)
        self.ptLocal(self.fout, "Feature dimension (sample, training feature): %d %d\n", \
            np.shape(self.X))
        # count the number of each label
        label_cnt = Counter(self.y)
        for _ in label_cnt:
            self.ptLocal(self.fout, "Label %d number: %d", (_, label_cnt[_]))
        self.ptLocal(self.fout, "Random pick successful rate: %.3f\n",\
            round(float(sum(self.expected)) / len(self.expected), 3))
        # cross validation
        self.K = 3
        self.k_fold = KFold(self.K)

    def selectedTime(self, names, year0, year1, ifTTM): # year1 as int
        tag = np.repeat(True, len(names))
        for num, name in enumerate(names):
            m = re.search("_(\d{4}|TTM)$", name)
            if m:
                date = m.group(1)
                if date == "TTM" and not ifTTM: tag[num] = False
                elif int(date) > year1 or int(date) < year0:
                    tag[num] = False
        return tag


    def SVM(self):      
        #choose the best C and gamma
        best, scores = 0, {}
        self.ptLocal(self.fout, "\nChoose best parameters\n", ())
        for c in np.logspace(1, 8, 10): # (s, e, n) means: n number starting from 10^s to 10^e
            for gamma in np.logspace(-7, -2, 10):
                score = []
                for k, (train, test) in enumerate(self.k_fold.split(self.X, self.y)):
                    clf = svm.SVC(C=c, gamma=gamma)
                    clf.fit(self.X[train], self.y[train])
                    score.append(clf.score(self.X[test], self.y[test]))
                if min(score) > best:
                    best = min(score)
                    self.ptLocal(self.fout, "C = %.1e, gamma = %.1e, score = %.3f\n", \
                        (c, gamma, best))
        
        print np.shape(self.X_test)
        predicted = clf.predict(self.X_test)
        
        self.ptLocal(self.fout, "Classification report for classifier %s:\n%s\n", \
            (clf, metrics.classification_report(self.expected, predicted)))
        self.ptLocal(self.fout, "Confusion matrix:\n%s", \
            metrics.confusion_matrix(self.expected, predicted))

        
        tickers_pred = self.tickers[predicted.astype(bool)].tolist()
        self.fticker.write(",".join(tickers_pred))
        print "Possible ticker number:", len(tickers_pred)
        print "Random pick successful ratio: ", \
            round(float(sum(self.expected)) / len(self.expected), 3)

    def allNeuralNet(self):
        def combine(n, k): # generate Combination 
            if k == 1:
                return [[i] for i in range(1, n+1)]
            if n == k:
                return [[i for i in range(1, n+1)]]
            return [i for i in combine(n-1, k)] + [i + [n] for i in combine(n-1,k-1)]
        
        best = 0
        for layer_n in range(1, 4): # number of layers
            layers = combine(20, layer_n) # combination of layers
            for layer in layers:
                if layer[0] == 1: continue # hidden layer should have more than 1 node
                layer = sorted(layer, reverse=True)
                layer.insert(layer_n, 2)
                score = [0] * self.K
                for k, (train, test) in enumerate(self.k_fold.split(self.X, self.y)):
                    clf = MLPClassifier(solver='lbfgs', alpha=1e-5, early_stopping=True, \
                        hidden_layer_sizes=layer, random_state=1, momentum=0.5, \
                        max_iter=10 ** 5)
                    clf.fit(self.X[train], self.y[train])
                    #score[k] = clf.score(self.X[test], self.y[test]) # if we care the whole
                    predicted = clf.predict(self.X[test])
                    score_mat = metrics.confusion_matrix(self.y[test], predicted)

                    if score_mat[1, 1] < 30: continue # only care label-1 performance
                    recall = float(score_mat[1, 1]) / sum(score_mat[1])
                    precision = float(score_mat[1, 1]) / sum(score_mat[:, 1])
                    #score[k] = 1 / ((1 / recall + 1 / precision) / 2) # f1 score
                    score[k] = precision
                #if min(score) <= best: continue # only update if we have better result
                best, idx = min(score), score.index(min(score))
                self.ptLocal(self.fout, "\nLayers: %s", ("-".join(np.array(layer, dtype=str))))
                self.ptLocal(self.fout, "Confusion matrix:\n%s", score_mat)
                self.ptLocal(self.fout, "Label 1 expected precision: %.3f\n", best)
                clf.fit(self.X, self.y)
                predicted = clf.predict(self.X_test)
                self.ptLocal(self.fout, "Classification report for classifier %s:\n%s", \
                    (clf, metrics.classification_report(self.expected, predicted)))
                self.ptLocal(self.fout, "Confusion matrix:\n%s", \
                    metrics.confusion_matrix(self.expected, predicted))
                tickers_pred = self.tickers[predicted.astype(bool)].tolist()
                self.fticker.write(",".join(tickers_pred))
                self.ptLocal(self.fout, "Possible ticker number: %s", len(tickers_pred))
                self.ptLocal(self.fout, "Random pick successful rate: %.3f\n",\
                 round(float(sum(self.expected)) / len(self.expected), 3))

    def neuralNet(self):
        self.ptLocal(self.fout, "\nDeep Neural Network%s", "")
        layer = [168, 32, 2]
        self.clf = MLPClassifier(solver='lbfgs', alpha=1e-5, early_stopping=True, \
            hidden_layer_sizes=layer, random_state=0, momentum=0.5, \
            max_iter=10 ** 5)
        self.perform()

    def randomForest(self):
        self.ptLocal(self.fout, "\nRandom Forest%s", "")
        self.clf = RandomForestClassifier(random_state=0)
        self.perform()

    def boosting(self):
        self.ptLocal(self.fout, "\nGradient Boosting%s", "")
        self.clf = GradientBoostingClassifier(n_estimators=1000, random_state=0)
        self.perform()

    # keras.io/getting-started/sequential-model-guide/
    def RNN(self):
        featureNum = len(self.X[0]) / 6
        X = np.empty((len(self.X), 6, featureNum))
        X_test = np.empty((len(self.X_test), 6, featureNum))
        self.X = self.X.reshape(len(self.X), featureNum, 6)
        self.X_test = self.X_test.reshape(len(self.X_test), featureNum, 6)
        for i in range(len(self.X)):
            X[i] = self.X[i].transpose()
        for i in range(len(self.X_test)):
            X_test[i] = self.X_test[i].transpose()

        np.random.seed(0)
        model = Sequential()
        model.add(SimpleRNN(20, batch_input_shape=(None, 6, 28)))
        model.add(Dropout(0.1))
        model.add(Dense(1, activation='sigmoid'))
        model.compile(loss='binary_crossentropy', optimizer='adam', metrics=['accuracy'])
        print(model.summary())
        model.fit(X, self.y, verbose=2)
        predicted = model.predict_classes(X_test, verbose=0)
        # Final evaluation of the model
        scores = model.evaluate(X_test, self.expected, verbose=0)
        print("Accuracy: %.2f%%" % (scores[1]*100))
        self.ptLocal(self.fout, "Classification report for classifier:\n%s", \
            (metrics.classification_report(self.expected, predicted)))
        self.ptLocal(self.fout, "Confusion matrix:\n%s", \
            metrics.confusion_matrix(self.expected, predicted))
        self.ptLocal(self.fout, "Random pick successful rate: %.3f\n",\
            round(float(sum(self.expected)) / len(self.expected), 3))

    def tensorflowRNN(self):
        # Parameters
        learning_rate = 0.001
        training_iters = 10000
        batch_size = 1280
        display_step = 10

        # Network Parameters
        n_input = 28 # MNIST data input (img shape: 28*28)
        n_steps = 6 # timesteps
        n_hidden = 100 # hidden layer num of features
        n_classes = 2 # MNIST total classes (0-9 digits)

        # tf Graph input
        x = tf.placeholder("float", [None, n_steps, n_input])
        y = tf.placeholder("float", [None, n_classes])

        # Define weights
        weights = {
            'out': tf.Variable(tf.random_normal([n_hidden, n_classes]))
        }
        biases = {
            'out': tf.Variable(tf.random_normal([n_classes]))
        }




            

    def perform(self):
        self.clf.fit(self.X, self.y)
        scores = cross_val_score(self.clf, self.X, self.y).mean()
        self.ptLocal(self.fout, "Cross Validation Score: %.3f", scores)
        predicted = self.clf.predict(self.X_test)
        self.ptLocal(self.fout, "Classification report for classifier %s:\n%s", \
            (self.clf, metrics.classification_report(self.expected, predicted)))
        self.ptLocal(self.fout, "Confusion matrix:\n%s", \
            metrics.confusion_matrix(self.expected, predicted))
        
if __name__ == "__main__":
    date_start = "2000-01-01"
    date_end = "2016-12-31"
    date_type = "d" # daily data
    sortino_rate = .5 # set classification threshold
    testYear = 2016
    s = learning(date_start, date_end, date_type, sortino_rate, testYear)
    s.boosting()
