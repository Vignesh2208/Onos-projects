import sys
import os
import numpy as np

address = 0
commandResponse = 1
controlMode = 2
controlScheme = 3
crc = 4
dataLen = 5
functionCode = 6
invalidDataLength = 7
invalidFunctionCode = 8
pIDCycleTime = 9
pIDDeadband = 10 
pIDGain = 11 
pIDRate = 12
pIDReset = 13
pipelinePSI = 14
pumpState = 15
setPoint = 16
solenoidState = 17
timeInterval = 18
#nTrainSamples = 4

registeredWriteFields = [controlMode,controlScheme,pIDCycleTime,pIDDeadband,pIDGain,pIDRate,pIDReset,setPoint]
registeredReadFields = [pipelinePSI,pumpState,solenoidState]
#registeredWriteFields = [setPoint]
#registeredReadFields = [pipelinePSI]


def transformFieldValues(fieldValues,registeredFields) :
	transformedValues = []
	fieldToIdxMapping = {}
	for idx in registeredFields:
		if idx == controlMode:
			sysStateIdx = len(transformedValues)
			if "X" in fieldValues[idx] or "Off" in fieldValues[idx]:
				transformedValues.append(0)
			else:
				transformedValues.append(1)
			fieldToIdxMapping[controlMode] = sysStateIdx

		elif idx == controlScheme:
			assert sysStateIdx != None
			if "Solenoid" in fieldValues[idx]:
				transformedValues[sysStateIdx] = 2*transformedValues[sysStateIdx]
			else:
				transformedValues[sysStateIdx] = 2*transformedValues[sysStateIdx] + 1
			fieldToIdxMapping[controlScheme] = sysStateIdx

		elif idx == pumpState:
			assert sysStateIdx != None
			if "X" in fieldValues[idx] or "Off" in fieldValues[idx]:
				transformedValues[sysStateIdx] = 2*transformedValues[sysStateIdx]
			else:
				transformedValues[sysStateIdx] = 2*transformedValues[sysStateIdx] + 1
			fieldToIdxMapping[pumpState] = sysStateIdx

		elif idx == solenoidState:
			assert sysStateIdx != None
			if "X" in fieldValues[idx] or "Off" in fieldValues[idx] :
				transformedValues[sysStateIdx]  = 2*transformedValues[sysStateIdx]
			else:
				transformedValues[sysStateIdx]  = 2*transformedValues[sysStateIdx] + 1
			fieldToIdxMapping[solenoidState] = sysStateIdx

		else:
			transformedValues.append(float(fieldValues[idx]))
			fieldToIdxMapping[idx] = len(transformedValues) - 1
	#print "sysState = ", transformedValues[sysStateIdx], " Idx = ", sysStateIdx
	
	return np.array(transformedValues),fieldToIdxMapping

	
	
	


