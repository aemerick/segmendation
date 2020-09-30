"""

    Author  : Andrew Emerick
    e-mail  : aemerick11@gmail.com
    year    : 2020

    LICENSE :GPLv3


    Processing OSM map data to the format and featues needed for
    routing.

    Auto-generated hiking and trail running routes anywhere where
    OSM has hiking data available. Optimized routes are
    based on given user-specified contraints.

"""

import numpy as np
import gpxpy
import shapely

from planit.autotrail.trailmap import TrailMap

import planit.autotrail.process_gpx_data as gpx_process



def process_ox(osx_graph, hiking_only = True):
    """
    Gather list of edges and nodes
    """

    edges = []
    mandatory_features = ['geometry']
    all_hway_types = ['tertiary', 'residential', 'path', 'unclassified', 'secondary',
                      'service', 'footway', 'pedestrian', 'trunk', 'primary', 'trunk_link',
                      'track', 'motorway_link', 'motorway', 'cycleway', 'tertiary_link', 'primary_link',
                      'living_street', 'secondary_link', 'steps']

    highway_types = {}
    for k in ['tertiary','residential','secondary','service','primary','trunk','trunk_link',
              'tertiary_link','primary_link','living_street','secondary_link']:
        highway_types[k] = 'road'

    for k in ['path','unclassified','footway','pedestrian']:
        highway_types[k] = k

    if hiking_only:
        edges = [(u,v,d) for (u,v,d) in osx_graph.edges(data=True) if all(f in d.keys() for f in mandatory_features) and any(f in d['highway'] for f in ['path','footway','track'])]

    else:
        edges = [(u,v,d) for (u,v,d) in osx_graph.edges(data=True) if all(f in d.keys() for f in mandatory_features)]

        #
        # set ones and zeros for each type of path (really road vs hiking)
        #
        for (u,v,d) in edges:
            for k in highway_types:
                if not (highway_types[k] in d.keys()) and k in d['highway']:
                    d[highway_types[k]] = 1
                else:
                    d[highway_types[k]] = 0

    #
    # now I need to add in all edge attributes
    #

    nodes = np.unique(np.concatenate([(u,v) for (u,v,d) in edges]).ravel())
    nodes = [(n, osx_graph._node[n]) for n in nodes]

    for n,d in nodes:
        d['lat'] = d['y']
        d['long'] = d['x']
        d['elevation'] = gpx_process._elevation_data.get_elevation(d['lat'],d['long'])
        d['index'] = d['osmid']

    edges = compute_osm_edge_properties(edges, nodes)

    tmap = TrailMap()
    tmap.graph['crs'] = osx_graph.graph['crs']
    tmap.add_edges_from(edges)
    tmap.add_nodes_from(nodes)

    return tmap



