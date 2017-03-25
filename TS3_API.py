'''
Created on 4 Jul 2016

@author: Tom
'''

import telnetlib, time
from Exceptions import IllegalStateException, TS3Exception

TS3_ESCAPE = [
        ("\\", r"\\"), # \
        ("/", r"\/"),  # /
        (" ", r"\s"),  # Space
        ("|", r"\p"),  # |
        ("\a", r"\a"), # Bell
        ("\b", r"\b"), # Backspace
        ("\f", r"\f"), # Form Feed
        ("\n", r"\n"), # Newline
        ("\r", r"\r"), # Carriage Return
        ("\t", r"\t"), # Horizontal Tab
        ("\v", r"\v")  # Vertical Tab
]

class TS3_API:

    #TS3 has an anti-flood system. This number defines the time this application sleeps between consecutive requests.
    sleep_time = 0

    conn = None
    is_Connected = False
    is_Authenticated = False

    clid = -1
    chid = -1

    def connect(self, domain, port):

        self.conn = telnetlib.Telnet(domain, port)

        if (
            self.conn.read_until(b"\n\r") == b"TS3\n\r" and
            self.conn.read_until(b"\n\r") != b""
        ):
            self.is_Connected = True
        else:
            raise ConnectionError("An unknown connection error occurred and we could not verify a connection to the server. You're likely flood banned or the server is down.")

    def disconnect(self):

        if not self.is_Connected:
            raise IllegalStateException("Not connected to a server; Cannot disconnect!")

        try:
            self.logout()
        except IllegalStateException:
            pass

        self.submitCommand("quit")
        self.conn.close()

        self.conn = None
        self.is_Connected = False
        self.is_Authenticated = False

    def changeSID(self, sid):
        self.submitCommand("use sid=" + str(sid))

    def login(self, username, password, sid=1, nickname=""):

        if not self.is_Connected:
            raise IllegalStateException("Not connected to a server; Cannot login!")

        self.changeSID(sid)                #Select virtual server.
        self.submitCommand("login " + username + " " + password) #Authenticate

        self.submitCommand("clientupdate client_nickname=" + (self.encode(nickname) if nickname != "" else self.encode(username))) #Change nickname to username.

        #Update meta-data
        wai = self.submitCommand("whoami")
        (self.clid, self.chid) = (wai['client_id'], wai['client_channel_id'])

        if(self.clid != -1 and self.chid != -1):
            self.is_Connected = True
            self.is_Authenticated = True

    def logout(self):

        if not self.is_Authenticated:
            raise IllegalStateException("Not logged in; Cannot logout!")

        self.submitCommand("logout")
        self.is_Authenticated = False

    def submitCommand(self, command):

        if not self.is_Connected:
            raise IllegalStateException("Not connected to a server; Cannot submit command!")

        self.conn.write((command + "\n\r").encode())

        return self.getResponse()

    def getResponse(self):

        rawResponse = self.conn.read_until(b"\n\r").decode().strip()

        #Check for OK response from pipe.
        if(rawResponse[:5] == "error"):
            errorReport = self.parseMap(rawResponse[6:])
            if errorReport["id"] is not "0":
                raise TS3Exception(errorReport["msg"], errorReport["id"])
            return None

        #Is the response a list?
        listResponse = rawResponse.split('|')
        if len(listResponse) > 1:
            values = []
            for ele in listResponse:
                values.append(self.parseMap(ele))

            self.getResponse() #Purge OK response from pipe
            return values

        else: #It was just a map!

            self.getResponse() #Purge OK response from pipe
            return self.parseMap(rawResponse)

    def parseMap(self, raw):

        dic = {}
        for ele in raw.split(" "):

            pos = ele.find('=')

            if pos != -1:
                dic[ele[:pos]] = self.decode(ele[pos+1:])
            else:
                dic[ele] = None

        return dic

    def encode(self, s):

        for (py_char, sq_char) in TS3_ESCAPE:
            s = s.replace(py_char, sq_char)

        return s

    def decode(self, s):

        for (py_char, sq_char) in reversed(TS3_ESCAPE):
            s = s.replace(sq_char, py_char)

        return s

    def getServerInfo(self):
        return self.submitCommand("serverinfo")

    def getServerList(self):
        return self.submitCommand("serverlist")

    def getChannelList(self):
        return self.submitCommand("channellist")

    def getChannelInfo(self, channelID):
        return self.submitCommand("channelinfo cid=" + str(channelID))

    def moveChannel(self, targetChannelID, parentChannelID, orderID=None):
        return self.submitCommand("channelmove cid=" + str(targetChannelID) + " cpid=" + str(parentChannelID) + ("order=" + orderID) if orderID != None else "")

    def deleteChannel(self, channelID, force=True):
        return self.submitCommand("channeldelete cid=" + str(channelID) + " force=1" if force else "");

    def getChannelGroups(self):
        return self.submitCommand("channelgrouplist")

    def getChannelGroupMembers(self, channelGroupID):
        return self.submitCommand("channelgroupclientlist cgid=" + channelGroupID)

    def getClientsChannelGroups(self, clientDBID):
        return self.submitCommand("channelgroupclientlist cldbid=" + str(clientDBID))

    def getClientInfo(self, clientID):
        return self.submitCommand("clientinfo clid=" + str(clientID))

    def setChannelGroup(self, clientDBID, channelGroupID, channelID):
        return self.submitCommand("setclientchannelgroup cldbid=" + str(clientDBID) + " cid=" + str(channelID) + " cgid=" + channelGroupID)

    def getConnectedClients(self, detailed=False):

        clients = self.submitCommand("clientlist")

        if detailed: #User asked for detailed client information that requires a follow up request.

            disconnected = []

            for client in clients:
                try:
                    time.sleep(self.sleep_time)                         #Sleep to prevent flood ban.
                    client.update(self.getClientInfo(client["clid"]))   #Update the dictionary with the additional values.
                except TS3Exception:
                     #If an an exception has been raised it's because the client disconnected and cannot be targeted anymore.
                     #In these cases append the disconnected client into a list to later be purged from the final returned list.
                    disconnected.append(client)

            for client in disconnected:
                clients.remove(client)

        return clients

    def getAllClients(self):
        return self.submitCommand("clientdblist")

    def getClientServerGroups(self, clientDBID):
        return self.submitCommand("servergroupsbyclientid cldbid=" + str(clientDBID))

    def kick(self, clientID, reason, fromServer):

        if len(reason) > 40:
            raise ValueError("The reason for a kick can be no greater than 40 characters. Your message was:\"" + reason + "\".")

        return self.submitCommand("clientkick clid=" + str(clientID) + (" reasonid=" + "5" if fromServer else "4") + " reasonmsg=" + self.encode(reason))

    def banClient(self, clientID, time=0, reason=""):

        if len(reason) > 40:
            raise ValueError("The reason for a kick can be no greater than 40 characters. Your message was:\"" + reason + "\".")

        return self.submitCommand("banclient clid=" + str(clientID) + (" time=" + time) if time > 0 else "" + (" banreason=" + self.encode(reason)) if reason != "" else "")

    def moveClient(self, clientID, channelID):
        return self.submitCommand("clientmove clid=" + str(clientID) + " cid=" + str(channelID));

    def pokeClient(self, clientID, message):
        return self.submitCommand("clientpoke clid=" + str(clientID) + " msg=" + self.encode(message));

    def messageClient(self, clientID, message):
        self.message(clientID, 1, message);

    def messageChannel(self, channelID, message):

        if self.chid != channelID:
            self.moveClient(self.clid, channelID) #Need to be in the channel to message it...
            self.chid = channelID

        return self.message(channelID, 2, message);

    def messageServer(self, serverID, message):
        return self.message(serverID, 3, message);

    def message(self, targetID, targetMode, message):
        return self.submitCommand("sendtextmessage targetmode=" + str(targetMode) + " target=" + str(targetID) + " msg=" + self.encode(message));

    def offlineMessageClient(self, clientUID, subject, message):
        return self.submitCommand("messageadd cluid=" + str(clientUID) + " subject=" + self.encode(subject) + " message=" + self.encode(message));

    def changeDisplayName(self, name):
        return self.submitCommand("clientupdate client_nickname=" + self.encode(name));

    def globalMessage(self, message):
        return self.submitCommand("gm msg=" + self.encode(message));

    def getServerGroups(self):
        return self.submitCommand("servergrouplist")

    def getServerGroupMembers(self, serverGroupID):
        return self.submitCommand("servergroupclientlist sgid=" + str(serverGroupID))

    def addClientToServerGroup(self, clientDBID, serverGroupID):
        return self.submitCommand("servergroupaddclient sgid=" + str(serverGroupID) + " cldbid=" + str(clientDBID));

    def removeClientFromServerGroup(self, clientDBID, serverGroupID):
        return self.submitCommand("servergroupdelclient sgid=" + str(serverGroupID) + " cldbid=" + str(clientDBID));