def readTrainSamplesSystemData(commandFile,responseFile):
	with open(commandFile,'r') as f:
		trainCommands = f.readlines()

	with open(responseFile,'r') as f:
		trainResponses = f.readlines()

	assert len(trainCommands) >= nTrainSamples
	assert len(trainResponses) >= nTrainSamples

	registeredWriteFields.append(timeInterval)
	registeredReadFields.append(timeInterval)
	registeredFields = list(registeredWriteFields)
	registeredFields.extend(list(registeredReadFields))
	registeredFields = sorted(list(set(registeredFields)))

	currCmdTime = 0
	currRespTime = 0
	

	line_no = 1
	trainSamples = []
	n_anomalies = 0
	while line_no <= nTrainSamples:
		cmdfieldValues = trainCommands[line_no].split(',')
		respfieldValues = trainResponses[line_no].split(',')
		if float(cmdfieldValues[timeInterval]) > 100000:
			cmdfieldValues[timeInterval] = 500
			n_anomalies = n_anomalies + 1
		if float(respfieldValues[timeInterval]) > 100000:
			respfieldValues[timeInterval] = 500
			n_anomalies = n_anomalies + 1
			

		currCmdTime = currCmdTime + float(cmdfieldValues[timeInterval])
		currRespTime = currRespTime + float(respfieldValues[timeInterval])
		
		if "0x10" in cmdfieldValues[functionCode]:
			#print "Cmd tranformed vals = ",fieldValues
			
			cmdfieldValues[timeInterval] = currCmdTime
			transformedValues,fieldToIdxMapping = transformFieldValues(cmdfieldValues,registeredFields)
			trainSamples.append(transformedValues)
			currIdx = len(trainSamples) - 1

			if line_no > 1 :
				prevPumpSolenoidState = int(trainSamples[currIdx - 1][fieldToIdxMapping[pumpState]]) % 4
				currControlState = int(trainSamples[currIdx][fieldToIdxMapping[controlScheme]]/4)
				trainSamples[currIdx][fieldToIdxMapping[controlScheme]] = 4*currControlState + prevPumpSolenoidState

			for fieldIdx in registeredReadFields:
				if fieldIdx not in registeredWriteFields and line_no > 1 and fieldIdx not in [controlScheme,controlMode,pumpState,solenoidState]:
					trainSamples[currIdx][fieldToIdxMapping[fieldIdx]] = trainSamples[currIdx-1][fieldToIdxMapping[fieldIdx]]
		
		
		#print "Resp transformed vals = ", fieldValues
		if "0x3" in respfieldValues[functionCode]:
			
			respfieldValues[timeInterval] = currRespTime
			transformedValues,fieldToIdxMapping = transformFieldValues(respfieldValues,registeredFields)
			trainSamples.append(transformedValues)
			currIdx = len(trainSamples) - 1

			if line_no > 1 :
				prevControlState = int(trainSamples[currIdx - 1][fieldToIdxMapping[controlScheme]]/4)
				currPumpSolenoidState = int(trainSamples[currIdx][fieldToIdxMapping[controlScheme]]) % 4
				trainSamples[currIdx][fieldToIdxMapping[controlScheme]] = 4*prevControlState + currPumpSolenoidState
	
			for fieldIdx in registeredWriteFields:
				if fieldIdx not in registeredReadFields and line_no > 1 and fieldIdx not in [controlScheme,controlMode,pumpState,solenoidState]:
					trainSamples[currIdx][fieldToIdxMapping[fieldIdx]] = trainSamples[currIdx-1][fieldToIdxMapping[fieldIdx]]



		trainCommands[line_no] = []
		trainResponses[line_no] = []
		line_no = line_no + 1
	
	print "n_anomalies = ", n_anomalies
	nFields = len(trainSamples[0])
	trainSamples = sorted(trainSamples,key=lambda x: x[nFields-1])
	return trainSamples


