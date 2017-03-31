'''
Created on 6 Jul 2016
@author: Tom

    A small script used to manage the poseidon servers TS3 server.
    When the server is close to capacity I run it to clean house and hopefully
    free some slots for other clients to connect.

'''
import os
import sys
import time

from config     import *
from Logger     import Logger
from TS3_API    import TS3_API
from Exceptions import TS3Exception

API = None
LOGGER = None

def manageUsersGroups(server_info, connected_clients):
    """
        Iterates over every client currently connected to the server and:
            1. Checks that no client belongs to more than 1 server group. If they do remove them from all but there highest ranked group (Based on groupsortid)
            2. If a client is only a member of the default group and they have > 50 connections, upgrade their rank to 'User'.
    """

    server_groups = dict([(x["sgid"], x) for x in API.getServerGroups()]) #Get the list of server groups and their information (In the form of a dictionary using the group ID as a key for lookup purposes).

    #Ugly means to find the next rank above the default one using "sortid".
    LOWEST_NON_DEFAULT_GROUP_ID = max(server_groups, key=lambda x: int(server_groups[x]["sortid"]) if x is not server_info["virtualserver_default_server_group"] else -1)

    for client in connected_clients:

        client_groups = client["client_servergroups"].split(',') #IDs come as a single string delimited with ",". Example; "1,2,3,4".

        #Get the users best group based on the groups sort IDs.
        best_SGID = min(client_groups, key=lambda x: server_groups[x]["sortid"])

        #If their best group is the default group and they've connected 50 times promote them, they earned it.
        if best_SGID is server_info["virtualserver_default_server_group"] and int(client["client_totalconnections"]) > 50:
            LOGGER.log("Adding \"" + client["client_nickname"] + "\" (" + client["client_database_id"] + ") to group \"" + server_groups[LOWEST_NON_DEFAULT_GROUP_ID]["name"] + "\"")
            API.addClientToServerGroup(client["client_database_id"], LOWEST_NON_DEFAULT_GROUP_ID)
        else:
            #For all other ranks remove.
            for group in client_groups:
                if group != best_SGID:
                    LOGGER.log("Removing \"" + client["client_nickname"] + "\" (" + client["client_database_id"] + ") from group \"" + server_groups[group]["name"] + "\"")
                    API.removeClientFromServerGroup(client["client_database_id"], group)

        time.sleep(1) #Take a rest to prevent recieve a flood ban from the server.

def kickIdlers(server_info, connected_clients):
    """
        Kicks clients who have either been idle for too long or for too much of their time connected.
        The definitions of "too long/much" is dynamic and depends upon the number of users connected to the server.
    """

    idlers = [] #We're going to collect clients requiring a kick in a list, then kick them all at once for exception handling reasons.

    BASE_MAX_IDLE_PERCENTAGE = 75
    server_info["virtualserver_emptyslots"] = int(server_info["virtualserver_maxclients"]) - int(server_info["virtualserver_clientsonline"])

    #10 minute base with 5 minutes for every available slot.
    max_idle_time = 600_000 + (int(server_info["virtualserver_emptyslots"]) * 5 * 60 * 1000)

    for client in connected_clients:

        #Ignore ServerQuery clients (That's us!).
        if client["client_platform"] == "ServerQuery":
            continue

        #If a client has exceeded the maximum time allowed to be idle, kick them.
        if int(client["client_idle_time"]) >= max_idle_time:
            idlers.append((client, "Idle for " + convertMillis(int(client["client_idle_time"])) + "."))
            continue

        #Calculate the percentage of time a client has been idle while connected to the server.
        client_idle_percent = int(int(client["client_idle_time"])/float(client["connection_connected_time"]) * 100)
        #If a client has spent more than (BASE_MAX_IDLE_PERCENTAGE + 1% for each empty slot) percent of their time idle, kick them.
        if client_idle_percent > BASE_MAX_IDLE_PERCENTAGE + int(server_info["virtualserver_emptyslots"]):
            idlers.append((client, "Idle for " + str(client_idle_percent) + "% of time connected."))
            continue

    for (client, reason) in idlers:

        LOGGER.log("Kicking \"" + client["client_nickname"] + "\" (" + client["client_database_id"] + ") for reason: " + reason)

        try: #Attempt the kick.
            API.kick(client["clid"], reason, True)
            time.sleep(1) #Take a break to prevent a flood ban.
        except TS3Exception as e: #Failed kicks are then logged for debugging purposes.
            LOGGER.log(client["client_nickname"] + "\" (" + client["client_database_id"] + ") could not be kicked (" + str(e) + ")")

    LOGGER.log("Kicked " + str(len(idlers)) + " clients.")

def convertMillis(millis):
    """
        Helper function to convert time from milliseconds to a more human readible format, namely a string in the form:
            H hour(s) M minute(s) S second(s)
    """

    millis /= 1000
    seconds = millis % 60

    millis /= 60
    minutes = millis % 60

    hours = (millis/60)

    return((hours + " hour" + ("s" if hours > 1 else "")) if hours != 0 else "" +
           (minutes + " minute" + ("s" if minutes > 1 else "")) if minutes != 0 else "" +
           (seconds + " seconds" + ("s" if seconds > 1 else "")) if seconds != 0 else "")

if __name__ == '__main__':

    os.chdir(sys.argv[0] + "/..") #Change our working directory to where this executed file is located.

    API = TS3_API()     #Setup the telnet connection to the TS3 server.
    API.sleep_time = 1  #Set the sleep time between server requests. This prevents flooding the server and it taking anti-flood measures.

    #Set up the logger.
    LOGGER = Logger("logs")
    LOGGER.log("RUNNING TS3Bot!")

    #Connect to the TS3 server and login.
    API.connect(DOMAIN, PORT)
    API.login(USERNAME, PASSWORD)

    #Acquire server info and connected clients.
    server_info = API.getServerInfo()
    connected_clients =  API.getConnectedClients(detailed=True)

    #Execute the heart of our script!
    kickIdlers(server_info, connected_clients)
    manageUsersGroups(server_info, connected_clients)

    #Give us a closing sit. rep.
    server_info = API.getServerInfo()
    LOGGER.log("Server @ " + server_info["virtualserver_clientsonline"] + "/" + server_info["virtualserver_maxclients"] + ".")

    #Formally close up shop.
    API.logout()
    API.disconnect()
