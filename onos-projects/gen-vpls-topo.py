#!/usr/bin/env python

from mininet.topo import Topo
from mininet.cli import CLI
from mininet.node import Link, Host
from mininet.link import Intf, TCLink
from mininet.net import Mininet
from mininet.node import RemoteController, OVSKernelSwitch
from mininet.term import makeTerm

from functools import partial
import os
import readTopoConfiguration
from readTopoConfiguration import *
import httplib2
import json
import urllib


#controllerIP='72.36.82.150'
#controllerPort=40002
#networkCfgPort=40001

controllerIP='172.17.0.2'
controllerPort=6653
networkCfgPort=8181


nGrids = 1
nSwitchesPerGrid = 3 # >= 2
nHostsPerSwitch = 3
controlVlanId = 255
controlVlanTCPSource = 100
controlVlanTCPDest = 100

class VLANHost( Host ):

	

	def config( self, vlan=100, **params ):

		self.nVlanInterfaces = 0
		self.nodeId = 0
		self.vlanInterfaceNames = []
		r = super( VLANHost, self ).config( **params )
		
		return r

	

	def setNodeId(self,nodeId):
		self.nodeId = nodeId

	def addVlanInterface(self,vlanId):
		#targetIntfName = "h" + str(self.nodeId) + "-eth" + str(self.nVlanInterfaces)
		targetIntfName = "h" + str(self.nodeId) + "-eth0" 
		
		self.nVlanInterfaces = 1
		#self.nVlanInterfaces = self.nVlanInterfaces + 1
		self.configVlanInterface(targetIntfName,vlanId)
		

	def getInterfaceMAC(self,hostId,intfId):
		mac = "00:" + str(hex(hostId)[2:]) + ":00:00:00:" +str(hex(intfId)[2:])
		return mac	

	def configVlanInterface(self,targetIntfName,vlanId):
		
		intf = targetIntfName
		print "Target intf Name = ", targetIntfName
		self.cmd('ip link set ' + str(intf) + ' address ' + self.getInterfaceMAC(self.nodeId,self.nVlanInterfaces))
		self.cmd( 'ifconfig %s inet 0' % intf )
		
		vlanIntfName =   intf + "." + str(vlanId)
		vlanIntfIP = "10." + str(vlanId) + ".0" + "." + str(self.nodeId)

		# create VLAN interface
		self.cmd( 'vconfig add %s %d' % ( intf, vlanId ) )
		# configure new VLAN interface
		cmdToRun = "ifconfig " + vlanIntfName + " " + vlanIntfIP + " " + "netmask 255.255.0.0"
		#cmdToRun = 'ifconfig ' + vlanIntfName + ' inet ' + (intfIP + "/8")
		self.cmd(cmdToRun)
		self.vlanInterfaceNames.append(vlanIntfName)









		