def compute_osm_edge_properties(edges, nodes):
    """

    """

    for i in range(len(edges)):
        tail, head, d = edges[i]

        #
        # by convention, lets make it such that the tail of every segment
        # starts at the node with the lower index (tail < head!)
        # tail and head are the node IDs, NOT their number in the node list
        if tail > head:
            val = head*1
            head = tail*1
            tail = val*1

        #
        # taili and headi are the list indexes NOT the node ID's
        #
        taili = [j for j,(ni,nd) in enumerate(nodes) if nd['osmid'] == tail][0]
        headi = [j for j,(ni,nd) in enumerate(nodes) if nd['osmid'] == head][0]

        #print(tail,head, taili, headi)

        if len(d['geometry'].coords[0]) == 2:
            tail_coords = (nodes[taili][1]['long'], nodes[taili][1]['lat'])
            head_coords = (nodes[headi][1]['long'], nodes[headi][1]['lat'])
        elif len(d['geometry'].coords[0]) == 3:
            tail_coords = (nodes[taili][1]['long'], nodes[taili][1]['lat'], nodes[taili][1]['elevation'])
            head_coords = (nodes[headi][1]['long'], nodes[headi][1]['lat'], nodes[headi][1]['elevation'])
        else:
            raise RuntimeError


        # now, check and see if the geometry needs to be flipped:
        # compute distances of tail node to each end of the segment.
        # this MAY not work the best if the segment is a closed loop (or
        # of similar shape...)
        tail_to_left  = gpxpy.geo.distance(tail_coords[1],
                                           tail_coords[0],
                                           0.0,   # elevation doesn't matter here
                                           d['geometry'].coords[0][1], # long lat!!
                                           d['geometry'].coords[0][0],
                                           0.0)

        tail_to_right = gpxpy.geo.distance(tail_coords[1],
                                           tail_coords[0],
                                           0.0,   # elevation doesn't matter here
                                           d['geometry'].coords[-1][1],
                                           d['geometry'].coords[-1][0],
                                           0.0)

        flip_geometry = False
        if tail_to_right < tail_to_left: # flip the geometry
            flip_geometry = True
            d['geometry'] = shapely.geometry.LineString(d['geometry'].coords[::-1])

        # append node coords to line to make everything continuous
        new_line = (d['geometry']).append(head_coords)
        new_line = new_line.prepend(tail_coords)

        #
        # Generate a GPX track object from this data to (easily) add in
        # elevations.
        #
        gpx = gpxpy.gpx.GPX()
        gpx_track = gpxpy.gpx.GPXTrack()
        gpx.tracks.append(gpx_track)

        gpx_segment = gpxpy.gpx.GPXTrackSegment()
        gpx_track.segments.append(gpx_segment)

        gpx_points  = [gpxpy.gpx.GPXTrackPoint(x[1],x[0]) for x in new_line.coords]
        gpx_segment.points.extend(gpx_points)

        # add in elevation data
        gpx = add_elevations(gpx, smooth=True)
        gpx_segment = gpx.tracks[0].segments[0]

        # point-point distances and elevations
        #
        # NOTE: Elevation gain and elevation loss requires defining a direction
        #       to travel on the trail. By convention the default direction
        #       will be from the tail -> head, where the node number of tail <
        #       the node number of head. So elevation_gain becomes
        #       elevation_loss when travelling from head to tail!!
        #

        distances   = gpx_distances(gpx_segment.points)
        elevations  = np.array([x.elevation for x in gpx_segment.points])
        dz          = (elevations[1:] - elevations[:-1])  # change in elevations
        grade       = dz / distances * 100.0            # percent grade!
        grade[np.abs(distances) < 0.1] = 0.0            # prevent arbitary large grades for short segs with errors


        d['geometry']         = shapely.geometry.LineString([(x.longitude,x.latitude,x.elevation) for x in gpx_segment.points])
        d['distance']         = np.sum(distances)
        d['elevation_gain']   = np.sum(dz[dz>0])            # see note above!
        d['elevation_loss']   = np.abs(np.sum( dz[dz<0] ))  # store as pos val
        d['elevation_change'] = d['elevation_gain'] + d['elevation_loss']
        d['min_grade']        = np.min(grade)
        d['max_grad']         = np.max(grade)
        d['average_grade']    = np.average(grade, weights = distances) # weighted avg!!
        d['min_altitude']     = np.min(elevations)
        d['max_altitude']     = np.max(elevations)
        d['average_altitude'] = np.average(0.5*(elevations[1:]+elevations[:-1]),weights=distances)
        d['traversed_count']  = 0

        # apparenlty geopandas uses fiona to do writing to file
        # which DOESN"T support storing lists / np arrays into individual
        # cells. The below is a workaround (and a sin).. converting to a string
        #
        # MAKING ELEVATIONS SAME LENGTH AS DISTANCES!!
        #
        d['elevations']  = ','.join(["%6.2E"%(a) for a in 0.5*(elevations[1:]+elevations[:-1])])
        d['grades']      = ','.join(["%6.2E"%(a) for a in grade])
        d['distances']   = ','.join(["%6.2E"%(a) for a in distances])

    return edges