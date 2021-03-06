# -*- coding: utf-8 -*-

# Copyright (C) 2016 Osmo Salomaa
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""A proxy for information from providers."""

import copy
import importlib.machinery
import os
import pan
import random
import re

__all__ = ("Provider",)


class Provider:

    """A proxy for information from providers."""

    def __new__(cls, id):
        """Return possibly existing instance for `id`."""
        if not hasattr(cls, "_instances"):
            cls._instances = {}
        if not id in cls._instances:
            cls._instances[id] = object.__new__(cls)
        return cls._instances[id]

    def __init__(self, id):
        """Initialize a :class:`Provider` instance."""
        # Initialize properties only once.
        if hasattr(self, "id"): return
        path, values = self._load_attributes(id)
        self.departure_list_item_qml = values["departure_list_item_qml"]
        self.description = values["description"]
        self.id = id
        self.name = values["name"]
        self._path = path
        self._provider = None
        self._stop_cache = {}
        self.update_interval = int(values["update_interval"])
        self._init_provider(id, re.sub(r"\.json$", ".py", path))

    def _add_distances(self, items, x, y):
        """Store distances to given coordinates in-place to `items`."""
        for item in items:
            item["dist"] = pan.util.format_distance(
                pan.util.calculate_distance(
                    x, y, item["x"], item["y"]))

    @pan.util.api_query([])
    def find_departures(self, stops, ignores=None):
        """Return a list of departures from `stops`."""
        if not stops: return []
        departures = self._provider.find_departures(stops)
        departures = pan.util.filter_departures(departures, ignores)
        for departure in departures:
            if "x" in departure and "y" in departure: continue
            # Add coordinates from cache if not set by provider.
            stop = self._stop_cache.get(departure["stop"], None)
            stop = stop or dict(x=0, y=0)
            departure["x"] = stop["x"]
            departure["y"] = stop["y"]
        return departures

    @pan.util.api_query([])
    def find_lines(self, stops):
        """Return a list of lines that use `stops`."""
        if not stops: return []
        return self._provider.find_lines(stops)

    @pan.util.api_query([])
    def find_nearby_stops(self, x, y):
        """Return a list of stops near given coordinates."""
        stops = self._provider.find_nearby_stops(x, y)
        stops = pan.util.sorted_by_distance(stops, x, y)
        self.store_stops(stops)
        self._add_distances(stops, x, y)
        return stops

    @pan.util.api_query([])
    def find_stops(self, query, x, y):
        """Return a list of stops matching `query`."""
        if not query: return []
        stops = self._provider.find_stops(query, x, y)
        self.store_stops(stops)
        self._add_distances(stops, x, y)
        return stops

    def _init_provider(self, id, path):
        """Initialize transit provider module from `path`."""
        name = "pan.provider{:d}".format(random.randrange(10**12))
        loader = importlib.machinery.SourceFileLoader(name, path)
        self._provider = loader.load_module(name)

    def _load_attributes(self, id):
        """Read and return attributes from JSON file."""
        leaf = os.path.join("providers", "{}.json".format(id))
        path = os.path.join(pan.DATA_HOME_DIR, leaf)
        if not os.path.isfile(path):
            path = os.path.join(pan.DATA_DIR, leaf)
        return path, pan.util.read_json(path)

    def store_stops(self, stops):
        """Inject `stops` into the cache of seen stops."""
        for stop in copy.deepcopy(stops):
            self._stop_cache[stop["id"]] = stop
