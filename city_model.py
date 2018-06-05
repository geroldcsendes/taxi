#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Nov 20 13:00:15 2017

@author: bokanyie
"""

import numpy as np
import pandas as pd
import json
from random import shuffle, choice
import matplotlib.pyplot as plt
from queue import Queue
from time import time
from copy import deepcopy
from scipy.stats import entropy


class City:
    """
    Represents a grid on which taxis are moving.
    """

    def __init__(self, **config):
        """      
        Parameters
        ----------
        
        n : int
            width of grid
        
        m : int
            height of grid

        base_coords : [int,int]
            grid coordinates of the taxi base
            
        base_sigma : float
            standard deviation of the 2D Gauss distribution
            around the taxi base

        Attributes
        ----------
        A : np.array of lists
            placeholder to store list of available taxi_ids at their actual
            positions

        n : int
            width of grid
        
        m : int
            height of grid

        base_coords: [int,int]
            coordinates of the taxi base
            
        base_sigma: float
            standard deviation of the 2D Gauss distribution
            around the taxi base
                    
        
        
        """
        if ("n" in config) and ("m" in config):
            self.n = config["n"]  # number of pixels in x direction
            self.m = config["m"]  # number of pixels in y direction

            # array that stores taxi_id of available taxis at the
            # specific position on the grid
            # we initialize this array with empy lists
            self.A = np.empty((self.n, self.m), dtype=list)
            for i in range(self.n):
                for j in range(self.m):
                    self.A[i, j] = list()

            self.base_coords = [int(np.floor(self.n / 2) - 1), int(np.floor(self.m / 2) - 1)]
            #            print(self.base_coords)
            self.base_sigma = config["base_sigma"]

    def measure_distance(self, source, destination):
        """
        Measure distance on the grid between two points.
        
        Returns
        -------
        Source coordinates are marked by *s*,
        destination coordinates are marked by *d*.
        
        The distance is the following integer:
        $$|x_s-x_d|+|y_s-y_d|$$
        """

        return np.dot(np.abs(np.array(destination) - np.array(source)), [1, 1])

    def create_path(self, source, destination):
        """
        Choose a random shortest path between source and destination.
        
        Parameters
        ----------
        
        source : [int,int]
            grid coordinates of the source
            
        destination : [int,int]
            grid coordinates of the destination
        
        
        Returns
        -------
        
        path : list of coordinate tuples
            coordinate list of a random path between source and destinaton
            
        """

        # distance along the x and the y axis
        dx, dy = np.array(destination) - np.array(source)
        # create a sequence of "x"-es and "y"-s
        # we are going to shuffle this sequence
        # to get a random order of "x" and "y" direction steps
        sequence = ['x'] * int(np.abs(dx)) + ['y'] * int(np.abs(dy))
        shuffle(sequence)
        # source is included in the path
        path = [source]
        for item in sequence:
            if item == "x":
                # we add one step in the "x" direction based on the last position
                path.append([np.sign(dx) + path[-1][0], 0 + path[-1][1]])
            else:
                # we add one step in the "y" direction based on the last position
                path.append([0 + path[-1][0], np.sign(dy) + path[-1][1]])
        return path

    def neighbors(self, coordinates):
        """
        Calculate the neighbors of a coordinate.
        On the edges of the simulation grid, there are no neighbors.
        (E.g. there are only 2 neighbors in the corners.)

        Parameters
        ----------
        
        coordinates : [int,int]
            input grid coordinate
            
        Returns
        -------
        
        ns : list of coordinate tuples
            list containing the coordinates of the neighbors        
        """

        ns = set()
        for dx, dy in [(1, 0), (0, 1), (-1, 0), (0, -1)]:
            new_x = coordinates[0] + dx
            new_y = coordinates[1] + dy

            if (0 <= new_x) and (self.n > new_x) and (0 <= new_y) and (self.m > new_y):
                ns.add((new_x, new_y))
        return ns

    def create_request_coords(self, mean=None):
        """
        Creates random request coords based on the base_coords and the
        base_sigma according to a 2D Gauss.
        
        Returns
        -------
        
        x,y
            coordinate tuple
        """

        done = False
        while not done:
            if mean is None:
                mean = self.base_coords
            cov = np.array([[self.base_sigma ** 2, 0], [0, self.base_sigma ** 2]])

            x, y = np.random.multivariate_normal(mean, cov)

            x = int(np.floor(x))
            y = int(np.floor(y))

            if (x >= 0) and (x < self.n) and (y >= 0) and (y < self.m):
                done = True
        return x, y


class Taxi:
    """
    Represents a taxi in the simulation.
    
    Attributes
    ----------
    
    x : int
        horizontal grid coordinate
    
    y : int
        vertical grid coordinate
    
    taxi_id : int
        unique identifier of taxi
        
    available : bool
        flag that stores whether taxi is free
        
    to_request : bool
        flag that stores when taxi is moving towards a request
        but there is still no user sitting in it
    
    with_passenger : bool
        flag that stores when taxi is carrying a passenger
        
    actual_request_executing : int
        id of request that is being executed by the taxi
        
    requests_completed : list of ints
        list of requests completed by taxi
        
    time_waiting : int
        time spent with empty waiting
    
    time_serving : int
        time spent with carrying a passenger

    time_to_request : int
        time spent from call assignment to pickup, without a passenger

    time_cruising : int
        time spent with travelling empty with no assigned requests

    next_destination : Queue
        Queue that stores the path forward of the taxi
    
    """

    def __init__(self, coords=None, taxi_id=None):
        if coords is None:
            print("You have to put your taxi somewhere in the city!")
        elif taxi_id is None:
            print("Not a licenced taxi.")
        else:

            self.x = coords[0]
            self.y = coords[1]

            self.taxi_id = taxi_id

            self.available = True
            self.to_request = False
            self.with_passenger = False

            self.actual_request_executing = None
            self.requests_completed = []

            # types of time metrics to be stored
            self.time_waiting = 0
            self.time_serving = 0
            self.time_cruising = 0
            self.time_to_request = 0

            # storing steps to take
            self.next_destination = Queue()  # path to travel

    def __str__(self):
        s = [
            "Taxi ",
            str(self.taxi_id),
            ".\n\tPosition ",
            str(self.x) + "," + str(self.y) + "\n"
        ]
        if self.available:
            s += ["\tAvailable.\n"]
        elif self.to_request:
            s += ["\tTravelling towards request " + str(self.actual_request_executing) + ".\n"]
        elif self.with_passenger:
            s += ["\tCarrying the passenger of request " + str(self.actual_request_executing) + ".\n"]

        return "".join(s)


class Request:
    """
    Represents a request that is being made.
    
    Attributes
    ----------
    
    ox,oy : int
        grid coordinates of request origin
        
    dx,dy : int
        grid coordinates of request destination
        
    request_id : int
        unique id of request
    
    request_timestamp : int
        timestamp of request
        
    pickup_timestamp : int
        timestamp of taxi arrival
        
    dropoff_timestamp : int
        timestamp of request completed
    
    taxi_id : int
        id of taxi that serves the request
    
    waiting_time : int
        how much time the user had to wait until picked up
    """

    def __init__(self, ocoords=None, dcoords=None, request_id=None, timestamp=None):
        """
        
        """
        if (ocoords is None) or (dcoords is None):
            print("A request has to have a well-defined origin and destination.")
        elif request_id is None:
            print("Please indentify each request uniquely.")
        elif timestamp is None:
            print("Please give a timestamp for the request!")
        else:
            # pickup coordinates
            self.ox = ocoords[0]
            self.oy = ocoords[1]

            # desired dropoff coordinates
            self.dx = dcoords[0]
            self.dy = dcoords[1]

            self.request_id = request_id

            self.request_timestamp = timestamp

            # travel data
            self.pickup_timestamp = None
            self.dropoff_timestamp = None
            self.taxi_id = None

            self.waiting_time = 0

    def __str__(self):
        s = [
            "Request ",
            str(self.request_id),
            ".\n\tOrigin ",
            str(self.ox) + "," + str(self.oy) + "\n",
            "\tDestination ",
            str(self.dx) + "," + str(self.dy) + "\n"
        ]
        if self.taxi_id is not None:
            s += ["\tTaxi assigned ", str(self.taxi_id), ".\n"]
        else:
            s += ["\tWaiting."]

        return "".join(s)


class Simulation:
    """
    Class for containing the elements of the simulation.
    
    Attributes
    ----------
    time : int
        stores the time elapsed in the simulation
    
    num_taxis : int
        how many taxis there are
    
    request_rate : float
        rate of requests per time period
    
    hard_limit : int
        max distance from which a taxi is still assigned to a request
    
    taxis : dict
        storing all Taxi() instances in a dict
        keys are `taxi_id`s
    
    latest_taxi_id : int
        shows latest given taxi_id
        used or generating new taxis
    
    taxis_available : list of int
        stores `taxi_id`s of available taxis
    
    taxis_to_request : list of int
        stores `taxi_id`s of taxis moving to serve a request
    
    taxis_to_destination : list of int
        stores `taxi_id`s of taxis with passenger
    
    requests : dict
        storing all Request() instances in a dict
        keys are `request_id`s
    
    latest_request_id : int
        shows latest given request_id
        used or generating new requests
    
    requests_pending : list of int
        requests waiting to be served
    
    requests_in_progress : list of int
        requests with assigned taxis
    
    requests_fulfilled : list of int
        requests that are closed
    
    requests_dropped : list of int
        unsuccessful requests
    
    city : City
        geometry of class City() underlying the simulation
        
    show_map_labels : bool
    
    """

    def __init__(self, **config):

        # initializing empty grid
        self.time = 0

        self.num_taxis = config["num_taxis"]
        self.request_rate = config["request_rate"]

        if "price_fixed" in config:
            # price that is used for every trip
            self.price_fixed = config["price_fixed"]
        else:
            self.price_fixed = 0

        if "price_per_dist" in config:
            # price per unit distance while carrying a passenger
            self.price_per_dist = config["price_per_dist"]
        else:
            self.price_per_dist = 1

        if "cost_per_unit" in config:
            # cost per unit distance (e.g. gas)
            self.cost_per_unit = config["cost_per_unit"]
        else:
            self.cost_per_unit = 0

        if "cost_per_time" in config:
            # cost per time (e.g. amortization)
            self.cost_per_time = config["cost_per_time"]
        else:
            self.cost_per_time = 0

        if "matching" in config:
            self.matching = config["matching"]

        if "batch_size" in config:
            self.batch_size = config["batch_size"]

        if "max_time" in config:
            self.max_time = config["max_time"]

        if "max_request_waiting_time" in config:
            self.max_request_waiting_time = config["max_request_waiting_time"]
        else:
            self.max_request_waiting_time = 10000 #TODO

        if ("batch_size" in config) and ("max_time" in config):
            self.num_iter = int(np.ceil(self.max_time/self.batch_size))
        else:
            self.num_iter = None

        self.taxis = {}
        self.latest_taxi_id = 0

        self.taxis_available = []
        self.taxis_to_request = []
        self.taxis_to_destination = []

        self.requests = {}
        self.latest_request_id = 0

        self.requests_pending = []
        self.requests_in_progress = []
        self.requests_fulfilled = []
        self.requests_dropped = []

        self.city = City(**config)

        if "hard_limit" in config:
            self.hard_limit = config["hard_limit"]
        else:
            self.hard_limit = self.city.n+self.city.m

        self.log = config["log"]
        self.show_plot = config["show_plot"]

        # initializing simulation with taxis
        for t in range(self.num_taxis):
            self.add_taxi()

        if self.show_plot:
            #         plotting variables
            self.canvas = plt.figure()
            self.canvas_ax = self.canvas.add_subplot(1, 1, 1)
            self.canvas_ax.set_aspect('equal', 'box')
            self.cmap = plt.get_cmap('viridis')
            self.taxi_colors = np.linspace(0, 1, self.num_taxis)
            self.show_map_labels = config["show_map_labels"]
            self.show_pending = config["show_pending"]
            self.init_canvas()

    def init_canvas(self):
        """
        Initialize plot.
        
        """
        self.canvas_ax.clear()
        self.canvas_ax.set_xlim(-0.5, self.city.n - 0.5)
        self.canvas_ax.set_ylim(-0.5, self.city.m - 0.5)

        self.canvas_ax.tick_params(length=0)
        self.canvas_ax.xaxis.set_ticks(list(range(self.city.n)))
        self.canvas_ax.yaxis.set_ticks(list(range(self.city.m)))
        if not self.show_map_labels:
            self.canvas_ax.xaxis.set_ticklabels([])
            self.canvas_ax.yaxis.set_ticklabels([])

        self.canvas_ax.set_aspect('equal', 'box')
        self.canvas.tight_layout()
        self.canvas_ax.grid()

    def add_taxi(self):
        """
        Create new taxi.
        
        """
        # create a taxi at the base
        tx = Taxi(self.city.base_coords, self.latest_taxi_id)

        # add to taxi storage
        self.taxis[self.latest_taxi_id] = tx
        # add to available taxi storage
        self.city.A[self.city.base_coords[0], self.city.base_coords[1]].append(
            self.latest_taxi_id)  # add to available taxi matrix
        self.taxis_available.append(self.latest_taxi_id)

        # increase id
        self.latest_taxi_id += 1

    def add_request(self):
        """
        Create new request.
        
        """
        # here we randonly choose a place for the request
        # origin
        ox, oy = self.city.create_request_coords()
        # destination
        dx, dy = self.city.create_request_coords((ox, oy))

        r = Request([ox, oy], [dx, dy], self.latest_request_id, self.time)

        # add to request storage
        self.requests[self.latest_request_id] = r
        # add to free users
        self.requests_pending.append(self.latest_request_id)

        self.latest_request_id += 1

    def go_to_base(self, taxi_id, bcoords):
        """
        This function sends the taxi to the base rom wherever it is.
        """
        # actual coordinates
        acoords = [self.taxis[taxi_id].x, self.taxis[taxi_id].y]
        # path between actual coordinates and destination
        path = self.city.create_path(acoords, bcoords)
        # erase path memory
        self.taxis[taxi_id].with_passenger = False
        self.taxis[taxi_id].to_request = False
        self.taxis[taxi_id].available = True
        #        print("Erasing path memory, Taxi "+str(taxi_id)+".")
        self.taxis[taxi_id].next_destination = Queue()
        # put path into taxi path queue
        #        print("Filling path memory, Taxi "+str(taxi_id)+". Path ",path)
        for p in path:
            self.taxis[taxi_id].next_destination.put(p)

    def assign_request(self, request_id, taxi_id):
        """
        Given a request_id, taxi_id pair, this function makes the match.
        It sets new state variables for the request and the taxi, updates path of the taxi etc.
        """
        r = self.requests[request_id]
        t = self.taxis[taxi_id]

        # pair the match
        t.actual_request_executing = request_id
        r.taxi_id = taxi_id

        # remove taxi from the available ones
        self.city.A[t.x, t.y].remove(taxi_id)
        self.taxis_available.remove(taxi_id)
        t.with_passenger = False
        t.available = False
        t.to_request = True

        # mark taxi as moving to request
        self.taxis_to_request.append(taxi_id)

        # forget the path that has been assigned
        t.next_destination = Queue()

        # create new path: to user, then to destination
        path = self.city.create_path([t.x, t.y], [r.ox, r.oy]) + \
           self.city.create_path([r.ox, r.oy], [r.dx, r.dy])[1:]
        for p in path:
            t.next_destination.put(p)

        # remove request from the pending ones, label it as "in progress"
        self.requests_pending.remove(request_id)
        self.requests_in_progress.append(request_id)

        # update taxi state in taxi storage
        self.taxis[taxi_id] = t
        # update request state
        self.requests[request_id] = r

        if self.log:
            print("\tM request " + str(request_id) + " taxi " + str(taxi_id))

    def matching_algorithm(self, mode="baseline"):
        """
        This function contains the possible matching functions which are selected by the mode keyword.

        Parameters
        ----------

        mode : str, default baseline
            matching algorithm mode
                * baseline : assigning a random taxi to the user
                * request_optimized : least possible waiting times or users
                * distance_based_match : sending the nearest available taxi for the user
                * levelling : based on different measures, we want to equalize payment for taxi drivers
        """

        if len(self.requests_pending)==0:
            if self.log:
                print("No pending requests.")
            return

        if mode == "baseline_random_user_random_taxi":

            # go through the pending requests in a random order
            #rp_list = deepcopy(self.requests_pending)
            #shuffle(rp_list)

            # go through the pending requests in the order of waiting times
            waiting_times = []
            rp_list = deepcopy(self.requests_pending)
            for request_id in rp_list:
                w = self.requests[request_id].waiting_time
                if w<=self.max_request_waiting_time:
                    waiting_times.append(w)
                else:
                    self.requests_pending.remove(request_id)
                    self.requests_dropped.append(request_id)

            rp_list = list(np.array(self.requests_pending)[np.argsort(waiting_times)])

            taxi_counter = 0
            taxi_counter_max = len(self.taxis_available)

            for request_id in rp_list:
                if taxi_counter>=taxi_counter_max:
                    break

                # select a random taxi
                taxi_id = choice(self.taxis_available)

                # make assignment
                self.assign_request(request_id, taxi_id)
                taxi_counter+=1

        elif mode == "baseline_random_user_nearest_taxi":
            # go through the pending requests in the order of waiting times
            waiting_times = []
            rp_list = deepcopy(self.requests_pending)
            for request_id in rp_list:
                w = self.requests[request_id].waiting_time
                if w<=self.max_request_waiting_time:
                    waiting_times.append(w)
                else:
                    self.requests_pending.remove(request_id)
                    self.requests_dropped.append(request_id)

            rp_list = list(np.array(self.requests_pending)[np.argsort(waiting_times)])

            taxi_counter = 0
            taxi_counter_max = len(self.taxis_available)

            for request_id in rp_list:
                if taxi_counter >= taxi_counter_max:
                    break
                # fetch request
                r = self.requests[request_id]

                # search for nearest free taxi
                possible_taxi_ids = self.find_nearest_available_taxis([r.ox, r.oy])

                # if there was one
                if len(possible_taxi_ids) > 0:
                    # select taxi
                    taxi_id = choice(possible_taxi_ids)
                    self.assign_request(request_id, taxi_id)
                    taxi_counter+=1

        elif mode == "first_come_first_served":
            # go through the pending requests in the order of waiting times
            waiting_times = []
            rp_list = deepcopy(self.requests_pending)
            for request_id in rp_list:
                w = self.requests[request_id].waiting_time
                if w<=self.max_request_waiting_time:
                    waiting_times.append(w)
                else:
                    self.requests_pending.remove(request_id)
                    self.requests_dropped.append(request_id)

            rp_list = list(np.array(self.requests_pending)[np.argsort(waiting_times)])

            taxi_counter = 0
            taxi_counter_max = len(self.taxis_available)

            for request_id in rp_list:
                if taxi_counter >= taxi_counter_max:
                    break
                # fetch request
                r = self.requests[request_id]

                # search for nearest free taxi
                possible_taxi_ids = self.find_nearest_available_taxis([r.ox, r.oy])

                # if there was one
                if len(possible_taxi_ids) > 0:
                    # select taxi
                    taxi_id = choice(possible_taxi_ids)
                    self.assign_request(request_id, taxi_id)
                    taxi_counter+=1

        elif mode == "levelling1_random_user_poorest_taxi":
            # always order taxi that has earned the least money so far

            # go through the pending requests in a random order
            # rp_list = deepcopy(self.requests_pending)
            # shuffle(rp_list)

            # go through the pending requests in the order of waiting times
            waiting_times = []
            for request_id in self.requests_pending:
                waiting_times.append(self.requests[request_id].waiting_time)
            rp_list = list(np.array(self.requests_pending)[np.argsort(waiting_times)])

            # evaulate the earnings of the available taxis so far
            taxi_earnings = []
            for taxi_id in self.taxis_available:
                taxi_earnings.append(self.eval_taxi_income(taxi_id))
            ta_list = list(np.array(self.taxis_available)[np.argsort(taxi_earnings)])

            # do the matching
            taxi_counter = 0
            taxi_counter_max = len(self.taxis_available)

            for request_id in rp_list:
                if taxi_counter >= taxi_counter_max:
                    break

                # take the least earning taxi so far to request
                taxi_id = ta_list[i]

                # make assignment
                self.assign_request(request_id, taxi_id)
                taxi_counter+=1

        elif mode == "levelling2_random_user_nearest_poorest_taxi_w_waiting_limit":
            # always order taxi that has earned the least money so far
            # but choose only from the nearest ones
            # hard limiting: e.g. if there is no taxi within the radius, then quit

            # go through the pending requests in a random order
            # rp_list = deepcopy(self.requests_pending)
            # shuffle(rp_list)

            # go through the pending requests in the order of waiting times
            waiting_times = []
            rp_list = deepcopy(self.requests_pending)
            for request_id in rp_list:
                w = self.requests[request_id].waiting_time
                if w<=self.max_request_waiting_time:
                    waiting_times.append(w)
                else:
                    self.requests_pending.remove(request_id)
                    self.requests_dropped.append(request_id)

            rp_list = list(np.array(self.requests_pending)[np.argsort(waiting_times)])

            # evaulate the earnings of the available taxis so far
            taxi_earnings = []
            for taxi_id in self.taxis_available:
                taxi_earnings.append(self.eval_taxi_income(taxi_id))
            ta_list = list(np.array(self.taxis_available)[np.argsort(taxi_earnings)])

            # do the matching
            taxi_counter = 0
            taxi_counter_max = len(self.taxis_available)

            for request_id in rp_list:
                if taxi_counter >= taxi_counter_max:
                    break

                r = self.requests[request_id]

                # find nearest vehicles in a radius
                possible_taxi_ids = self.find_nearest_available_taxis([r.ox,r.oy],mode="circle",radius=self.hard_limit)
                for t in ta_list:
                    if t in possible_taxi_ids:
                        # on first hit
                        # make assignment
                        self.assign_request(request_id, t)
                        taxi_counter+=1
                        break


        elif mode == "levelling3_random_user_nearest_poorest_taxi":
            # always order taxi that has earned the least money so far
            # but first choose only from the nearest ones
            # if there is no taxi within the radius, then pick the least earning one

            # go through the pending requests in a random order
            # rp_list = deepcopy(self.requests_pending)
            # shuffle(rp_list)

            # go through the pending requests in the order of waiting times
            waiting_times = []
            for request_id in self.requests_pending:
                waiting_times.append(self.requests[request_id].waiting_time)
            rp_list = list(np.array(self.requests_pending)[np.argsort(waiting_times)])

            # evaulate the earnings of the available taxis so far
            taxi_earnings = []
            for taxi_id in self.taxis_available:
                taxi_earnings.append(self.eval_taxi_income(taxi_id))
            ta_list = list(np.array(self.taxis_available)[np.argsort(taxi_earnings)])

            # do the matching
            taxi_counter = 0
            taxi_counter_max = len(self.taxis_available)

            for request_id in rp_list:
                if taxi_counter >= taxi_counter_max:
                    break

                r = self.requests[request_id]

                # find nearest vehicles in a radius
                possible_taxi_ids = self.find_nearest_available_taxis([r.ox, r.oy], mode="circle", radius=8)
                for t in ta_list:
                    if t in possible_taxi_ids:
                        # on first hit
                        # make assignment
                        self.assign_request(request_id, t)
                        taxi_counter+=1
                        break
                #????
                if (self.requests[request_id].taxi_id is None) and (len(self.taxis_available)>0):
                    self.assign_request(request_id, choice(self.taxis_available))

        # levelling4 could be based on expected income
        # levelling5 could be based on distance and income together

        else:
            print("I know of no such assigment mode! Please provide a valid one!")

    def pickup_request(self, request_id):
        """
        Pick up passenger.
        
        Parameters
        ----------
        
        request_id : int
        """

        # mark pickup timestamp
        r = self.requests[request_id]
        r.pickup_timestamp = self.time
        t = self.taxis[r.taxi_id]

        self.taxis_to_request.remove(r.taxi_id)
        self.taxis_to_destination.append(r.taxi_id)

        # change taxi state to with passenger
        t.to_request = False
        t.with_passenger = True
        t.available = False

        # set request waiting time
        r.waiting_time = self.time - r.request_timestamp

        # update request and taxi instances
        self.requests[request_id] = r
        self.taxis[r.taxi_id] = t
        if self.log:
            print('\tP ' + "request " + str(request_id) + ' taxi ' + str(t.taxi_id))

    def dropoff_request(self, request_id):
        """
        Drop off passenger, when taxi reached request destination.
        
        """

        # mark dropoff timestamp
        r = self.requests[request_id]
        r.dropoff_timestamp = self.time
        t = self.taxis[r.taxi_id]

        # change taxi state to available
        t.with_passenger = False
        t.available = True
        t.actual_request_executing = None

        # update taxi lists
        self.city.A[t.x, t.y].append(r.taxi_id)
        self.taxis_to_destination.remove(r.taxi_id)
        self.taxis_available.append(r.taxi_id)

        # udate request lists
        self.requests_in_progress.remove(request_id)
        t.requests_completed.append(request_id)
        self.requests_fulfilled.append(request_id)

        # update request and taxi instances
        self.requests[request_id] = r
        self.taxis[r.taxi_id] = t
        if self.log:
            print("\tD request " + str(request_id) + ' taxi ' + str(t.taxi_id))

    def find_nearest_available_taxis(
            self,
            source,
            mode="nearest",
            radius=None):
        """
        This function lists the available taxis according to mode.

        Parameters
        ----------

        source : tuple, no default
            coordinates of the place from which we want to determine the nearest
            possible taxi

        mode : str, default "nearest"
            determines the mode of taxi listing
                * "nearest" lists only the nearest taxis, returns a list where there \
                are all taxis at the nearest possible distance from the source

                * "circle" lists all taxis within a certain distance of the source

        radius : int, optional
            if mode is "circle", gives the circle radius
        """
        frontier = [source]
        visited = []
        possible_plate_numbers = []

        distance = 0
        while distance <= self.hard_limit:
            # check available taxis in given nodes
            for x, y in list(frontier):
                visited.append((x, y))  # mark the coordinate as visited
                for t in self.city.A[x, y]:  # get all available taxis there
                    possible_plate_numbers.append(t)
            # if we visited everybody, break
            if len(visited) == self.city.n * self.city.m:
                if self.log:
                    print("\tNo available taxis at this timepoint!")
                break
            # if we got available taxis in nearest mode, break
            if (mode == "nearest") and (len(possible_plate_numbers) > 0):
                break
            # if we reached our desired depth, break
            if (mode == "circle") and (distance > radius):
                break
            # if not, move on to next depth
            else:
                new_frontier = set()
                for f in frontier:
                    new_frontier = \
                        new_frontier.union(self.city.neighbors(f)).difference(set(visited))
                frontier = list(new_frontier)
                distance += 1

        return possible_plate_numbers

    def eval_taxi_income(self,taxi_id):
        """

        Parameters
        ----------
        taxi_id : int
            select taxi from self.taxis with id

        Returns
        -------
        price : int
            evaulated earnnigs of the taxi based on config

        """

        t = self.taxis[taxi_id]

        price =\
            self.price_fixed +\
            t.time_serving*self.price_per_dist -\
            (t.time_cruising+t.time_serving+t.time_to_request)*self.cost_per_unit -\
            (t.time_serving+t.time_cruising+t.time_to_request+t.time_waiting)*self.cost_per_time

        return price

    def plot_simulation(self):
        """
        Draws current state of the simulation on the predefined grid of the class.
        
        Is based on the taxis and requests and their internal states.
        """

        self.init_canvas()

        for i, taxi_id in enumerate(self.taxis.keys()):
            t = self.taxis[taxi_id]

            # plot a circle at the place of the taxi
            self.canvas_ax.plot(t.x, t.y, 'o', ms=10, c=self.cmap(self.taxi_colors[i]))

            if self.show_map_labels:
                self.canvas_ax.annotate(
                    str(i),
                    xy=(t.x, t.y),
                    xytext=(t.x, t.y),
                    ha='center',
                    va='center',
                    color='white'
                )

            # if the taxi has a path ahead of it, plot it
            if t.next_destination.qsize() != 0:
                path = np.array([[t.x, t.y]] + list(t.next_destination.queue))
                if len(path) > 1:
                    xp, yp = path.T
                    # plot path
                    self.canvas_ax.plot(
                        xp,
                        yp,
                        '-',
                        c=self.cmap(self.taxi_colors[i])
                    )
                    # plot a star at taxi destination
                    self.canvas_ax.plot(
                        path[-1][0],
                        path[-1][1],
                        '*',
                        ms=5,
                        c=self.cmap(self.taxi_colors[i])
                    )

            # if a taxi serves a request, put request on the map
            request_id = t.actual_request_executing
            if (request_id is not None) and (not t.with_passenger):
                r = self.requests[request_id]
                self.canvas_ax.plot(
                    r.ox,
                    r.oy,
                    'ro',
                    ms=3
                )
                if self.show_map_labels:
                    self.canvas_ax.annotate(
                        request_id,
                        xy=(r.ox, r.oy),
                        xytext=(r.ox - 0.2, r.oy - 0.2),
                        ha='center',
                        va='center'
                    )

        # plot taxi base
        self.canvas_ax.plot(
            self.city.base_coords[0],
            self.city.base_coords[1],
            'ks',
            ms=15
        )

        # plot pending requests
        if self.show_pending:
            for request_id in self.requests_pending:
                self.canvas_ax.plot(
                    self.requests[request_id].ox,
                    self.requests[request_id].oy,
                    'ro',
                    ms=3,
                    alpha=0.5
                )

        self.canvas.show()

    def move_taxi(self, taxi_id):
        """
        Move a taxi one step forward according to its path queue.
        
        Update taxi position on availablity grid, if necessary.
        
        Parameters
        ----------
        
        taxi_id : int
            unique id of taxi that we want to move
        """
        t = self.taxis[taxi_id]
        try:
            # move taxi one step forward    
            move = t.next_destination.get_nowait()

            old_x = t.x
            old_y = t.y

            t.x = move[0]
            t.y = move[1]

            if t.with_passenger:
                t.time_serving += 1
            else:
                if t.available:
                    t.time_cruising += 1
                else:
                    t.time_to_request +=1

            # move available taxis on availability grid
            if t.available:
                self.city.A[old_x, old_y].remove(taxi_id)
                self.city.A[t.x, t.y].append(taxi_id)

            # update taxi instance
            if self.log:
                print("\tF moved taxi " + str(taxi_id) + " remaining path ", list(t.next_destination.queue), "\n",
                      end="")
        except:
            self.taxis[taxi_id].time_waiting += 1

        self.taxis[taxi_id] = t


    def run_batch(self, run_id):
        """
        Create a batch run, where metrics are evaluated at every batch step and at the end.
        
        Parameters
        ----------
        
        run_id : str
            id that stands for simulation
        """

        measurement = Measurements(self)

        if self.num_iter is None:
            print("No batch run parameters were defined in the config file, please add them!")
            return

        print("Running simulation with run_id "+run_id+".")
        print("Batch time "+str(self.batch_size)+".")
        print("Number of iterations "+str(self.num_iter)+".")
        print("Total time simulated "+str(self.batch_size*self.num_iter)+".")
        print("Starting...")

        data_path = 'results'

        t = []
        w = []
        fields = set()
        results = []

        time1 = time()
        for i in range(self.num_iter):
            # tick the clock
            for k in range(self.batch_size):
                self.step_time("")

            ptm = measurement.read_per_taxi_metrics()
            prm = measurement.read_per_request_metrics()
            results.append(measurement.read_aggregated_metrics(ptm,prm))
            time2=time()
            print('Simulation batch '+str(i+1)+'/'+str(self.num_iter)+' , %.2f sec/batch.' % (time2-time1))
            time1=time2

        # dumping batch results
        pd.DataFrame.from_dict(results).to_csv(data_path + '/run_' + run_id + '_aggregates.csv')

        # dumping per taxi metrics out
        f = open(data_path + '/run_' + run_id + '_per_taxi_metrics.json', 'w')
        json.dump(ptm,f)
        f.close()

        # dumping per request metrics out
        f = open(data_path + '/run_' + run_id + '_per_request_metrics.json', 'w')
        json.dump(prm, f)
        f.close()

        print("Done.\n")


    def step_time(self, handler):
        """
        Ticks simulation time by 1.
        """

        if self.log:
            print("timestamp " + str(self.time))

        # move every taxi one step towards its destination
        for i, taxi_id in enumerate(self.taxis.keys()):
            self.move_taxi(taxi_id)
            t = self.taxis[taxi_id]

            # if a taxi can pick up its passenger, do it
            if taxi_id in self.taxis_to_request:
                r = self.requests[t.actual_request_executing]
                if (t.x == r.ox) and (t.y == r.oy):
                    self.pickup_request(t.actual_request_executing)
            # if a taxi can drop of its passenger, do it
            elif taxi_id in self.taxis_to_destination:
                r = self.requests[t.actual_request_executing]
                if (t.x == r.dx) and (t.y == r.dy):
                    self.dropoff_request(r.request_id)
                    self.go_to_base(taxi_id, self.city.base_coords)

        # generate requests
        for i in range(self.request_rate):
            self.add_request()

        # make matchings
        self.matching_algorithm(mode=self.matching)

        # step time
        if self.show_plot:
            self.plot_simulation()
        self.time += 1

class Measurements:

    def __init__(self,simulation):
        self.simulation = simulation

    def read_per_taxi_metrics(self):
        """
        Returns metrics for taxis.

        Outputs a dictionary that stores these metrics in lists and the timestamp of the call.

        Output
        ------

        timestamp: int
            the timestamp of the measurement

        avg_trip_length: list of floats
            average trip length

        std_trip_length: list of floats
            standard deviation of trip lengths per taxi

        avg_trip_price: list of floats
            average trip price per taxi

        std_trip_price: list of floats
            standard deviation of trip price per taxi

        number_of_requests_completed: list of ints
            how many passengers has the taxi served

        ratio_online: list of floats
            ratio of useful travel time from overall time per taxi
            online/(online+to_request+cruising+waiting)

        ratio_to_request: list of floats
            ratio of empty travel time (from assignment to pickup)

        ratio_cruising: list of floats
            ratio of travelling with no assigned request

        ratio_waiting: list of floats
            ratio of standing at a post with no assigned request
        """

        # for the taxis

        # average trip lengths per taxi
        # standard deviation of trip lengths per taxi
        trip_avg_length = []
        trip_std_length = []
        trip_avg_price = []
        trip_std_price = []
        trip_num_completed = []

        ratio_online = []
        ratio_serving = []
        ratio_to_request = []
        ratio_cruising = []
        ratio_waiting = []

        for taxi_id in self.simulation.taxis:
            taxi = self.simulation.taxis[taxi_id]
            req_lengths = []
            req_prices = []

            for request_id in taxi.requests_completed:
                r = self.simulation.requests[request_id]
                length = np.abs(r.dy - r.oy) + np.abs(r.dx - r.ox)
                req_lengths.append(length)
                price = self.simulation.eval_taxi_income(taxi_id)
                req_prices.append(price)
            if len(req_prices) > 0:
                trip_avg_price.append(np.nanmean(req_prices))
                trip_std_price.append(np.nanstd(req_prices))
                trip_avg_length.append(np.nanmean(req_lengths))
                trip_std_length.append(np.nanstd(req_lengths))
            else:
                trip_avg_price.append(0)
                trip_std_price.append(np.nan)
                trip_avg_length.append(0)
                trip_std_length.append(np.nan)
            trip_num_completed.append(len(req_prices))

            s = taxi.time_serving
            w = taxi.time_waiting
            r = taxi.time_to_request
            c = taxi.time_cruising
            total = s+w+r+c

            ratio_serving.append( s / total )
            ratio_cruising.append( c / total )
            ratio_online.append( (s+r) / total )
            ratio_waiting.append( w / total )
            ratio_to_request.append( r / total )

        return {
            "timestamp": self.simulation.time,
            "trip_avg_length": trip_avg_length,
            "trip_std_length": trip_std_length,
            "trip_avg_price": trip_avg_price,
            "trip_std_price": trip_std_price,
            "trip_num_completed": trip_num_completed,
            "ratio_serving": ratio_serving,
            "ratio_cruising": ratio_cruising,
            "ratio_online":ratio_online,
            "ratio_waiting":ratio_waiting,
            "ratio_to_request":ratio_to_request
        }

    def read_per_request_metrics(self):

        # for the requests

        request_completed = []
        total = 0
        request_last_waiting_times = []
        request_lengths = []

        for request_id in self.simulation.requests:
            r = self.simulation.requests[request_id]
            if r.dropoff_timestamp is not None:
                request_completed.append(1)
                request_lengths.append(float(np.abs(r.dy - r.oy) + np.abs(r.dx - r.ox)))
            else:
                request_completed.append(0)

            total += 1
            # to forget history
            # system-level waiting time peak detection
            # it would not be sensible to include all previous waiting times
            if (self.simulation.time - r.request_timestamp) < 100:
                if r.dropoff_timestamp is None:
                    request_last_waiting_times.append(r.waiting_time)

        return {
            "timestamp":self.simulation.time,
            "request_completed":request_completed,
            "request_last_waiting_times":request_last_waiting_times,
            "request_lengths":request_lengths
        }

    @staticmethod
    def read_aggregated_metrics(per_taxi_metrics, per_request_metrics):
        metrics = {"timestamp": per_taxi_metrics["timestamp"]}

        for k in per_taxi_metrics:
            if k[0:3]=='trip':
                if k[5]=='a':
                    metrics['avg_'+k] = np.nanmean(per_taxi_metrics[k])
                    metrics['std_' + k] = np.nanstd(per_taxi_metrics[k])
            elif k[0:5]=='ratio':
                metrics['avg_' + k] = np.nanmean(per_taxi_metrics[k])
                metrics['std_' + k] = np.nanstd(per_taxi_metrics[k])
                y,x = np.histogram(per_taxi_metrics[k],bins=100,density=True)
                metrics['entropy_' + k] = entropy(y)

        for k in per_request_metrics:
            metrics['avg_' + k] = np.nanmean(per_request_metrics[k])
            metrics['std_' + k] = np.nanstd(per_request_metrics[k])

        return metrics