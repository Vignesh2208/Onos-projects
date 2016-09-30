import os
import warnings
import sys
from readData import *
from scipy.fftpack import fft
from scipy.signal import blackman
import matplotlib.pyplot as plt
import numpy as np
from operator import itemgetter 
from sklearn import mixture
from operator import truediv
from hmmlearn import hmm
from statistics import mean
from statistics import stdev
import math


argList = sys.argv
#if len(argList) > 1 :
#	signal_no = int(argList[1])
#else:
#	signal_no = 0

#print "Signal no = ", signal_no

def extractAverageSamplingPeriod(trainSamples):
	N = len(trainSamples)
	i = 1
	T = 0.0
	nFields = len(trainSamples[0])
	while i < N :
		T = T + float(trainSamples[i][nFields-1]) - float(trainSamples[i-1][nFields-1])
		i = i + 1

	T = T/float(N*1000)
	return T

def getStateSimilarityMatrix(observations,nStages,nMixtures) :

	Sim = []
	j = 0
	while j < 2*nStages :
		currStateSim = []
		i = 0
		while i < 2*nStages :
			if j < nStages:
				srcStateGMM = observations[j]['gmms'][nMixtures - 1]
				if i < nStages :
					dstStateSamples = observations[i]['samples']
				elif len(observations[i % nStages]['anomalousSamples']) > 0 :
					dstStateSamples = observations[i % nStages]['anomalousSamples']
				if dstStateSamples != None :
					currStateSim.append(srcStateGMM.bic(np.array(dstStateSamples)))
					dstStateSamples = None
			elif len(observations[j % nStages]['anomalousSamples']) > 0 :
				srcStateGMM = observations[j % nStages]['agmms'][nMixtures - 1]
				if i < nStages :
					dstStateSamples = observations[i]['samples']
				elif len(observations[i % nStages]['anomalousSamples']) > 0 :
					dstStateSamples = observations[i % nStages]['anomalousSamples']
				if dstStateSamples != None :
					currStateSim.append(srcStateGMM.bic(np.array(dstStateSamples)))
					dstStateSamples = None
			i = i + 1

		Sim.append(currStateSim)
		j = j + 1
		
	print "BIC State Similarity Matrix (Lower values => more Similar) = "
	print np.array(Sim)
	return Sim
				
				

def getFFT(signal,T):
	#signal = np.array(map(itemgetter(signalNo), samples))
	N = len(signal)
	xf = np.linspace(0.0, 1.0/(2.0), N/2)
	w = blackman(N)
	ffts = []
	sfft = fft(np.array(signal)*w)
	#plt.semilogy(xf[1:N/2], 2.0/N * np.abs(sfft[1:N/2] + 1), '-r')
	#plt.grid(True)
	#plt.show()
	

	return xf,sfft
	
	

def plotSignal(signal,N=100):


	x = np.linspace(0,N,N)
	plt.plot(x,signal[0:N])
	plt.grid()
	plt.show()

def scoreSamples(samples,hmm,windowSize) :
	scores = []
	assert windowSize > 0
	N = windowSize
	nWindows = int(len(samples)/windowSize)
	nSamples = len(samples)
	#print "nWindows = ",nWindows, " nSamples = ", len(samples)
	i = 0
	while i + N < nSamples :
		scores.append(hmm.score(np.array(samples[i:i+N])))
		i = i  + 1
		
	scores.append(hmm.score(np.array(samples[i:])))
	#print "scores ", scores
	if len(scores) > 1 :
		return mean(scores),(1.96*stdev(scores))/float(math.sqrt(len(scores)))
	else :
		return mean(scores),0.0
	