def readTrainSamplesNetworkData(commandFile,responseFile,startLine=1,samplingPeriod=1000,nSamples=-1) :

	invalidFCode = 17
	with open(commandFile,'r') as f:
		trainCommands = f.readlines()

	with open(responseFile,'r') as f:
		trainResponses = f.readlines()

	

	if nSamples == -1 :
		nSamples = len(trainCommands) -1

	registeredWriteFields.append(timeInterval)
	registeredReadFields.append(timeInterval)
	registeredFields = list(registeredWriteFields)
	registeredFields.extend(list(registeredReadFields))
	registeredFields = sorted(list(set(registeredFields)))


	line_no = startLine
	currCmdTime = 0
	currRespTime = 0
	n_anomalies = 0
	samplingPeriod = samplingPeriod # 1sec

	while line_no <= nSamples :

		cmdfieldValues = trainCommands[line_no].split(',')
		respfieldValues = trainResponses[line_no].split(',')
		if float(cmdfieldValues[timeInterval]) > 100000:
			cmdfieldValues[timeInterval] = 500
			n_anomalies = n_anomalies + 1
		if float(respfieldValues[timeInterval]) > 100000:
			respfieldValues[timeInterval] = 500
			n_anomalies = n_anomalies + 1
			

		currCmdTime = currCmdTime + float(cmdfieldValues[timeInterval])
		currRespTime = currRespTime + float(respfieldValues[timeInterval])
		line_no = line_no + 1


	totalTrainTime = max(currRespTime,currCmdTime)

	Characteristics = {}
	Characteristics['FunctionCode'] = {}
	Characteristics['Registers'] = {}
	Characteristics['Network'] = {}
	Characteristics['Network']['Bytes'] = [0]*(int(totalTrainTime/samplingPeriod) + 1)

	for fCode in range(0,18) :
		Characteristics['FunctionCode'][fCode] = [0]*(int(totalTrainTime/samplingPeriod) + 1)
	
	for field in registeredFields:
		Characteristics['Registers'][field] = {}
		Characteristics['Registers'][field]['r'] = [0]*(int(totalTrainTime/samplingPeriod) + 1) 
		Characteristics['Registers'][field]['w'] = [0]*(int(totalTrainTime/samplingPeriod) + 1) 
	
	line_no = startLine
	currCmdTime = 0
	currRespTime = 0
	n_anomalies = 0


	while line_no <= nSamples :

		cmdfieldValues = trainCommands[line_no].split(',')
		respfieldValues = trainResponses[line_no].split(',')
		if float(cmdfieldValues[timeInterval]) > 100000:
			cmdfieldValues[timeInterval] = 500
		if float(respfieldValues[timeInterval]) > 100000:
			respfieldValues[timeInterval] = 500
	
	
		currCmdTime = currCmdTime + float(cmdfieldValues[timeInterval])
		currRespTime = currRespTime + float(respfieldValues[timeInterval])

		cmdIdx = int(currCmdTime/samplingPeriod)
		respIdx = int(currRespTime/samplingPeriod)

		assert cmdIdx < int(totalTrainTime/samplingPeriod) + 1
		assert respIdx < int(totalTrainTime/samplingPeriod) + 1

		#print line_no,int(cmdfieldValues[functionCode],16)


		if int(cmdfieldValues[functionCode],16) <= 16 :
			Characteristics['FunctionCode'][int(cmdfieldValues[functionCode],16)][cmdIdx] = Characteristics['FunctionCode'][int(cmdfieldValues[functionCode],16)][cmdIdx] + 1
		else :
			Characteristics['FunctionCode'][invalidFCode][cmdIdx] = Characteristics['FunctionCode'][invalidFCode][cmdIdx] + 1

		if int(respfieldValues[functionCode],16) <= 16 :
			Characteristics['FunctionCode'][int(respfieldValues[functionCode],16)][respIdx] = Characteristics['FunctionCode'][int(respfieldValues[functionCode],16)][respIdx] + 1
		else :
			Characteristics['FunctionCode'][invalidFCode][respIdx] = Characteristics['FunctionCode'][invalidFCode][respIdx] + 1

		Characteristics['Network']['Bytes'][cmdIdx] = Characteristics['Network']['Bytes'][cmdIdx] + int(cmdfieldValues[dataLen])
		Characteristics['Network']['Bytes'][respIdx] = Characteristics['Network']['Bytes'][respIdx] + int(respfieldValues[dataLen])

		if int(cmdfieldValues[functionCode],16) in [5,6,15,16] :
			for field in registeredWriteFields :
				Characteristics['Registers'][field]['w'][cmdIdx] = Characteristics['Registers'][field]['w'][cmdIdx] + 1

		if int(respfieldValues[functionCode],16) in [1,2,3,4] :		
			for field in registeredReadFields :
				Characteristics['Registers'][field]['r'][respIdx] = Characteristics['Registers'][field]['r'][respIdx] + 1
		
		line_no = line_no + 1

	

	idx = 0
	networkCharacteristicTimeSeries = []
	nSamplePoints = int(totalTrainTime/samplingPeriod) + 1
	print "nSamples = ", nSamplePoints
	while idx <  nSamplePoints :
		currIdxValues = []
		for fCode in range(0,18) :
			currIdxValues.append(Characteristics['FunctionCode'][fCode][idx])
		for field in registeredFields:
			currIdxValues.append(Characteristics['Registers'][field]['r'][idx])
			currIdxValues.append(Characteristics['Registers'][field]['w'][idx])
		currIdxValues.append(Characteristics['Network']['Bytes'][idx])
		networkCharacteristicTimeSeries.append(currIdxValues)
		idx = idx + 1
		
		
		
		

	return Characteristics,networkCharacteristicTimeSeries