def runTopology(topoConfigFile):

	net = Mininet(autoSetMacs=True)
	c1 = net.addController( 'c1', controller=RemoteController, ip=controllerIP, port=controllerPort)

	print "*** Reading Topology Config"
	Nodes,SwitchPortVlanMapping,SwitchConnections = parseTopoConfigFile(topoConfigFile)
	SwitchObjs = {}
	HostObjs = {}



	print "*** Adding Switches"

	switchList = sorted(list(SwitchPortVlanMapping.keys()))
	print "switchList = ", switchList
	for onosSwitchId in switchList:
		switchName = getSwitchName(onosSwitchId)
		switch = net.addSwitch(switchName)
		SwitchObjs[switchName] = switch
	
	switchList = sorted(list(SwitchObjs.keys()))
	nodeList = sorted(list(Nodes.keys()))

	print "*** Adding Hosts"

	for node in nodeList :
		host = net.addHost(node,cls=VLANHost)
		HostObjs[node] = net.getNodeByName(node)

	print "*** Adding Host-Switch Links"

	for node in nodeList:
		nIntfs = Nodes[node]['nIntfs']
		connectedSwitchName = Nodes[node]['switch']
		assert nIntfs > 0
		assert isHost(connectedSwitchName) == False
		assert connectedSwitchName in SwitchObjs.keys()
		i = 0

		while i < 1:
			intfName = node + "-eth" + str(i)
			l = net.addLink(HostObjs[node],SwitchObjs[connectedSwitchName],intfName1=intfName)
			i = i + 1

	print "*** Adding Switch-Switch Links"

	for connections in SwitchConnections:
		switch1Name = connections[0]
		switch2Name = connections[1]
		assert switch1Name in SwitchObjs.keys()
		assert switch2Name in SwitchObjs.keys()
		net.addLink(SwitchObjs[switch1Name],SwitchObjs[switch2Name])	

	# generate onos Network Cfg

	scriptDir = os.path.dirname(os.path.realpath(__file__))
	readTopoConfiguration.generateNetworkCfg(scriptDir + "/network-cfg.json",SwitchPortVlanMapping)
	os.system("curl --user karaf:karaf -X POST -H \"Content-Type: application/json\" http://" + str(controllerIP) + ":" + str(networkCfgPort) + "/onos/v1/network/configuration/ -d" + "@" + str(scriptDir) + "/network-cfg.json")
	print "*** Starting network" 
	net.build()

	for hostName in nodeList:
		hostId = int(hostName[1:])
		nIntfs = Nodes[hostName]['nIntfs']
		assert hostName in HostObjs.keys()
		assert nIntfs > 0
		hostObj = HostObjs[hostName]
		
		hostObj.setNodeId(hostId)
		i = 1
		while i <= nIntfs:
			intfName = hostName + "-eth" + str(i-1)
			vlanId = Nodes[hostName]['vlan'][i]
			hostObj.addVlanInterface(vlanId)
			i = i + 1

	c1.start()
	for switchName in switchList:
		switch = SwitchObjs[switchName]
		switch.start([c1])

	pingHosts(HostObjs)
	installControlVlanFlows()

	print "*** Running CLI"
	CLI( net )

 
	print "*** Stopping network"
	


	for switchName in switchList:
		switch = SwitchObjs[switchName]
		switch.stop()

	c1.stop()
	net.stop()



def installControlVlanFlows() :
	baseURL = "http://" + controllerIP + ":" + str(networkCfgPort) + "/onos/v1/"
	userName = "karaf"
	passwd = "karaf"
	requestHandler = httplib2.Http()
	requestHandler.add_credentials(userName,passwd)


	getFlowsUrl = baseURL + "flows"
	resp,content = requestHandler.request(getFlowsUrl,"GET")

	

	vplsFlows = json.loads(content)
	#print "vplsFlows = ",vplsFlows

	for flow in vplsFlows['flows'] :
		deleteFlowUrl = baseURL + "flows/" + urllib.quote(flow["deviceId"]) + "/" + flow["id"]
		
		#print "Flow = ", flow
		resp,content = requestHandler.request(deleteFlowUrl,"DELETE")
		flowCriteria = flow["selector"]["criteria"]
		for criteria in flowCriteria :
			if criteria["type"] == "VLAN_VID" :
				vlanId = criteria["vlanId"]
				if vlanId == controlVlanId :

					newTCPSrcCriteria = {}
					newTCPSrcCriteria["type"] = "TCP_SRC"
					newTCPSrcCriteria["tcpPort"] = controlVlanTCPSource
					flowCriteria.append(newTCPSrcCriteria)

					newTCPDestCriteria = {}
					newTCPDestCriteria["type"] = "TCP_DST"
					newTCPDestCriteria["tcpPort"] = controlVlanTCPDest
					flowCriteria.append(newTCPDestCriteria)
					
										
					break
	
					
	
	print "Updated Flows for controlVlan"
	updatedFlows = json.dumps(vplsFlows)
	updateFlowUrl = baseURL + "flows/"
	resp,content = requestHandler.request(updateFlowUrl,"POST",headers={'Content-type':'application/json; charset=UTF-8'},body=updatedFlows)
	