def trainHMM(observations,trainSamples,nMixtures=1,nStages=1,cvType='diag') :
	j = 0
	nStates = nStages
	assert nStates > 0
	while j < nStages :
		if len(observations[j]['anomalousSamples']) > 0 :
			nStates = nStates + 1
		j = j + 1

	transmat = []
	#startProb = [float(1.0/nStates)]*nStates
	startProb = [0.0]*nStates
	startProb[0] = 1.0
	j = 0
	while j < nStates :
		transmat.append([0.0]*nStates)
		j = j + 1

	anomalyStateId = nStages
	nAnomalyStates = nStates - nStages
	#print "nAnomalyStates in HMM = ",nAnomalyStates
	j = 0
	while j < nStages :
		
		if nStates == nStages :
			transmat[j][j] = 1
		else:
			currStage = j % nStages
			nextStage = (j+1) % nStages
			prevStage = (j-1) % nStages
			if len(observations[currStage]['anomalousSamples']) > 0 :
				transmat[prevStage][currStage] = 0.5
				transmat[prevStage][anomalyStateId] = 0.5
				if len(observations[prevStage]['anomalousSamples']) > 0 :
					transmat[(anomalyStateId -1 -nStages)% nAnomalyStates + nStages][anomalyStateId] = 0.5
					transmat[(anomalyStateId -1 -nStages)% nAnomalyStates + nStages][currStage] = 0.5
				anomalyStateId = anomalyStateId + 1
			else:
				transmat[prevStage][currStage] = 1
				if len(observations[prevStage]['anomalousSamples']) > 0 :
					transmat[(anomalyStateId -1 -nStages)% nAnomalyStates + nStages][currStage] = 1

		j = j + 1

	transmat = np.array(transmat)
	#print "Transition Probability Matrix = "
	#print transmat
	means = []
	covars = []
	weights = []
	j = 0
	while j < 2*nStages :
		if j < nStages :
			gmm = observations[j]['gmms'][nMixtures - 1]
		elif len(observations[j % nStages]['anomalousSamples']) > 0 : 
			gmm = observations[j % nStages]['agmms'][nMixtures - 1]
		
		if gmm != None :		
			means.append(gmm.means_)
			covars.append(gmm.covars_)
			weights.append(gmm.weights_)
			gmm = None

		j = j + 1
		

	means = np.array(means)
	covars = np.array(covars)
	weights = np.array(weights)

	#print "covars = ",covars

	if nStates >= nStages :
		#gmmHMM = hmm.GMMHMM(n_components=nStates,n_mix=nMixtures,covariance_type=cvType,params='stmcw', init_params='stmcw',n_iter=10,tol=0.001,verbose=1)
		gmmHMM = hmm.GaussianHMM(n_components=nStates,n_iter=1000,tol=0.0001,params='stmcw')
		gmmHMM.means_ = means
		gmmHMM.covars_ = covars 
		gmmHMM.weights_ = weights
		gmmHMM.startprob_ = np.array(startProb)
		gmmHMM.transmat_  = np.array(transmat)
		
		gmmHMM.fit(np.array(trainSamples))
		
		print "GMMHMM Score = ", gmmHMM.score(np.array(trainSamples))
		#print "GMMHMM TransMatrix = "
		#print gmmHMM.transmat_
		
		#print "GMMHMM StartProb = "
		#print gmmHMM.startprob_

	return gmmHMM
	


def trainGMMs(trainSamples,sysPeriod=1,nMaxMixtures=10,filterThreshold=0,cvType='diag') :
	assert len(trainSamples) > 0
	nFeatures = len(trainSamples[0])
	nSamples = len(trainSamples)
	nStages = sysPeriod
	observations = {}
	featureMax = []
	i = 0
	while i < nStages :
		observations[i] = {}
		observations[i]['samples'] = []
		observations[i]['anomalousSamples'] = []
		observations[i]['gmms'] = []
		observations[i]['agmms'] = []
		observations[i]['bic'] = []
		i = i + 1
	
	i = 0	
	while i < nFeatures :
		maxVal = max(np.array(map(itemgetter(i), trainSamples))) # need to alter if signal can have negative values
		if maxVal == 0:
			maxVal = 1
		featureMax.append(maxVal)
		i = i + 1
		

	i = 0
	while i < nSamples :
		currStage = i % nStages
		observations[currStage]['samples'].append(map(truediv,trainSamples[i],featureMax))
		i = i + 1



	i = 1
	min_BIC_List = []
	while i <= nMaxMixtures :
		min_BIC = np.infty
		j =  0
		while j < nStages :
			

			g = mixture.GMM(n_components=i,covariance_type=cvType,n_iter=100000)
			g.fit(np.array(observations[j]['samples']))
			bic = float(g.bic(np.array(observations[j]['samples'])))
			observations[j]['bic'].append(bic)
			observations[j]['gmms'].append(g)
			
			if bic < min_BIC :
				min_BIC = bic
			j = j + 1
		
		min_BIC_List.append(min_BIC)
		i = i + 1
	
	#print "Min BICs For Samples w.r.t nComponents = ", min_BIC_List
	nS1Mixtures = min_BIC_List.index(min(min_BIC_List)) + 1
	#print "Stage1 Optimum number of Mixtures = ", nS1Mixtures
	assert nS1Mixtures <= nMaxMixtures
	#if  nStages > 1 :
	if  False :
		i = 0
		while i < nStages :
			j = 0
			while j < nSamples :
				if j % nStages != i :
					currStage = j % nStages 
					gmm = observations[currStage]['gmms'][nS1Mixtures - 1]
					assert gmm != None
					if gmm.score([trainSamples[j]]) < filterThreshold :
						observations[i]['anomalousSamples'].append(trainSamples[j])
				j = j + 1
			i = i + 1
		
		i = 1
		min_BIC_List = []
		while i <= nMaxMixtures :
			min_BIC = np.infty
			j =  0
			while j < nStages :
			
				if len(observations[j]['anomalousSamples']) > 0 :
					g = mixture.GMM(n_components=i,covariance_type=cvType,n_iter=100000)
					g.fit(np.array(observations[j]['anomalousSamples']))
					bic = float(g.bic(np.array(observations[j]['anomalousSamples'])))
					observations[j]['bic'].append(bic)
					observations[j]['agmms'].append(g)
					if bic < min_BIC :
						min_BIC = bic
				j = j + 1
		
			min_BIC_List.append(min_BIC)
			i = i + 1	

		#print "Min BICs For Anomalous Samples w.r.t nComponents = ", min_BIC_List
		nS2Mixtures = min_BIC_List.index(min(min_BIC_List)) + 1
		#print "Stage2 Optimum number of Mixtures = ", nS2Mixtures
		assert nS2Mixtures <= nMaxMixtures
		if nStages > 1 :
			StateSimilarity = getStateSimilarityMatrix(observations,nStages,nS1Mixtures)

	return observations, nS1Mixtures
		
