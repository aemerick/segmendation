#!/usr/bin/python
# -*- coding: utf-8 -*-

import stravalib
import http.server
import urllib.parse
import webbrowser
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import os
import time
from mpl_toolkits.axes_grid1 import host_subplot
import mpl_toolkits.axisartist as AA

# -----------------------------------------------------------------------------
# *** Setup Section ***
# -----------------------------------------------------------------------------

# Port of the webserver
port = 5000

# Output Directory
out_dir = './out/'

# Initialize helper Vars

# limiter of the number of activities requested
limit = 2

# Create redirect URL
url = 'http://localhost:%d/authorization' % port
#url = 'http://127.0.0.1:%d/authorization' % port

# List of available types:
# https://pythonhosted.org/stravalib/api.html?highlight=get_activity_streams#stravalib.client.Client.get_activity_streams
types = ['time']

client_id, secret = open('client.secret').read().strip().split(',')
# Create the strava client, and open the web browser for authentication
client = stravalib.client.Client()
authorize_url = client.authorization_url(client_id=client_id,
                                         redirect_uri=url,
                                         scope="activity:read")
print('Opening: %s' % authorize_url)
webbrowser.open(authorize_url)


# -----------------------------------------------------------------------------
# Functions and Classes
# -----------------------------------------------------------------------------

# Define the web functions to call from the strava API
def UseCode(code):
    # Retrieve the login code from the Strava server

    regenerate_token = True
    if os.path.isfile('access.secret'):
        access_token, refresh_token, expires = open('access.secret').read().strip().split(',')
        expires = int(expires)

        if expires < (time.time() - 180):
            # regenerate if expering within the next few minutes
            print("regenerating access token set to expire at ", expires, time.time())
        else:
            regenerate_token = False
            print("Obtained access token from file. Still valid: ", expires, time.time())


    if regenerate_token:
        print("attempting to get access token")
        full_token = client.exchange_code_for_token(client_id=client_id,
                                                      client_secret=secret,
                                                      code=code)
        # Now store that access token somewhere (for now, it's just a local
        # variable)
        access_token = full_token['access_token']
        refresh_token = full_token['refresh_token']
        expires = int(full_token['expires_at'])

        print(full_token)
        f = open('access.secret','w')
        f.write(access_token)
        for k in ['refresh_token','expires_at']:
            f.write(","+str(full_token[k]))
        f.write('\n')
        f.close()

    client.access_token = access_token
    athlete = client.get_athlete()
    print("For %(id)s, I now have an access token %(token)s" %
          {'id': athlete.id, 'token': access_token})
    return client


def GetActivities(client, limit):
    # Returns a list of Strava activity objects, up to the number specified
    # by limit
    activities = client.get_activities(limit=limit)
    assert len(list(activities)) == limit

    return activities

def GetActivity(client, id):

    activity = client.get_activity(id)

    return activity


def GetStreams(client, activity, types):
    # Returns a Strava 'stream', which is timeseries data from an activity
    streams = client.get_activity_streams(activity,
                                          types=types, series_type='time')
    return streams


def DataFrame(dict, types):
    # Converts a Stream into a dataframe, and returns the dataframe
    # print(dict, types)
    df = pd.DataFrame()
    for item in types:
        if item in dict.keys():
            df.append(item.data)
    df.fillna('', inplace=True)
    return df


def ParseActivity(act, types):
    act_id = act.id
    name = act.name
    # print(str(act_id), str(act.name), act.start_date)
    streams = GetStreams(client, act_id, types)
    df = pd.DataFrame()

    # Write each row to a dataframe
    for item in types:
        if item in streams.keys():
            df[item] = pd.Series(streams[item].data, index=None)
        df['act_id'] = act.id
        df['act_startDate'] = pd.to_datetime(act.start_date)
        df['act_name'] = name
    return df


def convMs2Kmh(speed):
    # Convert m/s in km/h
    return speed / 1000 / (1 / 3600)