def readTestSamplesNetworkData(testFile,startLine=1,samplingPeriod=1000,nSamples=-1) :

	invalidFCode = 17
	with open(testFile,'r') as f:
		testSamples = f.readlines()
	if nSamples == -1 :
		nSamples = len(testSamples) -1

	registeredWriteFields.append(timeInterval)
	registeredReadFields.append(timeInterval)
	registeredFields = list(registeredWriteFields)
	registeredFields.extend(list(registeredReadFields))
	registeredFields = sorted(list(set(registeredFields)))


	line_no = startLine
	currTime = 0
	n_anomalies = 0
	samplingPeriod = samplingPeriod # 1sec

	while line_no <= nSamples :

		fieldValues = testSamples[line_no].split(',')
		#if float(fieldValues[timeInterval]) > 100000:
		#	fieldValues[timeInterval] = 500
		#	n_anomalies = n_anomalies + 1

		currTime = currTime + float(fieldValues[timeInterval])
		line_no = line_no + 1


	totalTestTime = currTime

	Characteristics = {}
	Characteristics['FunctionCode'] = {}
	Characteristics['Registers'] = {}
	Characteristics['Network'] = {}
	Characteristics['Network']['Bytes'] = [0]*(int(totalTestTime/samplingPeriod) + 1)

	for fCode in range(0,18) :
		Characteristics['FunctionCode'][fCode] = [0]*(int(totalTestTime/samplingPeriod) + 1)
	
	for field in registeredFields:
		Characteristics['Registers'][field] = {}
		Characteristics['Registers'][field]['r'] = [0]*(int(totalTestTime/samplingPeriod) + 1) 
		Characteristics['Registers'][field]['w'] = [0]*(int(totalTestTime/samplingPeriod) + 1) 
	
	line_no = startLine
	currTime = 0
	n_anomalies = 0


	while line_no <= nSamples :

		fieldValues = testSamples[line_no].split(',')
		#if float(fieldValues[timeInterval]) > 100000:
		#	fieldValues[timeInterval] = 500

	
	
		currTime = currTime + float(fieldValues[timeInterval])

		Idx = int(currTime/samplingPeriod)

		assert Idx < int(totalTestTime/samplingPeriod) + 1


		#print line_no,int(cmdfieldValues[functionCode],16)
		if int(fieldValues[functionCode],16) <= 16 :
			Characteristics['FunctionCode'][int(fieldValues[functionCode],16)][Idx] = Characteristics['FunctionCode'][int(fieldValues[functionCode],16)][Idx] + 1
		else :
			Characteristics['FunctionCode'][invalidFCode][Idx] = Characteristics['FunctionCode'][invalidFCode][Idx] + 1

		Characteristics['Network']['Bytes'][Idx] = Characteristics['Network']['Bytes'][Idx] + int(fieldValues[dataLen])


		if int(fieldValues[functionCode],16) in [5,6,15,16] :
			for field in registeredWriteFields :
				Characteristics['Registers'][field]['w'][Idx] = Characteristics['Registers'][field]['w'][Idx] + 1

		if int(fieldValues[functionCode],16) in [1,2,3,4] :		
			for field in registeredReadFields :
				Characteristics['Registers'][field]['r'][Idx] = Characteristics['Registers'][field]['r'][Idx] + 1
		
		line_no = line_no + 1

	

	idx = 0
	networkCharacteristicTimeSeries = []
	nSamplePoints = int(totalTestTime/samplingPeriod) + 1
	print "nSamples = ", nSamplePoints
	while idx <  nSamplePoints :
		currIdxValues = []
		for fCode in range(0,18) :
			currIdxValues.append(Characteristics['FunctionCode'][fCode][idx])
		for field in registeredFields:
			currIdxValues.append(Characteristics['Registers'][field]['r'][idx])
			currIdxValues.append(Characteristics['Registers'][field]['w'][idx])
		currIdxValues.append(Characteristics['Network']['Bytes'][idx])
		networkCharacteristicTimeSeries.append(currIdxValues)
		idx = idx + 1
		
		
		
		

	return Characteristics,networkCharacteristicTimeSeries
	



if __name__ == "__main__" :
	commandFile = '/home/vignesh/Downloads/ModbusRTUfeatureSetsV2/Command_Injection/AddressScanScrubbedV2.csv'
	responseFile = '/home/vignesh/Downloads/ModbusRTUfeatureSetsV2/Response_Injection/ScrubbedBurstV2/scrubbedBurstV2.csv'
	trainSamples = readTrainSamplesSystemData(commandFile,responseFile)
	characteristics,timeSeries = readTrainSamplesNetworkData(commandFile,responseFile,1,1000,28071)

	print "############ train samples obtained ############"
	for i in range(1,18000) :
		print timeSeries[i]
	