def plotInterestingFFTs(trainCharacteristics) :
	plt.close('all')

	plt.subplots_adjust(hspace=0.7)

	N= len(trainCharacteristics['FunctionCode'][3])
	xf,fCode3 = getFFT(trainCharacteristics['FunctionCode'][3],1000)
	xf,fCode16 = getFFT(trainCharacteristics['FunctionCode'][16],1000)
	xf,networkBytes = getFFT(trainCharacteristics['Network']['Bytes'],1000)
	xf,setpoint = getFFT(trainCharacteristics['Registers'][16]['w'],1000)	
	xf,pipelinePSI = getFFT(trainCharacteristics['Registers'][14]['r'],1000)	

	
	f,axarr = plt.subplots(3,2)
	#plt.semilogy(xf,fCode3)
	axarr[0,0].semilogy(xf[1:N/2], 2.0/N * np.abs(fCode3[1:N/2] + 1), '-r')
	axarr[0,0].set_title("FFT - Function Code 3 Access")
	axarr[0,0].grid(True)

	
	#plt.semilogy(xf,fCode16)
	axarr[0,1].semilogy(xf[1:N/2], 2.0/N * np.abs(fCode16[1:N/2] + 1), '-r')
	axarr[0,1].set_title("FFT - Function Code 16 Access")
	axarr[0,1].grid(True)

	
	#plt.semilogy(xf,setpoint)
	axarr[1,0].semilogy(xf[1:N/2], 2.0/N * np.abs(setpoint[1:N/2] + 1), '-r')
	axarr[1,0].set_title("FFT - Setpoint Reg Write")
	axarr[1,0].grid(True)


	#plt.semilogy(xf,pipelinePSI)
	axarr[1,1].semilogy(xf[1:N/2], 2.0/N * np.abs(pipelinePSI[1:N/2] + 1), '-r')
	axarr[1,1].set_title("FFT - Pressure Reg Read")
	axarr[1,1].grid(True)

	
	#plt.semilogy(xf,networkBytes)
	axarr[2,0].semilogy(xf[1:N/2], 2.0/N * np.abs(networkBytes[1:N/2] + 1), '-r')
	axarr[2,0].set_title("FFT - Network Bytes")
	axarr[2,0].grid(True)

	axarr[2,1].axis('off')

	plt.tight_layout()
	plt.show()
	

	