def prepareOneActivity(my_data, dir):
    # Prepare the heartrate data for barplot
    counts = [0, 0, 0, 0, 0]

    data = my_data['heartrate']
    for point in data:
        if (point < 137):
            counts[0] += 1
        elif (point >= 137 and point < 151):
            counts[1] += 1
        elif (point >= 151 and point < 165):
            counts[2] += 1
        elif (point >= 165 and point < 172):
            counts[3] += 1
        elif (point > 179):
            counts[4] += 1
    tmp = counts
    total = sum(tmp)
    counts = [(1. * x / total) * 100 for x in tmp]

    # Prepare the various data for boxplots

    hfrq_by_zones = [[], [], [], [], []]
    cadz_by_zones = [[], [], [], [], []]
    velo_by_zones = [[], [], [], [], []]

    my_list = list()
    my_list.append(list(my_data['heartrate']))
    my_list.append(list(my_data['velocity_smooth']))
    if ('cadence' in my_data):
        my_list.append(list(my_data['cadence']))
    else:
        my_list.append([0] * my_data['velocity_smooth'])

    my_array = zip(*my_list)

    for hr, vs, cd in my_array:
        vs = convMs2Kmh(vs)
        if (hr < 137):
            hfrq_by_zones[0].append(hr)
            cadz_by_zones[0].append(cd)
            velo_by_zones[0].append(vs)
        elif (hr >= 137 and hr < 151):
            hfrq_by_zones[1].append(hr)
            cadz_by_zones[1].append(cd)
            velo_by_zones[1].append(vs)
        elif (hr >= 151 and hr < 165):
            hfrq_by_zones[2].append(hr)
            cadz_by_zones[2].append(cd)
            velo_by_zones[2].append(vs)
        elif (hr >= 165 and hr < 172):
            hfrq_by_zones[3].append(hr)
            cadz_by_zones[3].append(cd)
            velo_by_zones[3].append(vs)
        elif (hr > 179):
            hfrq_by_zones[4].append(hr)
            cadz_by_zones[4].append(cd)
            velo_by_zones[4].append(vs)

    # -----------------------------------------------------------------------------
    # Prepare bar plot of number of values in the zone
    # -----------------------------------------------------------------------------

    objects = ('S', 'GA1', 'GA2', 'EB', 'SB')
    y_pos = np.arange(len(objects))

    plt.figure()

    plt.bar(y_pos, counts, align='center', alpha=0.5)
    plt.xticks(y_pos, objects)
    plt.ylabel('Percentage of activity')
    plt.xlabel('Zones')
    plt.title('Heartrate Zones')
    plt.ylim([0, 100])

    plt.savefig(dir + '/' + '1.png')

    # -----------------------------------------------------------------------------
    # Prepare the bar plot combined with boxplot of velocity & cadence
    # -----------------------------------------------------------------------------

    data_len = [int(i) for i in counts]

    plt.figure()

    host = host_subplot(111, axes_class=AA.Axes)
    plt.subplots_adjust(right=0.75)
    ax2 = host.twinx()
    ax3 = host.twinx()

    offset = 60
    new_fixed_axis = ax3.get_grid_helper().new_fixed_axis
    ax3.axis["right"] = new_fixed_axis(loc="right", axes=ax3,
                                       offset=(offset, 0))
    ax2.axis["right"].toggle(all=True)

    ax2_min = -100
    ax2_max = 175
    ax3_min = 0
    ax3_max = 100

    host.set_ylim([0, 100])
    ax2.set_ylim([ax2_min, ax2_max])
    ax3.set_ylim([ax3_min, ax3_max])

    host.set_xlabel("Zones")
    host.set_ylabel("Percentage of activity")
    ax2.set_ylabel("Cadence")
    ax3.set_ylabel("Velocity")


    host.bar(range(1, len(data_len) + 1), data_len, align='center',
             color="lightgrey")

    bp1 = ax2.boxplot(cadz_by_zones, widths=0.6)
    bp2 = ax3.boxplot(velo_by_zones, widths=0.6)

    ax2.axis["right"].label.set_color("red")
    ax3.axis["right"].label.set_color("blue")

    host.set_xticklabels(objects, rotation='vertical')
    # major ticks every 20, minor ticks every 5
    ax2_major_ticks = np.arange(ax2_min, ax2_max, 20)
    ax2_minor_ticks = np.arange(ax2_min, ax2_max, 5)
    ax2.set_yticks(ax2_major_ticks)
    ax2.set_yticks(ax2_minor_ticks, minor=True)

    ax3_major_ticks = np.arange(ax3_min, ax3_max, 20)
    ax3_minor_ticks = np.arange(ax3_min, ax3_max, 5)
    ax3.set_yticks(ax3_major_ticks)
    ax3.set_yticks(ax3_minor_ticks, minor=True)

    for box in bp1['boxes']:
        box.set(color='red', linewidth=1)

    for box in bp2['boxes']:
        box.set(color='blue', linewidth=1)

    plt.savefig(dir + '/' + '2.png')

    # -----------------------------------------------------------------------------
    # Setup
    # -----------------------------------------------------------------------------

    plt.figure()

    fig, axes = plt.subplots(nrows=1, ncols=2, figsize=(9, 4))

    bplot1 = axes[0].boxplot(hfrq_by_zones, vert=True, patch_artist=True)
    bplot2 = axes[1].boxplot(data, vert=True, patch_artist=True)

    colors = ['pink', 'lightblue', 'lightgreen']
    for bplot in (bplot1, bplot2):
        for patch, color in zip(bplot['boxes'], colors):
            patch.set_facecolor(color)

    axes[0].yaxis.grid(True)
    axes[1].yaxis.grid(True)
    axes[0].set_xticks([y + 1 for y in range(len(hfrq_by_zones))], )

    axes[0].set_xlabel('Zones')
    axes[0].set_ylabel('Heartrate')

    axes[0].set_ylim([100, 230])
    axes[1].set_ylim([100, 230])

    plt.setp(axes[0], xticks=[y + 1 for y in range(len(hfrq_by_zones))],
             xticklabels=objects)

    plt.setp(axes[1], xticks=[1],
             xticklabels=["All"])

    # -----------------------------------------------------------------------------
    # Display the plot windows
    # -----------------------------------------------------------------------------
    plt.savefig(dir + '/' + '3.png')


