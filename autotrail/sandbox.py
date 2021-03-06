import os
import requests
import numpy as np




def getTrails(private_key, lat, lon, verbose = False, **kwargs):
    """
    Wrapper around TrailRunProject's getTrails API
    to do some error checking and nicely generate the string for
    optional arguments.

    Additional kwargs are the parameters associated with the API:
    `maxDistance`, `maxResults`, `sort`, `minLength`, and `minStars`.

    Parameters:
    -----------
    private_key   : (string) Private key associated with account making request
    lat           : (float)  Latitude of query location
    lon           : (float)  Longitude
    verbose       : (bool). Optional. Print more info while running


    Returns:
    --------
    response   :   API response (from requests.get() )
    """


    args = "lat=%f&lon=%f&key=%s"%(lat,lon,private_key)

    if len(kwargs) > 0:
        possible_args = {'maxDistance':"%.2f",
                         'maxResults':"%d",
                         'sort':"%s",
                         'minLength':"%.2f",
                         'minStars' :"%d"}

        for key in kwargs.keys():
            if key in possible_args:
                args = args + "&" + key + "=" +(possible_args[key])%(kwargs[key])
                print("adding " + key + " to args")
            else:
                print("Key not found in possible getTrails arguments : ",key, kwargs[key])
                raise KeyError

    if verbose:
        print("Running with arg : ", args)
    url  = "https://www.trailrunproject.com/data/get-trails?"+args

    response = requests.get(url)

    #print("Status Code: ", response.status_code)
    #print(response)
    #print(response.__dict__)

    if response.status_code != 200:
        print("Error in getTrails API call ", response.status_code)
        raise RuntimeError



    return response


if __name__ == "__main__":

    #
    # Personal key for making API requests
    #
    private_key = open('privatekey.secret').read().strip()

    # test: Boulder, CO

    #
    # workflow:
    #   1) use api to get all trails
    #   2) database of trail names and summary statistics
    #   3) iterate through ALL trail websites and pull gpx
    #      file from each (UGH)... may need to iterate users
    #      AND IPs AND UGHHHHHHH... but could be OK
    #   --- maybe run like 1 scrape per minute? 
    #   4) profit?
    #   5) KEY: Need to figure out how to link and filter out
    #      overlapping trail routes from the list to get ONE
    #      trail map of non-overlapping GPX points that can be
    #      interconnected. How to deal with branched trails ??
    #      maybe allow connections to all points within X distance?
    #
    #
    lat = 40.0274
    lon = -105.2519


    getTrails(private_key, lat, lon)
