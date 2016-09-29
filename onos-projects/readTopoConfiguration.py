import os
import sys


def throwERROR(msg) :
	print "Topo Config Parser ERROR: ", msg
	sys.exit(-1)


def checkLabelFormat(nodeId,line_no):
	if not nodeId.startswith('s') and not nodeId.startswith('h'):
		throwERROR("Incorrect label at line no : " + str(line_no))
	elif not nodeId.startswith('s') :
		splitList = nodeId.split("_")
		assert len(splitList) == 2
		if not int(splitList[0][1:]) >= 1 or not int(splitList[1]) >= 1 :
			throwERROR("Incorrect label at line no : " + str(line_no))
	elif not int(nodeId[1:]) >= 1 :
		throwERROR("Incorrect label at line no : " + str(line_no))


def isHost(label):
	if label.startswith('h'):
		return True
	return False


def getOnosSwitchId(label):
	switchId = str(label[1:])
	while len(switchId) < 16:
		switchId = "0" + switchId
	
	return switchId

def getSwitchName(onosSwitchId):
	return "s" + str(int(onosSwitchId))

def getHostId(label):
	splitList = label.split("_")
	assert len(splitList) == 2
	return splitList[0]

def getInterface(label):
	splitList = label.split("_")
	assert len(splitList) == 2
	return int(splitList[1])

def getInterfaceMAC(hostId,intfId):
	mac = str(hex(hostId)[2:]) + ":00:00:00:00:" +str(hex(intfId)[2:])
	return mac
	

def generateNetworkCfg(SwitchPortMapping):
	with open('network-cfg.json',"w") as f:
		f.write("{\n")
		f.write("	\"ports\": {\n")
		switchList = sorted(list(SwitchPortMapping.keys()))
		j = 0
		for onosSwitchId in switchList:
			i = 1
			nPorts = SwitchPortMapping[onosSwitchId]['nPorts']
			while i <= nPorts:
				f.write("		\"of:" + str(onosSwitchId) + "/" + str(i) + "\" :	{\n")
				f.write("			\"interfaces\"	:	[\n")
				k = 0
				while k < len(SwitchPortMapping[onosSwitchId][i]) :
					f.write("				{\n")
					f.write("					\"name\":	\"" + str(SwitchPortMapping[onosSwitchId][i][k][0]) + "\",\n")
					f.write("					\"vlan\":	\"" + str(SwitchPortMapping[onosSwitchId][i][k][1]) + "\"\n")

					if k < len(SwitchPortMapping[onosSwitchId][i]) - 1 :
						f.write("				},\n")
					else:
						f.write("				}\n")
					k = k + 1


				f.write("			]\n")
				if j == len(switchList) - 1 and i == nPorts:
					f.write("		}\n")
				else:
					f.write("		},\n")
				i = i + 1
			j = j + 1

		f.write("	}\n}\n")
	

def parseTopoConfigFile(configFileName):

	lines = [line.rstrip('\n') for line in open(configFileName)]

	line_no = 0
	Nodes = {}
	
	SwitchPortVlanMapping = {}
	SwitchConnections = []
	for line in lines:
		line_no = line_no + 1
		if not line.startswith('#') :
			fieldsList = line.split(',')
			if len(fieldsList) != 2 and len(fieldsList) != 3:
				pass
			else:
				srcId = fieldsList[0]
				dstId = fieldsList[1]
				checkLabelFormat(srcId,line_no)
				checkLabelFormat(dstId,line_no)

				if srcId.startswith('s') and dstId.startswith('s') :
					SwitchConnections.append((srcId,dstId))
				elif srcId.startswith('h') and dstId.startswith('h') :
					throwERROR("Hosts cannot be directly connected together. Line no : " + str(line_no))
				else:
					try:
						vlanId = int(fieldsList[2])
					except:
						throwERROR("Unable to parse vlanId at line: " + str(line_no))
					
				

			
					if isHost(srcId) :
						intf = getInterface(srcId)
						srcId = getHostId(srcId)				
						if srcId not in Nodes.keys():
							Nodes[srcId] = {}
							Nodes[srcId]['vlan'] = {}
							Nodes[srcId]['nIntfs'] = 0
	
					elif srcId not in SwitchPortVlanMapping.keys():
						SwitchPortVlanMapping[getOnosSwitchId(srcId)] = {}
						SwitchPortVlanMapping[getOnosSwitchId(srcId)]['nPorts'] = 0
						

					if isHost(dstId) :
						intf = getInterface(srcId)
						dstId = getHostId(dstId)
						if dstId not in Nodes.keys():
							Nodes[dstId] = {}
							Nodes[dstId]['vlan'] = {}
							Nodes[dstId]['nIntfs'] = 0

					elif dstId not in SwitchPortVlanMapping.keys():
						SwitchPortVlanMapping[getOnosSwitchId(dstId)] = {}
						SwitchPortVlanMapping[getOnosSwitchId(dstId)]['nPorts'] = 0
						
					if isHost(srcId) :
						Nodes[srcId]['nIntfs'] = Nodes[srcId]['nIntfs'] + 1
						Nodes[srcId]['vlan'][intf] = vlanId
						Nodes[srcId]['switch'] = dstId

					if isHost(dstId) :
						Nodes[dstId]['nIntfs'] = Nodes[dstId]['nIntfs'] + 1
						Nodes[dstId]['vlan'][intf] = vlanId
						Nodes[dstId]['switch'] = srcId

	
	nodeList = sorted(Nodes.keys())
	for node in nodeList:
		nIntfs = Nodes[node]['nIntfs']
		assert nIntfs > 0
		assert isHost(Nodes[node]['switch']) == False

		connectedSwitch = getOnosSwitchId(Nodes[node]['switch'])
		portNo = SwitchPortVlanMapping[connectedSwitch]['nPorts'] + 1
		SwitchPortVlanMapping[connectedSwitch][portNo] = []
		SwitchPortVlanMapping[connectedSwitch]['nPorts'] = SwitchPortVlanMapping[connectedSwitch]['nPorts'] + 1

		i = 1
		while i <= nIntfs:
			if i not in Nodes[node]['vlan'].keys():
				throwERROR("Missing Interface " + str(i) + " for host " + str(node))
			
			vlanId = Nodes[node]['vlan'][i]
			intfName = node + "-eth0." + str(vlanId)
			SwitchPortVlanMapping[connectedSwitch][portNo].append((intfName,vlanId))
			i = i + 1



	return (Nodes,SwitchPortVlanMapping,SwitchConnections)


if __name__ == '__main__':
	Nodes,SwitchPortVlanMapping,SwitchConnections = parseTopoConfigFile('topology-configuration.txt')
	print "##########Nodes#########"
	print Nodes
	print "\n\n"
	print "###SwitchPortVlanMapping###"
	print SwitchPortVlanMapping
	print "\n\n"
	print "####SwitchConnections####"
	print SwitchConnections

	generateNetworkCfg(SwitchPortVlanMapping)

