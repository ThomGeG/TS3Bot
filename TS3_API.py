'''
Created on 4 Jul 2016

@author: Tom
'''

import telnetlib, time
from Exceptions import IllegalStateException, TS3Exception

TS3_ESCAPE = [ #Series of escape characters required to communicate successfully with TS3.
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

    #TS3 has an anti-flood system. This number defines the time this application will sleep between consecutive requests in some functions.
    sleep_time = 0

    conn = None
    is_Connected = False
    is_Authenticated = False

    clid = -1 #This ServerQuery instance's client ID.
    chid = -1 #The ID of the channel this instance currently resides in.

    ###############################################################################
    ##################### Networking/IO Functionalities ###########################
    ###############################################################################

    def connect(self, address, port, sid=1):
        """ Connect to a target TS3 server via telnet connection. """

        self.conn = telnetlib.Telnet(address, port)

        if (
            self.conn.read_until(b"\n\r") == b"TS3\n\r" and
            self.conn.read_until(b"\n\r") != b""
        ):
            self.is_Connected = True
            self.changeSID(sid) #Select virtual server
        else:
            raise ConnectionError("An unknown connection error occurred and we could not verify a connection to the server. You're likely flood banned or the server is down.")

    def disconnect(self):
        """ Disconnect from the current TS3 server and close the telnet connection. """

        if not self.is_Connected:
            raise IllegalStateException("Not connected to a server; Cannot disconnect!")

        try: #Attempt to logout
            self.logout()
        except IllegalStateException:
            pass

        #Close connection
        self.submitCommand("quit")
        self.conn.close()

        #Reset internal variables
        self.conn = None
        self.is_Connected = False
        self.is_Authenticated = False

    def submitCommand(self, command):
        """
            The corner stone of communication between the TS3 server and ourselves.
            Transmits a command to the server and then returns its response.
        """

        if not self.is_Connected:
            raise IllegalStateException("Not connected to a server; Cannot submit command!")

        self.conn.write((command + "\n\r").encode()) #Encode and transmit command.

        return self.getResponse() #Get and return response.

    def getResponse(self):
        """ Listens for and returns a response from the server after a command is exectued. """

        raw_response = self.conn.read_until(b"\n\r").decode().strip() #Collect from pipe until terminating character is read.

        #Check for OK response from pipe.
        if(raw_response[:5] == "error"):
            error_report = self.parseMap(raw_response[6:])  #Retrieve the error and parse it
            if error_report["id"] is not "0":               #If it was not an OK response...
                raise TS3Exception(error_report["msg"], error_report["id"]) #...raise it as an exception to the calling function.
            return None #Otherwise just ignore it.

        #Is the response a list?
        if "|" in raw_response:
            values = [self.parseMap(x) for x in raw_response.split('|')] #Parse all elements of the list
            self.getResponse() #Purge OK response from pipe
            return values

        else: #It was just a map!
            self.getResponse() #Purge OK response from pipe
            return self.parseMap(raw_response)

    def parseMap(self, raw_string):
        """
            Function that turns the formatted map-like string response of a TS3 server into a python dictionary/map/associate array/what you wish to call it.

            Example Input: virtualserver_status=unknown virtualserver_unique_identifier virtualserver_port=0 virtualserver_id=0 client_id=0
            Example Output: {"virtualserver_status" : "unknown", "virtualserver_unique_identifier" : None, "virtualserver_port" : "0", "virtualserver_id" : "0", "client_id" : "0"}
        """

        dic = {}
        for ele in raw_string.split(" "): #Key value pairs are delimited by spaces (" "). Iterate over the key value pairs...

            pos = ele.find('=') #Elements are of the form "key=value". Not as simple as "dic + ele.split("=")", value may contain "=" as it is not a reserved character.

            if pos != -1:
                dic[ele[:pos]] = self.decode(ele[pos+1:]) #dic[key] = value
            else:
                dic[ele] = None #No "=" present means this key had no associated value and should therefore be None.

        return dic

    def encode(self, s):
        """ Utilizes TS3_ESCAPE to replace any/all characters reserved by TS3 for formatting transmissions/response into their safe escape character counterparts. """

        for (py_char, sq_char) in TS3_ESCAPE: #For each character pair in the list...
            s = s.replace(py_char, sq_char)   #...replace the normal character with it's ServerQuery escape character.

        return s

    def decode(self, s):
        """ Utilizes TS3_ESCAPE to replace any/all TS3 escape characters back into their normal characters. """

        for (py_char, sq_char) in reversed(TS3_ESCAPE): #For each character pair in the REVERSED ORDER of the list...
            s = s.replace(sq_char, py_char)             #...replace the ServerQuery escape character with it's normal character.

        return s

    ###############################################################################
    ############################ Server Query Commands ############################
    ###############################################################################

    def login(self, username, password, nickname=None):
        """ Raise privledges and permission values by logining into a ServerQuery account. """

        if not self.is_Connected:
            raise IllegalStateException("Not connected to a server; Cannot login!")

        self.submitCommand("login " + username + " " + password) #Authenticate
        self.submitCommand("clientupdate client_nickname=" + (self.encode(nickname) if nickname is not None else self.encode(username))) #Change nickname to username.
            #Update meta-data
        wai = self.submitCommand("whoami")
        (self.clid, self.chid) = (wai['client_id'], wai['client_channel_id'])

        if(self.clid != -1 and self.chid != -1):
            self.is_Connected = True
            self.is_Authenticated = True

    def logout(self):
        """ Logout and return to the default ServerQuery user group. """

        if not self.is_Authenticated:
            raise IllegalStateException("Not logged in; Cannot logout!")

        self.submitCommand("logout")
        self.is_Authenticated = False

    def changeSID(self, sid):
        """ Change what virtual server the ServerQuery instance is operating on. """
        self.submitCommand("use sid=" + str(sid))

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
        """ Get a far more detailed list of meta-data than what is provided by "clientlist". """
        return self.submitCommand("clientinfo clid=" + str(clientID))

    def setChannelGroup(self, clientDBID, channelGroupID, channelID):
        return self.submitCommand("setclientchannelgroup cldbid=" + str(clientDBID) + " cid=" + str(channelID) + " cgid=" + channelGroupID)

    def getConnectedClients(self, detailed=False):
        """ Request a list of the clients currently connected to the server. Set detailed to True if you require more detailed information than what TS3's "clientlist" command provides. """
        clients = self.submitCommand("clientlist")

        if detailed: #User asked for detailed client information that requires a follow up request for each client.

            disconnected = [] #Clients that disconnected whilst this funciton was executing. We'll purge them before returning.

            for client in clients:
                try:
                    time.sleep(self.sleep_time)                         #Sleep to prevent flood ban.
                    client.update(self.getClientInfo(client["clid"]))   #Update the dictionary with the additional values.
                except TS3Exception as e:
                    if e.error_ID is 512: #512 is "client could not be targeted", IE. they logged out.
                        disconnected.append(client) #...append them into a list to purge later.
                    else:
                        raise e #otherwise raise the exception as something bad happened.

            for client in disconnected:
                clients.remove(client) #PURGE!

        return clients

    def getAllClients(self):
        """ Requests a list of EVERY client (incl. offline ones) from the database. """
        return self.submitCommand("clientdblist")

    def getClientServerGroups(self, clientDBID):
        return self.submitCommand("servergroupsbyclientid cldbid=" + str(clientDBID))

    def kick(self, clientID, reason, fromServer):

        if len(reason) > 40:
            raise ValueError("The reason for a kick can be no greater than 40 characters. Your message was:\"" + reason + "\" w/ " + len(reason) + " characters.")

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
