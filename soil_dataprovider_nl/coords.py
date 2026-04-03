# -*- coding: utf-8 -*-
# Copyright (c) 2026 Wageningen Environmental Research, Wageningen-UR
# Allard de Wit (allard.dewit@wur.nl), April 2026
import pyproj

class CoordinateStore:
    rd_stelsel = "epsg:7415"

    def __init__(self, x, y):
        self._conv = pyproj.Proj(self.rd_stelsel)

        if self._is_valid_xcoord_rd(x) and self._is_valid_ycoord_rd(y):
            self.xcoord = x
            self.ycoord = y
            self.lon, self.lat = self.from_RD(x, y)
        elif self._is_valid_longitude(x) and self._is_valid_latitude(y):
            self.lon = x
            self.lat = y
            self.xcoord, self.ycoord = self.from_lonlat(x, y)
        else:
            raise ValueError(f"Coordinates out of bounding box. Did you swap longitude/latitude?")

    def from_RD(self, x, y):
        return self._conv(x, y, inverse=True)

    def from_lonlat(self, lon, lat):
        return self._conv(lon, lat)

    @staticmethod
    def _is_valid_xcoord_rd(xcoord):
        rdx_min = 7000
        rdx_max = 289000
        return rdx_min < xcoord < rdx_max

    @staticmethod
    def _is_valid_ycoord_rd(ycoord):
        rdy_min = 289000
        rdy_max = 629000
        return  rdy_min < ycoord < rdy_max

    @staticmethod
    def _is_valid_longitude(lon):
        lon_min = 3.2
        lon_max = 7.3
        return lon_min < lon < lon_max

    @staticmethod
    def _is_valid_latitude(lat):
        lat_min = 50.7
        lat_max = 53.6
        return  lat_min < lat < lat_max

    def __str__(self):
        msg = f"RD coordinates for current location: {self.xcoord}, {self.ycoord}\n"
        msg += f"Lon/Lat coordinates for current location: {self.lon}, {self.lat}\n"
        return msg