if __name__ == "__main__" :



	np.random.seed(123456)

	sysPeriod = 1
	nMaxPeriods = 10
	maxMixtures = 1
	covType = 'full'
	probThreshold = 80


	trainCommandFile = '/home/vignesh/Downloads/ModbusRTUfeatureSetsV2/Command_Injection/AddressScanScrubbedV2.csv'
	trainResponseFile = '/home/vignesh/Downloads/ModbusRTUfeatureSetsV2/Response_Injection/ScrubbedBurstV2/scrubbedBurstV2.csv'
	dosAttackDataFile = '/home/vignesh/Downloads/ModbusRTUfeatureSetsV2/DoS_Data_FeatureSet/modbusRTU_DoSResponseInjectionV2.csv'
	functionScanDataFile = '/home/vignesh/Downloads/ModbusRTUfeatureSetsV2/Command_Injection/FunctionCodeScanScrubbedV2.csv'
	burstResponseFile = '/home/vignesh/Downloads/ModbusRTUfeatureSetsV2/Response_Injection/ScrubbedBurstV2/scrubbedBurstV2.csv'
	fastburstResponseFile = '/home/vignesh/Downloads/ModbusRTUfeatureSetsV2/Response_Injection/ScrubbedFastV2/scrubbedFastV2.csv'
	slowburstResponseFile = '/home/vignesh/Downloads/ModbusRTUfeatureSetsV2/Response_Injection/ScrubbedSlowV2/scrubbedSlowV2.csv'
	
	assert os.path.isfile(trainCommandFile)
	assert os.path.isfile(trainResponseFile)
	assert os.path.isfile(dosAttackDataFile)
	assert os.path.isfile(functionScanDataFile)
	assert os.path.isfile(burstResponseFile)
	assert os.path.isfile(fastburstResponseFile)
	assert os.path.isfile(slowburstResponseFile)
	
	#trainSamples = readTrainSamplesSystemData(commandFile,responseFile)
	print "Reading Train and Test Samples ..."
	traincharacteristics,timeSeries = readTrainSamplesNetworkData(trainCommandFile,trainResponseFile,1,1000,28071)

	#plotInterestingFFTs(traincharacteristics)
	#sys.exit(0)

	print "Reading DoS Data ..."	
	characteristics,dosAttackData = readTestSamplesNetworkData(dosAttackDataFile,28072,1000)
	print "Reading Function Code Scan Data ..."
	characteristics,functionScanData = readTestSamplesNetworkData(functionScanDataFile,28088,1000)
	#print functionScanData
	print "Reading burst response .."
	characteristics,burstResponseData = readTestSamplesNetworkData(burstResponseFile,28072,1000)
	print "Reading fast burst ..."
	characteristics,fastburstResponseData = readTestSamplesNetworkData(fastburstResponseFile,28072,1000)
	print "Reading slow burst ..."
	characteristics,slowburstResponseData = readTestSamplesNetworkData(slowburstResponseFile,28072,1000)

	trainMeans = []
	trainErrs = []
	doSMeans = []
	doSErrs = []
	fScanMeans = []
	fScanErrs = []
	bRMeans = []
	bRErrs = []
	fbRMeans = []
	fbRErrs = []
	sbRMeans = []
	sbRErrs = []

	
	start = 1
	period = []
	while start < nMaxPeriods + 1 :
		sysPeriod = start
		period.append(sysPeriod)
		print "Training HMM for SysPeriod = ",sysPeriod
		observations, nS1Mixtures = trainGMMs(timeSeries,sysPeriod=sysPeriod,nMaxMixtures=maxMixtures,filterThreshold=probThreshold,cvType=covType)
		Hmm = trainHMM(observations=observations,trainSamples=timeSeries,nMixtures=nS1Mixtures,nStages=sysPeriod,cvType=covType)

		print "Scoring Samples ..."
	
		windowSize = 60
		mu,err = scoreSamples(timeSeries,Hmm,windowSize)
		trainMeans.append(mu)
		trainErrs.append(err)
		mu,err = scoreSamples(dosAttackData,Hmm,windowSize)
		doSMeans.append(mu)
		doSErrs.append(err)
		mu,err = scoreSamples(functionScanData,Hmm,windowSize)
		fScanMeans.append(mu)
		fScanErrs.append(err)
		mu,err = scoreSamples(burstResponseData,Hmm,windowSize)
		bRMeans.append(mu)
		bRErrs.append(err)
		mu,err = scoreSamples(fastburstResponseData,Hmm,windowSize)
		fbRMeans.append(mu)
		fbRErrs.append(err)
		mu,err = scoreSamples(slowburstResponseData,Hmm,windowSize)
		sbRMeans.append(mu)
		sbRErrs.append(err)

		start =  start + 1
		
	

	trainLine = plt.errorbar(period,trainMeans,yerr=trainErrs,label="Train Samples",linestyle='--',marker="d",color="red")
	doSLine = plt.errorbar(period,doSMeans,yerr=doSErrs,label="DoS Attack",linestyle='-',marker="+",color="black")
	fScanLine = plt.errorbar(period,fScanMeans,yerr=fScanErrs,label="Function Scan",linestyle='-.',marker="^",color="green")
	bRLine = plt.errorbar(period,bRMeans,yerr=bRErrs,label="Burst Response",linestyle='-',marker="x", color="blue")
	fbRLine = plt.errorbar(period,fbRMeans,yerr=fbRErrs,label="Fast Burst",linestyle='--',marker='*',color="m")
	sbRLine = plt.errorbar(period,sbRMeans,yerr=sbRErrs,label="Slow Burst",linestyle='-',marker='o',color="green")
	plt.title("Log Likelihood Variation for Window Size = 60 sec")
	plt.xlabel("Number of States")
	plt.ylabel("HMM average log likelihood")
	plt.xticks(np.arange(min(period), 15 , 1.0))
	plt.yscale('symlog')
	plt.legend(loc='upper right',shadow=True)
	plt.grid(True)
	plt.show()
	

	#plotSignal(sNetwork)
	#plotFFT(sNetwork,1000)