def pingAllHostPairs(HostObjs,hostIds,vlanId) :

	assert vlanId <= 256
	nHosts = len(hostIds)
	for i in xrange(0,nHosts) :
		for j in xrange(i+1,nHosts) :
			srcHostName = "h" + str(hostIds[i])
			dstHostName = "h" + str(hostIds[j])
			assert srcHostName in HostObjs.keys()
			assert dstHostName in HostObjs.keys()

			dstHostIp = "10." + str(vlanId) + ".0." + str(hostIds[j])
			srcHostInterface = srcHostName + "-eth0." + str(vlanId)
			srcHost = HostObjs[srcHostName]
			dstHost = HostObjs[dstHostName]
			pingCmd = "ping -c 1 -I " + srcHostInterface + " " + dstHostIp
			srcHost.cmd(pingCmd)

			

def pingHosts(HostObjs) :

	nSwitches = nSwitchesPerGrid*nGrids
	nHosts = nSwitches*nHostsPerSwitch
	nHostsPerGrid = nSwitchesPerGrid*nHostsPerSwitch
	
	controlSwitch = nSwitches + 1
	controlHost = nHosts + 1
	i = 1
	while  i <= nHosts + 1 - nHostsPerSwitch :
		enclaveHosts = range(i,i+nHostsPerSwitch,1)
		assert len(enclaveHosts) == nHostsPerSwitch
		
		switchId = int((i-1)/nHostsPerSwitch) + 1
		enclaveVlanId = switchId
		print "Pinging hosts in enclave: ", enclaveVlanId
		pingAllHostPairs(HostObjs,enclaveHosts,enclaveVlanId)
		i = i + nHostsPerSwitch

	controlVlanHosts = range(1,controlHost + 1, nHostsPerSwitch)
	assert len(controlVlanHosts) == nSwitches + 1
	print "pinging control vlan hosts .."
	pingAllHostPairs(HostObjs,controlVlanHosts,controlVlanId)
	
	
					
def genUGridTopoConfig(topoConfigFile):
	nSwitches = nSwitchesPerGrid*nGrids
	nHosts = nSwitches*nHostsPerSwitch
	nHostsPerGrid = nSwitchesPerGrid*nHostsPerSwitch

	controlSwitch = nSwitches + 1
	controlHost = nHosts + 1
	
	assert nHosts > 0
	assert nSwitches > 0

	with open(topoConfigFile,"w") as f :
		f.write("h" + str(controlHost) + "_1,s" + str(controlSwitch) + "," + str(controlVlanId) + "\n")
		for i in xrange(1,nHosts + 1) :
			switchId = int((i-1)/nHostsPerSwitch) + 1
			uGridId = int((i-1)/nHostsPerGrid) + 1
			enclaveVlanId = switchId
			if i % nHostsPerSwitch == 1 :
				f.write("h" + str(i) + "_1,s" + str(switchId) + "," + str(enclaveVlanId) + "\n")
				f.write("h" + str(i) + "_2,s" + str(switchId) + "," + str(controlVlanId)  + "\n")
				if switchId <= uGridId*nSwitchesPerGrid - 1 :
					f.write("s" + str(switchId) + ",s" + str(switchId + 1) + "\n")
				elif switchId == uGridId*nSwitchesPerGrid :
					f.write("s" + str(switchId) + ",s" + str(controlSwitch) + "\n")
					f.write("s" + str(switchId) + ",s"  + str((uGridId - 1)*nSwitchesPerGrid + 1) + "\n")
			else :
				f.write("h" + str(i) + "_1,s" + str(switchId) + "," + str(enclaveVlanId)  + "\n")


				
			
		
	
	

	
 
	
	
if __name__ == '__main__':
	
	genUGridTopoConfig("topology-configuration.txt")
	runTopology("topology-configuration.txt")
	
	