class MyHandler2(http.server.BaseHTTPRequestHandler):
    # Handle the web data sent from the strava API

    allDone = False
    data = {}

    def do_HEAD(self):
        return self.do_GET()

    def do_GET(self):
        # Get the API code for Strava
        # self.wfile.write('<script>window.close();</script>')
        # print(self.path)
        full_output = urllib.parse.parse_qs(
               urllib.parse.urlparse(self.path).query)

        print("---------- full out    ", full_output)
        code = full_output['code'][0]
        #code = request.args.get('code') #
        print("---------", code)
        # Login to the API
        client = UseCode(code)

        # Retrieve the last limit activities
        activities = GetActivities(client, limit)
        for item in activities:
            print(item.name)


        # Loop through the activities, and create a dict of the dataframe
        # stream data of each activity
        MyHandler2.activities      = [x for x in activities]
        MyHandler2.activities_list = []
        for act in activities:
            print(dir(act))
            MyHandler2.activities_list.append(client.get_activity(act.id))

            #print(activity.__dict__)



        #print("looping through activities...")
        #df_lst = {}
        #for act in activities:
        #    df_lst[act.start_date] = ParseActivity(act, types)

        #MyHandler2.data = df_lst
        MyHandler2.allDone = True

# -----------------------------------------------------------------------------
# *** Run Section ***
# -----------------------------------------------------------------------------


# -----------------------------------------------------------------------------
# Request access via local browser
# -----------------------------------------------------------------------------




# -----------------------------------------------------------------------------
# Start webserver and wait for redirect local browser
# -----------------------------------------------------------------------------
print("opening local browser for server")
httpd = http.server.HTTPServer(('localhost', port), MyHandler2)
while not MyHandler2.allDone:
    print(MyHandler2.allDone)
    httpd.handle_request()

# -----------------------------------------------------------------------------
# Data preparation
# -----------------------------------------------------------------------------
# if os.path.exists(out_dir):
#    os.remove(out_dir)

#if not os.path.isdir(out_dir):
#    os.makedirs(out_dir)
#html_str = """
#<table border=1>
#     <tr>
#       <th>Name</th>
#       <th>1</th>
#       <th>2</th>
#       <th>3</th>
#     </tr>
#     <indent>
#"""

#name_counter = {}

#for act in iter(MyHandler2.data.values()):
#    if (len(act['act_name']) > 0 and ('heartrate' in (act))):
#        if act['act_name'][0] in name_counter:
#            name_counter[act['act_name'][0]] += 1
#            act['act_name'][0] = act['act_name'][0] + str(name_counter[
#                act['act_name'][0]])
#        else:
#            name_counter[act['act_name'][0]] = 0

#for act in iter(MyHandler2.data.values()):
#    if (len(act['act_name']) > 0 and ('heartrate' in (act))):
#        print(act['act_name'][0])
#        os.makedirs(out_dir + '/' + act['act_name'][0])
#        prepareOneActivity(act, out_dir + "/" + act['act_name'][0])
#        html_str += "<tr><td>" + str(act['act_name'][0]) + "</td>"
#        html_str += '<td><image src="' +  './' + act['act_name'][0] + '/1.png' + '"/></td>'
#        html_str += '<td><image src="' +  './' + act['act_name'][0] + '/2.png' + '"/></td>'
#        html_str += '<td><image src="' +  './' + act['act_name'][0] + '/3.png' + '"/></td>'
#html_str += """
#     </indent>
#</table>
#"""

#Html_file = open(out_dir + '/' + "report.html", "w")
#Html_file.write(html_str)
#Html_file.close()

#webbrowser.open(out_dir + '/' + "report.html")
